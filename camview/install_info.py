"""Shared by installer and uninstaller: paths, shortcuts and the Windows app list.

The installation is per user (no administrator): the program lives in
%LOCALAPPDATA%\\Programs\\AgesenCamView and is listed in "Installed apps" under
HKEY_CURRENT_USER. The settings in %APPDATA%\\AgesenCamView are not touched.
"""

import os
import shutil
import subprocess
import winreg

APP_ID = "AgesenCamView"
DISPLAY_NAME = "Agesen CamView"
PUBLISHER = "Agesen EL-Teknik"
URL = "https://www.agesen.dk"
EXE_NAME = "AgesenCamView.exe"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"

# Testing only: shortcuts in a test folder and a separate key in the app list.
TEST_DIR = os.environ.get("CAMVIEW_INSTALL_TEST", "")
if TEST_DIR:
    UNINSTALL_KEY += "Test"

# Before the first public release the program was called HikViewer. The
# installer removes such an installation and moves its settings over.
LEGACY_ID = "HikViewer"
LEGACY_EXE = "HikViewer.exe"
LEGACY_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{LEGACY_ID}" + ("Test" if TEST_DIR else "")


def default_install_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    return os.path.join(base, "Programs", APP_ID)


def start_menu_shortcut() -> str:
    if TEST_DIR:
        return os.path.join(TEST_DIR, "startmenu", DISPLAY_NAME + ".lnk")
    return os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs", DISPLAY_NAME + ".lnk")


def desktop_shortcut() -> str:
    if TEST_DIR:
        return os.path.join(TEST_DIR, "desktop", DISPLAY_NAME + ".lnk")
    # The desktop may have been moved (OneDrive); ask Windows where it is.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            desk = os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0])
    except OSError:
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
    return os.path.join(desk, DISPLAY_NAME + ".lnk")


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create_shortcut(lnk: str, target: str, workdir: str, description: str = DISPLAY_NAME) -> bool:
    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    script = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(lnk)});"
              f"$s.TargetPath={_ps_quote(target)};$s.WorkingDirectory={_ps_quote(workdir)};"
              f"$s.IconLocation={_ps_quote(target + ',0')};$s.Description={_ps_quote(description)};$s.Save()")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode == 0 and os.path.exists(lnk)


def dir_size_kb(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total // 1024


def register(install_dir: str, version: str, key: str = UNINSTALL_KEY):
    exe = os.path.join(install_dir, EXE_NAME)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
        values = {
            "DisplayName": DISPLAY_NAME,
            "DisplayVersion": version,
            "Publisher": PUBLISHER,
            "URLInfoAbout": URL,
            "InstallLocation": install_dir,
            "DisplayIcon": exe + ",0",
            "UninstallString": f'"{exe}" --uninstall',
            "QuietUninstallString": f'"{exe}" --uninstall --silent',
        }
        for name, val in values.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, dir_size_kb(install_dir))


def unregister(key: str = UNINSTALL_KEY):
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
    except OSError:
        pass


def installed_dir(key: str = UNINSTALL_KEY):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "InstallLocation")[0]
    except OSError:
        return None


def is_running(exe: str = EXE_NAME) -> bool:
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"], capture_output=True,
                       text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return exe.lower() in r.stdout.lower()


def legacy_installed_dir():
    return installed_dir(LEGACY_KEY)


def remove_legacy() -> bool:
    """Remove an installation of the old HikViewer: program folder, shortcuts and app list entry."""
    folder = legacy_installed_dir()
    if folder is None:
        return False
    if os.path.isfile(os.path.join(folder, LEGACY_EXE)):
        shutil.rmtree(folder, ignore_errors=True)
    for lnk in (start_menu_shortcut(), desktop_shortcut()):
        old = os.path.join(os.path.dirname(lnk), LEGACY_ID + ".lnk")
        try:
            os.remove(old)
        except OSError:
            pass
    unregister(LEGACY_KEY)
    return True


def delete_dir_after_exit(path: str):
    """The program cannot delete its own folder while running: leave it to cmd."""
    # The command line is passed as one string: a list would make Python quote
    # the quotation marks in a way cmd does not understand. Retries for up to 20 s
    # until the program has released its files.
    cmd = (f'cmd.exe /c for /l %i in (1,1,10) do (ping -n 3 127.0.0.1 >nul '
           f'& if exist "{path}" rmdir /s /q "{path}")')
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                     close_fds=True)
