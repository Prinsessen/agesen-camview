"""Settings: customer name, language, cameras per page and the list of up to 32 cameras.

The brand bar at the bottom is fixed in the program and cannot be changed here.
"""

import copy
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from . import hik
from .config import MAX_CAMERAS, PER_PAGE_CHOICES, Camera
from .i18n import LANGUAGES, language, tr

STREAMS = ["auto", "main", "sub"]


class _Relay(QObject):
    done = Signal(object, object)   # (result, error text)


def run_bg(fn, callback):
    """Run fn in a thread and call callback(result, error) in the GUI thread."""
    relay = _Relay()
    relay.done.connect(callback)

    def work():
        try:
            relay.done.emit(fn(), None)
        except hik.AuthError:
            relay.done.emit(None, tr("err_auth"))
        except Exception as e:  # noqa: BLE001
            relay.done.emit(None, tr("no_conn_detail", e=e.__class__.__name__))

    threading.Thread(target=work, daemon=True).start()
    return relay


def _buttons(ok_key):
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr(ok_key))
    bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
    return bb


class DiscoverDialog(QDialog):
    """Finds Hikvision devices on the network; one or more can be selected."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("discover_title"))
        self.resize(480, 380)
        self.result_devices = []
        lay = QVBoxLayout(self)
        self.info = QLabel(tr("discover_searching"))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        mono = self.list.font()
        mono.setFamily("Consolas")
        self.list.setFont(mono)
        self.list.itemDoubleClicked.connect(lambda *_: self.accept())
        lay.addWidget(self.info)
        lay.addWidget(self.list, 1)
        bb = _buttons("add_selected")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._relay = run_bg(hik.discover, self._found)

    def _found(self, devices, err):
        if err or not devices:
            self.info.setText(tr("discover_none"))
            return
        self.info.setText(tr("discover_found", n=len(devices)))
        for d in devices:
            kind = "  PTZ" if hik.looks_like_ptz(d["model"]) else ""
            it = QListWidgetItem(f"{d['ip']:<16} {d['model']}{kind}")
            it.setData(Qt.ItemDataRole.UserRole, d)
            self.list.addItem(it)

    def accept(self):
        self.result_devices = [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()]
        super().accept()


class CameraForm(QWidget):
    """Edits one camera. changed() is emitted when the name, IP or channel changes."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(12, 0, 0, 0)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.name = QLineEdit()
        self.host = QLineEdit()
        self.host.setPlaceholderText(tr("ip_ph"))
        self.http = QSpinBox()
        self.http.setRange(1, 65535)
        self.rtsp = QSpinBox()
        self.rtsp.setRange(1, 65535)
        ports = QHBoxLayout()
        ports.addWidget(QLabel("HTTP"))
        ports.addWidget(self.http)
        ports.addSpacing(12)
        ports.addWidget(QLabel("RTSP"))
        ports.addWidget(self.rtsp)
        ports.addStretch(1)
        self.user = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        show = QPushButton(tr("show"))
        show.setCheckable(True)
        show.toggled.connect(lambda on: self.password.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        pwrow = QHBoxLayout()
        pwrow.addWidget(self.password, 1)
        pwrow.addWidget(show)
        self.channel = QSpinBox()
        self.channel.setRange(1, 64)
        self.channel.setToolTip(tr("channel_tip"))
        self.stream = QComboBox()
        for key in STREAMS:
            self.stream.addItem(tr("stream_" + key), key)
        test = QPushButton(tr("test"))
        test.clicked.connect(self._test)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        testrow = QHBoxLayout()
        testrow.addWidget(test)
        testrow.addWidget(self.result, 1)

        form.addRow(tr("name"), self.name)
        form.addRow(tr("ip"), self.host)
        form.addRow(tr("ports"), ports)
        form.addRow(tr("user"), self.user)
        form.addRow(tr("password"), pwrow)
        form.addRow(tr("channel"), self.channel)
        form.addRow(tr("quality"), self.stream)
        form.addRow("", testrow)
        self.index = 0
        self._relay = None
        for w in (self.name, self.host):
            w.textChanged.connect(self.changed)
        self.channel.valueChanged.connect(self.changed)

    def load(self, cam: Camera, index: int):
        self.blockSignals(True)
        self.index = index
        self.name.setPlaceholderText(tr("camera_n", n=index + 1))
        self.name.setText(cam.name)
        self.host.setText(cam.host)
        self.http.setValue(cam.http_port)
        self.rtsp.setValue(cam.rtsp_port)
        self.user.setText(cam.user)
        self.password.setText(cam.password)
        self.channel.setValue(cam.channel)
        self.stream.setCurrentIndex(STREAMS.index(cam.stream) if cam.stream in STREAMS else 0)
        self.result.clear()
        self.blockSignals(False)

    def camera(self) -> Camera:
        return Camera(name=self.name.text().strip(), host=self.host.text().strip(),
                      http_port=self.http.value(), rtsp_port=self.rtsp.value(),
                      user=self.user.text().strip(), password=self.password.text(),
                      channel=self.channel.value(), stream=self.stream.currentData())

    def _test(self):
        cam = self.camera()
        if not cam.configured:
            self.result.setText(tr("enter_ip_first"))
            return
        self.result.setStyleSheet("")
        self.result.setText(tr("testing"))

        def work():
            dev = hik.HikDevice(cam)
            info = dev.device_info()
            info["ptz"] = dev.detect_ptz()
            return info

        self._relay = run_bg(work, self._tested)

    def _tested(self, info, err):
        if err:
            self.result.setStyleSheet("color:#E5534B;")
            self.result.setText(err)
            return
        self.result.setStyleSheet("color:#3FB950;")
        self.result.setText(tr("test_ok", model=info["model"], ptz=tr("yes") if info["ptz"] else tr("no")))
        if not self.name.text().strip() and info.get("name"):
            self.name.setText(info["name"])


class SettingsDialog(QDialog):
    def __init__(self, cfg, select: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings"))
        self.resize(820, 540)
        self.cams = [copy.copy(c) for c in cfg.cameras]
        self.cur = None
        lay = QVBoxLayout(self)

        top = QFormLayout()
        self.customer = QLineEdit(cfg.customer)
        self.customer.setPlaceholderText(tr("customer_ph"))
        top.addRow(tr("customer"), self.customer)
        self.language = QComboBox()
        for code, label in LANGUAGES:
            self.language.addItem(label, code)
        self.language.setCurrentIndex([c for c, _ in LANGUAGES].index(language()))
        self.per_page = QComboBox()
        for n in PER_PAGE_CHOICES:
            self.per_page.addItem(str(n), n)
        self.per_page.setCurrentIndex(PER_PAGE_CHOICES.index(cfg.per_page))
        row = QHBoxLayout()
        row.addWidget(self.language)
        row.addSpacing(24)
        row.addWidget(QLabel(tr("per_page")))
        row.addWidget(self.per_page)
        row.addStretch(1)
        top.addRow(tr("language"), row)
        lay.addLayout(top)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.count = QLabel()
        left.addWidget(self.count)
        self.list = QListWidget()
        self.list.setMinimumWidth(270)
        self.list.currentRowChanged.connect(self._select)
        left.addWidget(self.list, 1)
        btns = QGridLayout()
        b_add = QPushButton(tr("add_camera"))
        b_add.clicked.connect(self._add)
        b_dup = QPushButton(tr("duplicate"))
        b_dup.setToolTip(tr("duplicate_tip"))
        b_dup.clicked.connect(self._duplicate)
        b_find = QPushButton(tr("search_net"))
        b_find.clicked.connect(self._discover)
        b_del = QPushButton(tr("remove_camera"))
        b_del.clicked.connect(self._remove)
        b_up = QPushButton(tr("move_up"))
        b_up.clicked.connect(lambda: self._move(-1))
        b_down = QPushButton(tr("move_down"))
        b_down.clicked.connect(lambda: self._move(1))
        btns.addWidget(b_add, 0, 0)
        btns.addWidget(b_dup, 0, 1)
        btns.addWidget(b_find, 1, 0, 1, 2)
        btns.addWidget(b_del, 2, 0)
        btns.addWidget(b_up, 3, 0)
        btns.addWidget(b_down, 3, 1)
        left.addLayout(btns)
        body.addLayout(left)
        self.form = CameraForm()
        self.form.changed.connect(self._form_changed)
        self.empty = QLabel(tr("no_camera_selected"))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("color:#8A90A0;")
        body.addWidget(self.form, 1)
        body.addWidget(self.empty, 1)
        lay.addLayout(body, 1)

        note = QLabel(tr("pw_note"))
        note.setStyleSheet("color:#8A90A0;")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = _buttons("save")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._refresh(select)

    # --- List handling ----------------------------------------------------------------

    def _item_text(self, i):
        cam = self.cams[i]
        text = f"{i + 1}.  {cam.label(i)}"
        if cam.host:
            text += f"   {cam.host}"
            if cam.channel > 1:
                text += f"  ch{cam.channel}"
        return text

    def _refresh(self, select=None):
        self.cur = None
        self.list.blockSignals(True)
        self.list.clear()
        for i in range(len(self.cams)):
            self.list.addItem(self._item_text(i))
        self.list.blockSignals(False)
        self.count.setText(tr("cameras_list", n=len(self.cams), max=MAX_CAMERAS))
        if self.cams:
            row = min(max(0, select or 0), len(self.cams) - 1)
            self.list.blockSignals(True)
            self.list.setCurrentRow(row)
            self.list.blockSignals(False)
            self._select(row)
        else:
            self._select(-1)

    def _commit(self):
        """Store the form in the current camera."""
        if self.cur is not None and 0 <= self.cur < len(self.cams):
            self.cams[self.cur] = self.form.camera()

    def _select(self, row):
        self._commit()
        has = 0 <= row < len(self.cams)
        self.form.setVisible(has)
        self.empty.setVisible(not has)
        self.cur = row if has else None
        if has:
            self.form.load(self.cams[row], row)

    def _form_changed(self):
        if self.cur is None:
            return
        self._commit()
        item = self.list.item(self.cur)
        if item is not None:
            item.setText(self._item_text(self.cur))

    def _room(self, n=1) -> bool:
        if len(self.cams) + n > MAX_CAMERAS:
            QMessageBox.information(self, tr("settings"), tr("max_cameras", n=MAX_CAMERAS))
            return False
        return True

    def _template(self) -> Camera:
        """New cameras get the login of the selected camera; most sites use the same one."""
        self._commit()
        base = self.cams[self.cur] if self.cur is not None else Camera()
        return Camera(user=base.user, password=base.password, http_port=base.http_port,
                      rtsp_port=base.rtsp_port)

    def _add(self):
        if not self._room():
            return
        self.cams.append(self._template())
        self._refresh(len(self.cams) - 1)
        self.form.host.setFocus()

    def _duplicate(self):
        if self.cur is None or not self._room():
            return
        self._commit()
        row = self.cur
        cam = copy.copy(self.cams[row])
        cam.channel = min(64, cam.channel + 1)
        cam.name = ""
        self.cams.insert(row + 1, cam)
        self._refresh(row + 1)

    def _discover(self):
        dlg = DiscoverDialog(self)
        if not dlg.exec() or not dlg.result_devices:
            return
        template = self._template()
        present = {(c.host, c.channel) for c in self.cams}
        new = [d for d in dlg.result_devices if (d["ip"], 1) not in present]
        if not new or not self._room(len(new)):
            return
        for d in new:
            cam = copy.copy(template)
            cam.host, cam.http_port, cam.name = d["ip"], d["http_port"], d["model"]
            self.cams.append(cam)
        self._refresh(len(self.cams) - 1)

    def _remove(self):
        if self.cur is None:
            return
        row = self.cur
        self.cur = None
        del self.cams[row]
        self._refresh(min(row, len(self.cams) - 1))

    def _move(self, d):
        if self.cur is None:
            return
        self._commit()
        a, b = self.cur, self.cur + d
        if 0 <= b < len(self.cams):
            self.cams[a], self.cams[b] = self.cams[b], self.cams[a]
            self._refresh(b)

    def apply_to(self, cfg):
        self._commit()
        cfg.customer = self.customer.text().strip()
        cfg.language = self.language.currentData()
        cfg.per_page = self.per_page.currentData()
        cfg.cameras = [c for c in self.cams if c.configured][:MAX_CAMERAS]
