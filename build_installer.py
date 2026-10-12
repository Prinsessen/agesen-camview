"""Builds the program and the installer: dist\\AgesenCamView-Setup-<version>.exe

Run:      python build_installer.py
Requires: pip install pyside6 av requests pyinstaller pillow
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from camview import APP_ID, APP_VERSION  # noqa: E402

BUILD = ROOT / "build" / "installer"
APP = ROOT / "dist" / APP_ID


def run(cmd):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    # 1. The program itself (the dist\AgesenCamView folder)
    run(["cmd", "/c", str(ROOT / "build.bat")])
    if not (APP / f"{APP_ID}.exe").exists():
        sys.exit(f"{APP / APP_ID}.exe is missing")

    # 2. The package the installer unpacks
    BUILD.mkdir(parents=True, exist_ok=True)
    payload = BUILD / "payload.zip"
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(APP.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(APP).as_posix())
    print(f"payload.zip: {payload.stat().st_size / 1e6:.0f} MB")

    # 3. Logo for the installer's white header (black text)
    logo = Image.open(ROOT / "assets" / "logo-dark.png")
    logo.thumbnail((1200, 240), Image.LANCZOS)
    bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    bg.alpha_composite(logo)
    bg.convert("RGB").save(BUILD / "installer_logo.png")

    # 4. The installer as a single .exe
    name = f"{APP_ID}-Setup-{APP_VERSION}"
    sep = os.pathsep
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
         "--name", name, "--icon", str(ROOT / "assets" / "icon.ico"),
         "--paths", str(ROOT),
         "--add-data", f"{payload}{sep}.",
         "--add-data", f"{BUILD / 'installer_logo.png'}{sep}.",
         "--add-data", f"{ROOT / 'assets' / 'icon.ico'}{sep}.",
         "--workpath", str(BUILD / "work"), "--specpath", str(BUILD),
         "--distpath", str(ROOT / "dist"),
         str(ROOT / "installer" / "setup.py")])
    out = ROOT / "dist" / f"{name}.exe"
    print(f"\nDone: {out}  ({out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
