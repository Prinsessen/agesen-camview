"""Main window: up to 32 cameras over as many pages as needed, PTZ panel and brand bar.

Click a camera to show it alone in the whole window (main stream, PTZ panel if
the camera has PTZ); click again or press Esc to go back to the overview.
"""

import base64
import os
import sys
import threading
import time

from PySide6.QtCore import QByteArray, QLockFile, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QSizePolicy, QSlider, QToolBar, QVBoxLayout,
                               QWidget)

from . import APP_ID, APP_NAME, APP_VERSION, brand, config, hik, i18n
from .i18n import tr
from .settings import SettingsDialog
from .video import StreamWorker
from .widgets import BrandBar, Joystick, VideoTile, make_app_icon


def grid_shape(n: int) -> list:
    """Tile positions (row, column, rows, columns) for n cameras on one page.

    1: full, 2: side by side, 3: one large and two small, then 2x2, 3x2, 3x3, 4x3, 4x4.
    """
    if n <= 1:
        return [(0, 0, 1, 1)]
    if n == 2:
        return [(0, 0, 1, 1), (0, 1, 1, 1)]
    if n == 3:
        return [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)]
    cols = 2 if n <= 4 else 3 if n <= 9 else 4
    return [(i // cols, i % cols, 1, 1) for i in range(n)]


class PtzPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(236)
        self.setStyleSheet("PtzPanel{background:#1A1C22; border-left:1px solid #2A2D36;}"
                           "QLabel{color:#C9CDD8;} QPushButton{background:#2A2E38; color:#E8EAF0;"
                           "border:1px solid #3A3F4C; border-radius:6px; padding:8px; font-size:13pt;}"
                           "QPushButton:pressed{background:#3A4050;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight:600; font-size:11pt; color:#E8EAF0;")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        self.joystick = Joystick()
        lay.addWidget(self.joystick, 0, Qt.AlignmentFlag.AlignHCenter)
        zoom = QHBoxLayout()
        self.zoom_out = QPushButton()
        self.zoom_in = QPushButton()
        zoom.addWidget(self.zoom_out)
        zoom.addWidget(self.zoom_in)
        lay.addLayout(zoom)
        lay.addSpacing(6)
        self.speed_label = QLabel()
        lay.addWidget(self.speed_label)
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(10, 100)
        self.speed.valueChanged.connect(lambda v: self.speed_label.setText(tr("speed", v=v)))
        lay.addWidget(self.speed)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#7D8394; font-size:8.5pt;")
        lay.addWidget(self.hint)
        lay.addStretch(1)
        self.retranslate()

    def retranslate(self):
        self.zoom_out.setText(tr("zoom_out"))
        self.zoom_in.setText(tr("zoom_in"))
        self.speed_label.setText(tr("speed", v=self.speed.value()))
        self.hint.setText(tr("ptz_hint"))


class MainWindow(QMainWindow):
    ptzFound = Signal(object, bool)   # (device, has PTZ)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.tiles = [VideoTile(i) for i in range(max(config.PER_PAGE_CHOICES))]
        for t in self.tiles:
            t.cam = None
        self.workers = {}       # camera index -> StreamWorker
        self.devices = []       # camera index -> HikDevice
        self.ptz_known = {}     # camera index -> True/False once detected
        self.last_image = {}    # camera index -> last frame, shown while a stream (re)connects
        self.page = 0
        self.single = None      # camera index shown alone, or None for the overview
        self.retired = []
        self.ptz = hik.PtzController()
        self.joy = (0.0, 0.0)
        self.zoom_dir = 0
        self.keys = set()
        self.ptzFound.connect(self._on_ptz_found)

        icon_path = config.resource(os.path.join("assets", "icon.ico"))
        self.setWindowIcon(QIcon(icon_path) if icon_path else QIcon(make_app_icon()))
        self._build()
        self.apply_config()
        if cfg.geometry:
            self.restoreGeometry(QByteArray(base64.b64decode(cfg.geometry)))
        else:
            self.resize(1280, 800)
        if not cfg.cameras:
            QTimer.singleShot(300, self.open_settings)

    # --- Layout ----------------------------------------------------------------------

    def _build(self):
        tb = QToolBar("View")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        self.back_action = QAction("", self)
        self.back_action.triggered.connect(self.show_overview)
        tb.addAction(self.back_action)
        self.prev_action = QAction("◀", self)
        self.prev_action.triggered.connect(lambda: self.turn_page(-1))
        tb.addAction(self.prev_action)
        self.page_label = QLabel()
        self.page_label_action = tb.addWidget(self.page_label)
        self.next_action = QAction("▶", self)
        self.next_action.triggered.connect(lambda: self.turn_page(1))
        tb.addAction(self.next_action)
        self.ptz_action = QAction("", self, checkable=True, checked=True)
        self.ptz_action.triggered.connect(lambda _: self._update_ptz_panel())
        tb.addAction(self.ptz_action)
        self.full_action = QAction("", self)
        self.full_action.setShortcut(QKeySequence("F11"))
        self.full_action.triggered.connect(self.toggle_fullscreen)
        tb.addAction(self.full_action)
        for k in range(2):
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            tb.addWidget(spacer)
            if k == 0:
                self.customer = QLabel()
                self.customer.setStyleSheet("color:#F0F2F7; font-size:13pt; font-weight:600; padding:0 16px;")
                tb.addWidget(self.customer)
        self.settings_action = QAction("", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.triggered.connect(lambda: self.open_settings())
        tb.addAction(self.settings_action)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(2, 2, 2, 2)
        self.grid.setSpacing(2)
        for t in self.tiles:
            t.clicked.connect(self._tile_clicked)
            t.resized.connect(self._tile_resized)
        body.addWidget(self.grid_host, 1)
        self.panel = PtzPanel()
        self.panel.speed.setValue(self.cfg.ptz_speed)
        self.panel.speed.valueChanged.connect(self._speed_changed)
        self.panel.joystick.moved.connect(self._joystick)
        self.panel.zoom_in.pressed.connect(lambda: self._zoom(1))
        self.panel.zoom_out.pressed.connect(lambda: self._zoom(-1))
        self.panel.zoom_in.released.connect(lambda: self._zoom(0))
        self.panel.zoom_out.released.connect(lambda: self._zoom(0))
        body.addWidget(self.panel)
        outer.addLayout(body, 1)
        self.brand = BrandBar()
        outer.addWidget(self.brand)
        self.setCentralWidget(central)
        self.retranslate()

    def retranslate(self):
        self.back_action.setText("←  " + tr("overview"))
        self.back_action.setToolTip(tr("click_back"))
        self.prev_action.setToolTip(tr("prev_page"))
        self.next_action.setToolTip(tr("next_page"))
        self.ptz_action.setText(tr("ptz_panel"))
        self.full_action.setText(tr("fullscreen"))
        self.settings_action.setText(tr("settings"))
        self.panel.retranslate()

    # --- Setup --------------------------------------------------------------------------

    def apply_config(self):
        cust = self.cfg.customer.strip()
        self.customer.setText(cust)
        self.customer.setVisible(bool(cust))
        self.setWindowTitle(" - ".join(x for x in (cust, tr("monitoring"), brand.COMPANY) if x))
        accent = QColor(brand.ACCENT)
        self.panel.joystick.accent = accent
        apply_accent(QApplication.instance(), accent)
        for t in self.tiles:
            t.accent = accent
        self.ptz.set_device(None)
        for i in list(self.workers):
            self._stop_worker(i)
        self.devices = [hik.HikDevice(c) for c in self.cfg.cameras]
        self.ptz_known.clear()
        self.last_image.clear()
        for t in self.tiles:
            t.cam = None
        if self.single is not None and self.single >= len(self.cfg.cameras):
            self.single = None
        self.page = min(self.page, self.pages() - 1)
        self._relayout()

    def pages(self) -> int:
        per = self.cfg.per_page
        return max(1, (len(self.cfg.cameras) + per - 1) // per)

    def visible(self) -> list:
        if self.single is not None:
            return [self.single]
        per = self.cfg.per_page
        start = self.page * per
        return list(range(start, min(len(self.cfg.cameras), start + per)))

    def _relayout(self):
        while self.grid.count():
            self.grid.takeAt(0)
        for t in self.tiles:
            t.hide()
        cams = self.visible()
        if not cams:
            t = self.tiles[0]
            t.cam = None
            t.title, t.ptz = "", False
            t.clear(tr("no_cameras"))
            t.setToolTip("")
            self.grid.addWidget(t, 0, 0)
            t.show()
            positions = [(0, 0, 1, 1)]
        else:
            positions = grid_shape(len(cams))
            for tile, i, (r, c, rs, cs) in zip(self.tiles, cams, positions):
                if tile.cam != i:
                    tile.cam = i
                    img = self.last_image.get(i)
                    if img is not None:
                        tile.set_image(img)
                    else:
                        tile.clear(tr("connecting"))
                tile.title = self.cfg.cameras[i].label(i)
                tile.ptz = self.ptz_known.get(i, False)
                tile.setToolTip(tr("click_back") if self.single is not None else tr("click_full"))
                self.grid.addWidget(tile, r, c, rs, cs)
                tile.show()
                tile.update()
        rows = max(r + rs for r, c, rs, cs in positions)
        cols = max(c + cs for r, c, rs, cs in positions)
        for k in range(4):
            self.grid.setRowStretch(k, 1 if k < rows else 0)
            self.grid.setColumnStretch(k, 1 if k < cols else 0)

        high = len(cams) == 1
        for i in list(self.workers):
            if i not in cams:
                self._stop_worker(i)
        for i in cams:
            self._ensure_worker(i, hik.rtsp_url(self.cfg.cameras[i], high))
            if i not in self.ptz_known:
                self.ptz_known[i] = False
                threading.Thread(target=self._detect_ptz, args=(self.devices[i],), daemon=True).start()
        self._update_toolbar()
        self._update_ptz_panel()

    def _update_toolbar(self):
        overview = self.single is None
        paged = overview and self.pages() > 1
        self.back_action.setVisible(not overview)
        for a in (self.prev_action, self.page_label_action, self.next_action):
            a.setVisible(paged)
        self.page_label.setText("  " + tr("page", n=self.page + 1, total=self.pages()) + "  ")
        self.prev_action.setEnabled(self.page > 0)
        self.next_action.setEnabled(self.page < self.pages() - 1)
        self.ptz_action.setVisible(not overview and self.ptz_known.get(self.single, False))

    def _detect_ptz(self, dev):
        try:
            ok = dev.detect_ptz()
        except Exception:  # noqa: BLE001 - without a PTZ answer the camera is just shown without joystick
            ok = False
        self.ptzFound.emit(dev, ok)

    def _on_ptz_found(self, dev, ok):
        if dev not in self.devices:
            return
        i = self.devices.index(dev)
        self.ptz_known[i] = ok
        for t in self.tiles:
            if t.cam == i:
                t.ptz = ok
                t.update()
        self._update_toolbar()
        self._update_ptz_panel()

    # --- Video ------------------------------------------------------------------------------

    def _tile_for(self, i):
        for t in self.tiles:
            if t.cam == i and not t.isHidden():
                return t
        return None

    def _ensure_worker(self, i, url):
        w = self.workers.get(i)
        if w is not None and w.url == url and w.isRunning():
            return
        self._stop_worker(i)
        w = StreamWorker(url)
        t = self._tile_for(i)
        if t is not None:
            w.set_target(t.width(), t.height())
        w.frame.connect(self._on_frame)
        w.status.connect(self._on_status)
        w.finished.connect(self._reap)
        self.workers[i] = w
        w.start()

    def _stop_worker(self, i):
        w = self.workers.pop(i, None)
        if w is None:
            return
        w.stop()
        self.retired.append(w)

    def _reap(self):
        self.retired = [w for w in self.retired if w.isRunning()]

    def _index_of(self, worker):
        for i, w in self.workers.items():
            if w is worker:
                return i
        return None

    def _on_frame(self, worker, img):
        i = self._index_of(worker)
        if i is None:
            return
        self.last_image[i] = img
        t = self._tile_for(i)
        if t is not None:
            t.set_image(img)

    def _on_status(self, worker, text):
        i = self._index_of(worker)
        t = self._tile_for(i) if i is not None else None
        if t is not None:
            t.set_status(text)

    def _tile_resized(self, pos, w, h):
        cam = self.tiles[pos].cam
        wk = self.workers.get(cam) if cam is not None else None
        if wk is not None:
            wk.set_target(w, h)

    # --- Actions ----------------------------------------------------------------------------

    def _tile_clicked(self, pos):
        cam = self.tiles[pos].cam
        if cam is None:
            self.open_settings()
        elif self.single is None:
            self.single = cam
            self._relayout()
        else:
            self.show_overview()

    def show_overview(self):
        if self.single is not None:
            self.page = self.single // self.cfg.per_page
            self.single = None
            self._relayout()

    def turn_page(self, d):
        if self.single is not None:
            return
        page = min(max(0, self.page + d), self.pages() - 1)
        if page != self.page:
            self.page = page
            self._relayout()

    def _update_ptz_panel(self):
        i = self.single
        show = (i is not None and self.ptz_action.isChecked() and self.ptz_known.get(i, False))
        self.panel.setVisible(bool(show))
        if i is not None:
            self.panel.title.setText(tr("ptz_title", name=self.cfg.cameras[i].label(i)))
        if self.panel.joystick.dragging:
            self.panel.joystick.release()
        self.joy, self.zoom_dir = (0.0, 0.0), 0
        self.ptz.set_device(self.devices[i] if show else None)

    def _speed_changed(self, v):
        self.cfg.ptz_speed = v
        self._send_ptz()

    def _joystick(self, x, y):
        self.joy = (x, y)
        self._send_ptz()

    def _zoom(self, d):
        self.zoom_dir = d
        self._send_ptz()

    def _send_ptz(self):
        s = self.panel.speed.value()
        x, y = self.joy
        self.ptz.move(round(x * s), round(y * s), self.zoom_dir * s)

    PTZ_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Plus, Qt.Key.Key_Minus)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            if self.single is not None:
                self.show_overview()
            elif self.isFullScreen():
                self.showNormal()
            return
        if k == Qt.Key.Key_PageDown or (self.single is None and k == Qt.Key.Key_Right):
            self.turn_page(1)
            return
        if k == Qt.Key.Key_PageUp or (self.single is None and k == Qt.Key.Key_Left):
            self.turn_page(-1)
            return
        if self.panel.isVisible() and not e.isAutoRepeat() and k in self.PTZ_KEYS:
            self.keys.add(k)
            self._keys_to_ptz()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() in self.keys and not e.isAutoRepeat():
            self.keys.discard(e.key())
            self._keys_to_ptz()
            return
        super().keyReleaseEvent(e)

    def _keys_to_ptz(self):
        K = Qt.Key
        x = (K.Key_Right in self.keys) - (K.Key_Left in self.keys)
        y = (K.Key_Up in self.keys) - (K.Key_Down in self.keys)
        self.joy = (float(x), float(y))
        self.zoom_dir = (K.Key_Plus in self.keys) - (K.Key_Minus in self.keys)
        self._send_ptz()

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def open_settings(self, select=None):
        if select is None:
            select = self.single if self.single is not None else self.page * self.cfg.per_page
        dlg = SettingsDialog(self.cfg, select, self)
        if dlg.exec():
            dlg.apply_to(self.cfg)
            self._save()
            i18n.set_language(self.cfg.language)
            self.retranslate()
            self.single = None
            self.apply_config()

    def _save(self):
        self.cfg.geometry = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
        try:
            config.save(self.cfg)
        except OSError:
            pass

    def closeEvent(self, e):
        self._save()
        self.hide()
        self.ptz.shutdown()
        for i in list(self.workers):
            self._stop_worker(i)
        deadline = time.monotonic() + 7.0
        for w in self.retired:
            w.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        if any(w.isRunning() for w in self.retired):
            # A thread is stuck in a connection attempt; everything is saved, so exit hard.
            os._exit(0)
        super().closeEvent(e)


def dark_palette(app):
    app.setStyle("Fusion")
    pal = QPalette()
    base, text = QColor(30, 32, 38), QColor(225, 228, 235)
    pal.setColor(QPalette.ColorRole.Window, base)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, QColor(22, 24, 29))
    pal.setColor(QPalette.ColorRole.AlternateBase, base)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, QColor(40, 43, 51))
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Highlight, QColor(brand.ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.ToolTipBase, base)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 124, 135))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(120, 124, 135))
    app.setPalette(pal)
    apply_accent(app, QColor(brand.ACCENT))


