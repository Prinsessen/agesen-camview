"""RTSP playback in a background thread with FFmpeg (PyAV)."""

import time

import av
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from .i18n import tr

OPTIONS = {
    "rtsp_transport": "tcp",
    "fflags": "nobuffer",
    "flags": "low_delay",
    "max_delay": "300000",
    "timeout": "6000000",      # microseconds: abort if the network stalls
}


def classify(err: Exception) -> str:
    s = str(err)
    low = s.lower()
    if "401" in s or "unauthorized" in low or "authoriz" in low:
        return "err_auth"
    if "404" in s or "not found" in low:
        return "err_channel"
    return "err_conn"


class StreamWorker(QThread):
    frame = Signal(object, QImage)
    status = Signal(object, str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._stop = False
        self._target = (640, 360)
        self.max_fps = 25

    def set_target(self, w: int, h: int):
        self._target = (max(64, int(w)), max(36, int(h)))

    def stop(self):
        self._stop = True

    def _sleep(self, seconds):
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(0.1)

    def run(self):
        backoff = 1.0
        first = True
        while not self._stop:
            if first:
                # On retries the error text stays visible, so there is time to read it.
                self.status.emit(self, tr("connecting"))
                first = False
            container = None
            try:
                container = av.open(self.url, options=OPTIONS, timeout=(5.0, 6.0))
                stream = container.streams.video[0]
                stream.thread_type = "AUTO"
                last = 0.0
                for packet in container.demux(stream):
                    if self._stop:
                        break
                    for fr in packet.decode():
                        now = time.monotonic()
                        if now - last < 1.0 / self.max_fps:
                            continue
                        last = now
                        tw, th = self._target
                        scale = min(tw / fr.width, th / fr.height, 1.0)
                        w = max(2, int(fr.width * scale) // 2 * 2)
                        h = max(2, int(fr.height * scale) // 2 * 2)
                        rgb = fr.reformat(width=w, height=h, format="rgb24")
                        plane = rgb.planes[0]
                        img = QImage(bytes(plane), w, h, plane.line_size, QImage.Format.Format_RGB888).copy()
                        self.frame.emit(self, img)
                        backoff = 1.0
                if not self._stop:
                    self.status.emit(self, tr("stream_lost"))
            except Exception as e:  # noqa: BLE001 - any FFmpeg error just triggers a retry
                if self._stop:
                    break
                kind = classify(e)
                if kind == "err_auth":
                    # No retry: Hikvision locks out the IP address after a few
                    # failed logins. The user fixes it under Settings.
                    self.status.emit(self, tr("err_auth") + "\n" + tr("err_auth_fix"))
                    return
                self.status.emit(self, tr(kind) + " - " + tr("retrying"))
            finally:
                if container is not None:
                    try:
                        container.close()
                    except Exception:
                        pass
            self._sleep(backoff)
            backoff = min(backoff * 2, 15.0)
