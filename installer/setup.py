"""Installer for Agesen CamView (Danish and English).

With GUI:  AgesenCamView-Setup-<version>.exe
Silent:    AgesenCamView-Setup-<version>.exe --silent [--dir FOLDER] [--customer "Name"]
           [--lang da|en] [--no-desktop] [--reset]

The package contains no camera settings. On a new PC the program starts empty.
--reset (or the checkbox in the wizard) deletes earlier settings on the PC.

Installs per user in %LOCALAPPDATA%\\Programs\\AgesenCamView, so no administrator
rights are needed. Everything the program needs (Python, Qt, FFmpeg and the
Microsoft C++ runtime) is in the package. Requires Windows 10 or 11, 64-bit.
"""

import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile

from camview import APP_ID, APP_NAME, APP_VERSION, i18n, install_info
from camview.i18n import tr

LOG = os.path.join(os.environ.get("TEMP", "."), f"{APP_ID}-Setup.log")
CONFIG = os.path.join(os.environ.get("APPDATA", ""), APP_ID, "config.json")
# Settings of the old HikViewer, moved over on installation
LEGACY_CONFIG = os.path.join(os.environ.get("APPDATA", ""), install_info.LEGACY_ID, "config.json")


def res(name: str) -> str:
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), name)


def log(msg: str):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def read_config() -> dict:
    for path in (CONFIG, LEGACY_CONFIG):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return {}


def migrate_legacy_config():
    """Move the settings of the old HikViewer (cameras, encrypted passwords) to the new folder."""
    old_dir = os.path.dirname(LEGACY_CONFIG)
    if not os.path.isdir(old_dir):
        return
    if os.path.isfile(LEGACY_CONFIG) and not os.path.isfile(CONFIG):
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        shutil.copy2(LEGACY_CONFIG, CONFIG)
        log("Moved the HikViewer settings")
    shutil.rmtree(old_dir, ignore_errors=True)


def write_settings(**values):
    data = read_config()
    data.update(values)
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG)


def install(target: str, desktop: bool, customer, progress=lambda f, t: None, reset: bool = False):
    target = os.path.abspath(target)
    log(f"Installing {APP_VERSION} to {target} (reset={reset}, language={i18n.language()})")
    if install_info.is_running() or install_info.is_running(install_info.LEGACY_EXE):
        raise RuntimeError(tr("in_running"))
    exe = os.path.join(target, install_info.EXE_NAME)
    if os.path.isdir(target) and os.listdir(target) and not os.path.isfile(exe):
        raise RuntimeError(tr("in_notempty"))
    if reset:
        # Start fresh: cameras, passwords and customer name from an
        # earlier installation on this PC are deleted.
        shutil.rmtree(os.path.dirname(CONFIG), ignore_errors=True)
        shutil.rmtree(os.path.dirname(LEGACY_CONFIG), ignore_errors=True)
    else:
        migrate_legacy_config()
    if install_info.remove_legacy():
        log("Removed the old HikViewer installation")
    if os.path.isfile(exe):
        progress(0.0, tr("in_remove_old"))
        shutil.rmtree(target)   # program files only; the settings live in %APPDATA%
    os.makedirs(target, exist_ok=True)

    with zipfile.ZipFile(res("payload.zip")) as z:
        members = z.infolist()
        total = sum(m.file_size for m in members) or 1
        done = 0
        for m in members:
            z.extract(m, target)
            done += m.file_size
            progress(0.95 * done / total, tr("in_copy"))

    progress(0.96, tr("in_shortcuts"))
    if not install_info.create_shortcut(install_info.start_menu_shortcut(), exe, target):
        log("Could not create the Start menu shortcut")
    desk = install_info.desktop_shortcut()
    if desktop:
        if not install_info.create_shortcut(desk, exe, target):
            log("Could not create the desktop shortcut")
    elif os.path.exists(desk):
        os.remove(desk)
    progress(0.98, tr("in_register"))
    install_info.register(target, APP_VERSION)
    values = {"language": i18n.language()}
    if customer is not None:
        values["customer"] = customer.strip()
    write_settings(**values)
    progress(1.0, tr("in_finished"))
    log("OK")
    return exe


