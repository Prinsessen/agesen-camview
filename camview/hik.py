"""Hikvision: ISAPI (device info, PTZ), RTSP URLs and SADP discovery on the network."""

import re
import socket
import threading
import time
import uuid
from urllib.parse import quote

import requests
from requests.auth import HTTPDigestAuth


class AuthError(Exception):
    pass


def rtsp_url(cam, high_quality: bool) -> str:
    if cam.stream == "main":
        sub = 1
    elif cam.stream == "sub":
        sub = 2
    else:
        sub = 1 if high_quality else 2
    auth = f"{quote(cam.user, safe='')}:{quote(cam.password, safe='')}@" if cam.user else ""
    return f"rtsp://{auth}{cam.host.strip()}:{cam.rtsp_port}/Streaming/Channels/{int(cam.channel)}0{sub}"


def _tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    return m.group(1).strip() if m else ""


class HikDevice:
    def __init__(self, cam):
        self.cam = cam
        self.base = f"http://{cam.host.strip()}:{cam.http_port}"
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(cam.user, cam.password)
        self.ptz_path = None

    def _get(self, path, timeout=4):
        r = self.session.get(self.base + path, timeout=timeout)
        if r.status_code == 401:
            raise AuthError("Wrong user name or password")
        return r

    def device_info(self) -> dict:
        r = self._get("/ISAPI/System/deviceInfo")
        r.raise_for_status()
        t = r.text
        return {
            "model": _tag(t, "model"),
            "name": _tag(t, "deviceName"),
            "type": _tag(t, "deviceType"),
            "firmware": _tag(t, "firmwareVersion"),
        }

    def detect_ptz(self) -> bool:
        """Find PTZ directly on the camera or through an NVR (PTZCtrlProxy)."""
        ch = int(self.cam.channel)
        for path in (f"/ISAPI/PTZCtrl/channels/{ch}", f"/ISAPI/ContentMgmt/PTZCtrlProxy/channels/{ch}"):
            try:
                r = self._get(path + "/capabilities")
            except AuthError:
                raise
            except requests.RequestException:
                continue
            if r.status_code == 200 and re.search(r"(?i)continuousPanTiltSpace|ContinuousZoomSpace", r.text):
                self.ptz_path = path
                return True
        self.ptz_path = None
        return False

    def continuous(self, pan: int, tilt: int, zoom: int) -> bool:
        if not self.ptz_path:
            return False
        body = ('<?xml version="1.0" encoding="UTF-8"?><PTZData>'
                f"<pan>{int(pan)}</pan><tilt>{int(tilt)}</tilt><zoom>{int(zoom)}</zoom></PTZData>")
        try:
            r = self.session.put(self.base + self.ptz_path + "/continuous", data=body.encode(),
                                 headers={"Content-Type": "application/xml"}, timeout=2.5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def goto_preset(self, preset: int) -> bool:
        if not self.ptz_path:
            return False
        try:
            r = self.session.put(f"{self.base}{self.ptz_path}/presets/{int(preset)}/goto", timeout=2.5)
            return r.status_code == 200
        except requests.RequestException:
            return False


class PtzController:
    """Send joystick movements to one camera at a time.

    Only the latest command is sent (at most about 8 per second), so the camera never
    gets a queue of stale commands. Stop is always sent, also after network errors.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._dev = None
        self._target = (0, 0, 0)
        self._sent = (0, 0, 0)
        self._fails = 0
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def set_device(self, dev):
        with self._lock:
            old, sent = self._dev, self._sent
            self._dev, self._target, self._sent = dev, (0, 0, 0), (0, 0, 0)
        if old is not None and old is not dev and sent != (0, 0, 0):
            threading.Thread(target=old.continuous, args=(0, 0, 0), daemon=True).start()

    def move(self, pan: int, tilt: int, zoom: int):
        with self._lock:
            self._target = (int(pan), int(tilt), int(zoom))
        self._event.set()

    def stop(self):
        self.move(0, 0, 0)

    def shutdown(self):
        with self._lock:
            dev, sent = self._dev, self._sent
            self._running = False
        self._event.set()
        if dev is not None and sent != (0, 0, 0):
            dev.continuous(0, 0, 0)

    def _loop(self):
        while True:
            self._event.wait(0.5)
            self._event.clear()
            with self._lock:
                if not self._running:
                    return
                dev, target = self._dev, self._target
            if dev is None or target == self._sent:
                continue
            ok = dev.continuous(*target)
            with self._lock:
                if self._dev is not dev:
                    continue
                if ok or self._fails >= 3:
                    self._sent, self._fails = target, 0
                else:
                    self._fails += 1
                    self._event.set()
            time.sleep(0.12)


# --- SADP: Hikvision's own discovery on the local network ----------------------

def _local_ipv4():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips = {ip for ip in ips if not ip.startswith(("127.", "169.254."))}
    return sorted(ips) or ["0.0.0.0"]


def discover(timeout: float = 3.0) -> list:
    probe = ('<?xml version="1.0" encoding="utf-8"?><Probe><Uuid>%s</Uuid>'
             '<Types>inquiry</Types></Probe>' % str(uuid.uuid4()).upper()).encode()
    found = {}
    lock = threading.Lock()

    def scan(local):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((local, 0))
            if local != "0.0.0.0":
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            s.settimeout(0.4)
            for _ in range(2):
                s.sendto(probe, ("239.255.255.250", 37020))
        except OSError:
            return
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, _ = s.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            t = data.decode("utf-8", "ignore")
            ip = _tag(t, "IPv4Address")
            if ip:
                with lock:
                    found[ip] = {
                        "ip": ip,
                        "model": _tag(t, "DeviceDescription"),
                        "http_port": int(_tag(t, "HttpPort") or 80),
                        "type": _tag(t, "DeviceType"),
                    }
        s.close()

    threads = [threading.Thread(target=scan, args=(ip,), daemon=True) for ip in _local_ipv4()]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout + 2)
    return sorted(found.values(), key=lambda d: tuple(int(x) for x in d["ip"].split(".")))


def looks_like_ptz(model: str) -> bool:
    return model.upper().startswith(("DS-2DE", "DS-2DF", "DS-2DY", "DS-2SE", "DS-2DP"))
