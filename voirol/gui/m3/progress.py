"""M3 Progress — Material You 进度指示器。

- M3CircularProgress: 圆形旋转进度（不确定）
- M3LinearProgress:   线性进度条（可确定/不确定）
"""
from __future__ import annotations

import time

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, QTimer, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget

from voirol.gui.m3.base import M3Widget
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3CircularProgress(QWidget, M3Widget):
    """M3 圆形进度指示器（不确定模式）。"""

    SIZE = 48
    STROKE = 4
    SWEEP = 270  # 旋转弧度（度）

    def __init__(self, parent=None, size: int = 48):
        QWidget.__init__(self, parent)
        self._size = size
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._start_time = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        M3Widget.__init__(self, parent)

    def _tick(self):
        # M3 规范：360° per 1.4s
        elapsed = (time.monotonic() - self._start_time) * 1000
        self._angle = (elapsed * 360.0 / 1400.0) % 360.0
        self.update()

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self._scheme = scheme
        self.setStyleSheet("background: transparent;")

    def sizeHint(self):
        return (self._size, self._size)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        r = (self._size - self.STROKE) / 2

        # track
        track_color = QColor(self._scheme.surface_container_highest)
        painter.setPen(QPen(track_color, self.STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # arc
        primary = QColor(self._scheme.primary)
        painter.setPen(QPen(primary, self.STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        start = int(self._angle * 16)
        span = int(self.SWEEP * 16)
        painter.drawArc(
            int(cx - r), int(cy - r), int(r * 2), int(r * 2),
            -start, -span,
        )


class M3LinearProgress(QWidget, M3Widget):
    """M3 线性进度条。"""

    def __init__(self, parent=None, determinate: bool = False):
        QWidget.__init__(self, parent)
        self._determinate = determinate
        self._value = 0  # 0-100
        self._indeterminate_phase = 0.0
        self._start_time = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.setFixedHeight(4)
        M3Widget.__init__(self, parent)

    def set_value(self, value: int):
        self._value = max(0, min(100, value))
        self._determinate = True
        self.update()

    def _tick(self):
        if not self._determinate:
            elapsed = time.monotonic() - self._start_time
            # 不确定模式：条形左右往返
            self._indeterminate_phase = (elapsed % 1.8) / 1.8
            self.update()

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self._scheme = scheme
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        radius = rect.height() / 2

        # track
        track_color = QColor(self._scheme.surface_container_highest)
        painter.setBrush(track_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # fill
        primary = QColor(self._scheme.primary)
        painter.setBrush(primary)
        if self._determinate:
            fill_w = rect.width() * self._value / 100.0
            fill_rect = QRectF(0, 0, fill_w, rect.height())
            painter.drawRoundedRect(fill_rect, radius, radius)
        else:
            # 不确定模式：宽度 40%，从左到右移动
            w = rect.width() * 0.4
            # phase: 0 -> 1，移动从 -w 到 rect.width
            t = self._indeterminate_phase
            # ease-in-out
            t = 4 * t ** 3 if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2
            x = -w + (rect.width() + w) * t
            fill_rect = QRectF(x, 0, w, rect.height())
            painter.drawRoundedRect(fill_rect, radius, radius)