# --- Silent ------------------------------------------------------------------------

def silent(argv) -> int:
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default
    # On upgrade, keep the language the program already uses.
    i18n.set_language(opt("--lang") or read_config().get("language", ""))
    try:
        install(opt("--dir", install_info.installed_dir() or install_info.default_install_dir()),
                "--no-desktop" not in argv, opt("--customer"), reset="--reset" in argv)
        return 0
    except Exception:  # noqa: BLE001
        log(traceback.format_exc())
        return 1


# --- GUI ------------------------------------------------------------------------------

def gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

    previous = read_config()
    i18n.set_language(previous.get("language", ""))

    root = tk.Tk()
    scale = root.winfo_fpixels("1i") / 96.0
    px = lambda v: int(v * scale)  # noqa: E731
    root.geometry(f"{px(580)}x{px(460)}")
    root.resizable(False, False)
    try:
        root.iconbitmap(res("icon.ico"))
    except tk.TclError:
        pass

    RED = "#DA3648"
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("Title.TLabel", font=("Segoe UI", 15, "bold"))
    style.configure("Body.TLabel", font=("Segoe UI", 10))
    style.configure("Small.TLabel", font=("Segoe UI", 9), foreground="#666")

    header = tk.Frame(root, bg="white", height=px(84))
    header.pack(fill="x")
    header.pack_propagate(False)
    try:
        logo = tk.PhotoImage(file=res("installer_logo.png"))
        f = max(1, round(logo.height() / px(56)))
        logo = logo.subsample(f, f)
        tk.Label(header, image=logo, bg="white").pack(side="left", padx=px(18))
        header.logo = logo
    except tk.TclError:
        pass
    subtitle = tk.Label(header, bg="white", fg="#222", font=("Segoe UI", 11), justify="right")
    subtitle.pack(side="right", padx=px(18))
    tk.Frame(root, bg=RED, height=px(3)).pack(fill="x")

    body = ttk.Frame(root, padding=px(20))
    body.pack(fill="both", expand=True)
    footer = ttk.Frame(root, padding=(px(20), 0, px(20), px(16)))
    footer.pack(fill="x")

    target = tk.StringVar(value=install_info.installed_dir() or install_info.default_install_dir())
    customer = tk.StringVar(value=previous.get("customer", ""))
    want_desktop = tk.BooleanVar(value=True)
    want_reset = tk.BooleanVar(value=False)
    start_now = tk.BooleanVar(value=True)
    had_config = os.path.isfile(CONFIG) or os.path.isfile(LEGACY_CONFIG)
    state = {"exe": None, "rc": 1}
    q = queue.Queue()

    def clear():
        for w in body.winfo_children() + footer.winfo_children():
            w.destroy()

    def chrome():
        root.title(tr("in_window", name=install_info.DISPLAY_NAME))
        subtitle["text"] = f"{APP_NAME} {APP_VERSION}\n{tr('monitoring')}"

    def page_welcome():
        clear()
        chrome()
        top = ttk.Frame(body)
        top.pack(fill="x")
        ttk.Label(top, text=tr("in_welcome"), style="Title.TLabel").pack(side="left")
        lang = ttk.Combobox(top, state="readonly", width=10, values=[label for _, label in i18n.LANGUAGES])
        lang.current([c for c, _ in i18n.LANGUAGES].index(i18n.language()))

        def change_lang(_):
            i18n.set_language(i18n.LANGUAGES[lang.current()][0])
            page_welcome()
        lang.bind("<<ComboboxSelected>>", change_lang)
        lang.pack(side="right")
        ttk.Label(top, text=tr("language") + "  ", style="Body.TLabel").pack(side="right")

        upgrade = install_info.installed_dir() or install_info.legacy_installed_dir()
        txt = tr("in_upgrade") if upgrade else tr("in_new")
        ttk.Label(body, text=txt, style="Body.TLabel", wraplength=px(530)).pack(anchor="w", pady=(px(6), px(12)))
        ttk.Label(body, text=tr("in_folder"), style="Body.TLabel").pack(anchor="w")
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(px(2), px(10)))
        ttk.Entry(row, textvariable=target).pack(side="left", fill="x", expand=True)

        def browse():
            d = filedialog.askdirectory(initialdir=os.path.dirname(target.get()), title=tr("in_choose_folder"))
            if d:
                d = os.path.normpath(d)
                target.set(d if os.path.basename(d).lower() == APP_ID.lower() else os.path.join(d, APP_ID))
        ttk.Button(row, text=tr("in_browse"), command=browse).pack(side="left", padx=(px(6), 0))
        ttk.Label(body, text=tr("in_customer"), style="Body.TLabel").pack(anchor="w")
        ttk.Entry(body, textvariable=customer).pack(fill="x", pady=(px(2), px(10)))
        ttk.Checkbutton(body, text=tr("in_desktop"), variable=want_desktop).pack(anchor="w")
        if had_config:
            ttk.Checkbutton(body, text=tr("in_reset"), variable=want_reset).pack(anchor="w", pady=(px(4), 0))
        ttk.Label(body, text=tr("in_noadmin"), style="Small.TLabel").pack(anchor="w", side="bottom")
        ttk.Button(footer, text=tr("cancel"), command=root.destroy).pack(side="right")
        ttk.Button(footer, text=tr("in_install"), command=start).pack(side="right", padx=(0, px(8)))

    def start():
        if not target.get().strip():
            messagebox.showerror(tr("in_failed"), tr("in_need_folder"))
            return
        clear()
        ttk.Label(body, text=tr("in_installing"), style="Title.TLabel").pack(anchor="w")
        bar = ttk.Progressbar(body, maximum=1000, length=px(530))
        bar.pack(fill="x", pady=(px(18), px(6)))
        status = ttk.Label(body, text="", style="Body.TLabel")
        status.pack(anchor="w")
        body.bar, body.status = bar, status

        def work():
            try:
                exe = install(target.get().strip(), want_desktop.get(), customer.get(),
                              lambda f, t: q.put(("p", f, t)), reset=want_reset.get())
                q.put(("ok", exe))
            except Exception as e:  # noqa: BLE001
                log(traceback.format_exc())
                q.put(("err", str(e)))

        threading.Thread(target=work, daemon=True).start()
        root.after(50, poll)

    def poll():
        try:
            while True:
                msg = q.get_nowait()
                if msg[0] == "p":
                    body.bar["value"] = int(msg[1] * 1000)
                    body.status["text"] = msg[2]
                elif msg[0] == "ok":
                    state["exe"], state["rc"] = msg[1], 0
                    page_done()
                    return
                else:
                    messagebox.showerror(tr("in_failed"), msg[1])
                    page_welcome()
                    return
        except queue.Empty:
            pass
        root.after(50, poll)

    def page_done():
        clear()
        ttk.Label(body, text=tr("in_done"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text=tr("in_where_desk") if want_desktop.get() else tr("in_where"),
                  style="Body.TLabel").pack(anchor="w", pady=(px(4), px(14)))
        ttk.Checkbutton(body, text=tr("in_start"), variable=start_now).pack(anchor="w")

        def finish():
            if start_now.get() and state["exe"]:
                subprocess.Popen([state["exe"]], cwd=os.path.dirname(state["exe"]), close_fds=True)
            root.destroy()
        ttk.Button(footer, text=tr("in_finish"), command=finish).pack(side="right")

    page_welcome()
    root.mainloop()
    return state["rc"]


def main():
    argv = sys.argv[1:]
    if "--silent" in argv or "/S" in argv:
        sys.exit(silent(argv))
    sys.exit(gui())


if __name__ == "__main__":
    main()
