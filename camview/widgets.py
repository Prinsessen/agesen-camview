"""Widgets: video tile, PTZ joystick and company bar."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QRadialGradient)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

BG = QColor(14, 15, 18)


class VideoTile(QWidget):
    clicked = Signal(int)
    doubleClicked = Signal(int)
    resized = Signal(int, int, int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.title = ""
        self.status = ""
        self.image = None
        self.selected = False
        self.ptz = False
        self.accent = QColor("#2F80ED")
        self.setMinimumSize(160, 90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_image(self, img: QImage):
        self.image = img
        self.status = ""
        self.update()

    def set_status(self, text: str):
        self.status = text
        self.update()

    def clear(self, status: str):
        self.image = None
        self.status = status
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.index)

    def resizeEvent(self, e):
        self.resized.emit(self.index, self.width(), self.height())
        super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, BG)
        if self.image is not None and not self.image.isNull():
            s = min(r.width() / self.image.width(), r.height() / self.image.height())
            w, h = self.image.width() * s, self.image.height() * s
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(QRectF((r.width() - w) / 2, (r.height() - h) / 2, w, h), self.image)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Name in the top left corner
        f = QFont(self.font())
        f.setPointSizeF(9.5)
        f.setBold(True)
        p.setFont(f)
        label = self.title + ("   PTZ" if self.ptz else "")
        tw = p.fontMetrics().horizontalAdvance(label) + 16
        pill = QRectF(8, 8, tw, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        p.drawRoundedRect(pill, 6, 6)
        p.setPen(QColor(235, 235, 240))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)

        if self.status:
            f.setBold(False)
            f.setPointSizeF(10.5)
            p.setFont(f)
            fm = p.fontMetrics()
            lines = self.status.split("\n")
            bw = max(fm.horizontalAdvance(t) for t in lines) + 32
            bh = fm.height() * len(lines) + 18
            box = QRectF((r.width() - bw) / 2, (r.height() - bh) / 2, bw, bh)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor(210, 212, 220))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.status)

        if self.selected:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(self.accent, 3))
            p.drawRect(QRectF(r).adjusted(1.5, 1.5, -1.5, -1.5))
        p.end()


class Joystick(QWidget):
    """Drag the knob: direction = pan/tilt, distance from the centre = speed."""

    moved = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.knob = QPointF(0, 0)
        self.dragging = False
        self.accent = QColor("#2F80ED")
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _center(self):
        return QPointF(self.width() / 2, self.height() / 2)

    def _radius(self):
        return min(self.width(), self.height()) / 2 - 30

    def _update(self, pos):
        v = pos - self._center()
        R = self._radius()
        length = math.hypot(v.x(), v.y())
        if length > R:
            v = v * (R / length)
        self.knob = v
        self.update()
        x, y = v.x() / R, -v.y() / R
        x = 0.0 if abs(x) < 0.1 else x
        y = 0.0 if abs(y) < 0.1 else y
        self.moved.emit(x, y)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._update(e.position())

    def mouseMoveEvent(self, e):
        if self.dragging:
            self._update(e.position())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.release()

    def release(self):
        self.dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.knob = QPointF(0, 0)
        self.update()
        self.moved.emit(0.0, 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._center()
        outer = min(self.width(), self.height()) / 2 - 4
        g = QRadialGradient(c, outer)
        g.setColorAt(0, QColor(48, 52, 62))
        g.setColorAt(1, QColor(26, 28, 34))
        p.setPen(QPen(QColor(70, 75, 88), 2))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, outer, outer)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(150, 155, 170))
        a, d = 8, outer - 14
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            tip = QPointF(c.x() + dx * d, c.y() + dy * d)
            base = QPointF(c.x() + dx * (d - 12), c.y() + dy * (d - 12))
            px, py = -dy, dx
            p.drawPolygon(QPolygonF([tip, QPointF(base.x() + px * a, base.y() + py * a),
                                     QPointF(base.x() - px * a, base.y() - py * a)]))

        k = c + self.knob
        kr = 26
        kg = QRadialGradient(k + QPointF(-8, -8), kr * 1.6)
        kg.setColorAt(0, self.accent.lighter(150))
        kg.setColorAt(1, self.accent.darker(130))
        p.setPen(QPen(QColor(0, 0, 0, 90), 2))
        p.setBrush(QBrush(kg))
        p.drawEllipse(k, kr, kr)
        p.end()


class BrandBar(QWidget):
    """Narrow bar at the bottom with the company logo and contact info. Fixed in the program."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from . import brand
        self.setFixedHeight(46)
        self.accent = QColor(brand.ACCENT)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 14, 4)
        lay.setSpacing(10)
        self.logo = QLabel()
        pm = QPixmap()
        pm.loadFromData(brand.LOGO_PNG, "PNG")
        dpr = self.devicePixelRatioF() or 1.0
        pm = pm.scaledToHeight(int(30 * dpr), Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.logo.setPixmap(pm)
        self.logo.setToolTip(brand.COMPANY)
        self.contact = QLabel(brand.CONTACT)
        self.contact.setStyleSheet("color:#A8AEBD; font-size:9.5pt;")
        lay.addWidget(self.logo)
        lay.addStretch(1)
        lay.addWidget(self.contact)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(22, 24, 29))
        p.fillRect(0, 0, self.width(), 2, self.accent)
        p.end()


def make_app_icon() -> QPixmap:
    """Simple camera glyph, used when there is no .ico."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2F80ED"))
    p.drawRoundedRect(QRectF(4, 16, 42, 32), 7, 7)
    path = QPainterPath()
    path.moveTo(46, 26)
    path.lineTo(60, 18)
    path.lineTo(60, 46)
    path.lineTo(46, 38)
    path.closeSubpath()
    p.drawPath(path)
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(QPointF(25, 32), 8, 8)
    p.end()
    return pm
