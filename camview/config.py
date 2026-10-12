r"""Settings: stored in %APPDATA%\AgesenCamView\config.json.

Passwords are encrypted with Windows DPAPI, so they can only be read by the same
Windows user on the same PC. The file therefore cannot be copied to another PC
with the passwords intact.
"""

import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
from dataclasses import asdict, dataclass, field

APP_DIR = os.environ.get("CAMVIEW_CONFIG_DIR") or os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "AgesenCamView")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
MAX_CAMERAS = 32
PER_PAGE_CHOICES = (4, 6, 9, 16)


# --- DPAPI -----------------------------------------------------------------

class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(data: bytes, protect: bool) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    crypt32 = ctypes.windll.crypt32
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(inp), "AgesenCamView", None, None, None, 0x1, ctypes.byref(out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect(text: str) -> str:
    if not text:
        return ""
    return base64.b64encode(_crypt(text.encode("utf-8"), True)).decode("ascii")


def unprotect(blob: str) -> str:
    if not blob:
        return ""
    try:
        return _crypt(base64.b64decode(blob), False).decode("utf-8")
    except Exception:
        return ""   # different user/PC: the password must be entered again


# --- Data --------------------------------------------------------------------

@dataclass
class Camera:
    name: str = ""
    host: str = ""
    http_port: int = 80
    rtsp_port: int = 554
    user: str = "admin"
    password: str = ""      # in memory only; on disk as password_enc
    channel: int = 1        # 1 for a camera, channel number for an NVR
    stream: str = "auto"    # auto = main when alone, sub in grid

    @property
    def configured(self) -> bool:
        return bool(self.host.strip())

    def label(self, index: int) -> str:
        from .i18n import tr
        return self.name.strip() or tr("camera_n", n=index + 1)


@dataclass
class Config:
    per_page: int = 4       # cameras per page in the overview
    ptz_speed: int = 50
    customer: str = ""      # customer name, shown at the top
    language: str = ""      # "da", "en" or empty = Windows language
    cameras: list = field(default_factory=list)   # only cameras that are set up, in display order
    geometry: str = ""


def resource(name: str) -> str:
    """File shipped with the program (icon)."""
    import sys
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(base, name)
    return p if os.path.exists(p) else ""


def load() -> Config:
    cfg = Config()
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return cfg
    per_page = int(data.get("per_page", 4))
    cfg.per_page = per_page if per_page in PER_PAGE_CHOICES else 4
    cfg.ptz_speed = int(data.get("ptz_speed", 50))
    cfg.customer = str(data.get("customer", ""))
    cfg.language = str(data.get("language", ""))
    cfg.geometry = data.get("geometry", "")
    cams = []
    for c in data.get("cameras", []):
        cam = Camera(**{k: v for k, v in c.items() if k in Camera.__dataclass_fields__ and k != "password"})
        cam.password = unprotect(c.get("password_enc", ""))
        if cam.configured:          # older versions saved empty slots too
            cams.append(cam)
    cfg.cameras = cams[:MAX_CAMERAS]
    return cfg


def save(cfg: Config) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    cams = []
    for cam in cfg.cameras:
        d = asdict(cam)
        d.pop("password")
        d["password_enc"] = protect(cam.password)
        cams.append(d)
    data = {
        "per_page": cfg.per_page,
        "ptz_speed": cfg.ptz_speed,
        "customer": cfg.customer,
        "language": cfg.language,
        "geometry": cfg.geometry,
        "cameras": cams,
    }
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)