def apply_accent(app, accent: QColor):
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    app.setPalette(pal)
    app.setStyleSheet(
        "QToolBar{background:#1A1C22; border:0; border-bottom:1px solid #2A2D36; padding:4px; spacing:4px;}"
        "QToolBar QLabel{color:#9AA0AF;}"
        "QToolButton{padding:5px 12px; border-radius:5px; color:#D8DBE3;}"
        "QToolButton:hover{background:#2A2E38;}"
        f"QToolButton:checked{{background:{accent.name()}; color:white;}}")


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ID}.{APP_VERSION}")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    dark_palette(app)
    cfg = config.load()
    i18n.set_language(cfg.language)
    # Only one window at a time: two windows would overwrite each other's settings.
    os.makedirs(config.APP_DIR, exist_ok=True)
    lock = QLockFile(os.path.join(config.APP_DIR, "instance.lock"))
    lock.setStaleLockTime(0)
    locked = lock.tryLock(100)
    if "--uninstall" in sys.argv:
        if not locked:
            if "--silent" not in sys.argv:
                QMessageBox.warning(None, APP_NAME, tr("close_before_uninstall"))
            sys.exit(2)
        from . import uninstall
        rc = uninstall.run(sys.argv)
        lock.unlock()
        sys.exit(rc)
    if not locked:
        QMessageBox.information(None, APP_NAME, tr("already_running"))
        sys.exit(0)
    win = MainWindow(cfg)
    win.show()
    # Automated testing only: close after N ms and save a screenshot
    shot = os.environ.get("CAMVIEW_SCREENSHOT")
    if shot:
        def grab():
            win.grab().save(shot)
            win.close()
        QTimer.singleShot(int(os.environ.get("CAMVIEW_SCREENSHOT_MS", "2500")), grab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
