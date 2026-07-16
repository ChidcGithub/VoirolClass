"""M3Switch — Material You 开关。

替代 QCheckBox 的开关变体，用于布尔值切换。
- 滑块（thumb）：关闭时 16x16 outline，打开时 24x24 primary
- 轨道（track）：关闭时 surface_variant，打开时 primary
- 状态层 + 涟漪
"""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QAbstractButton

from voirol.gui.m3.base import M3Widget, StateLayerOverlay, RippleOverlay
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3Switch(QAbstractButton, M3Widget):
    """M3 开关。"""

    TRACK_W = 52
    TRACK_H = 32
    THUMB_OFF = 16
    THUMB_ON = 24

    def __init__(self, checked: bool = False, parent=None):
        QAbstractButton.__init__(self, parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim_progress: float = 1.0 if checked else 0.0
        self._state_layer = StateLayerOverlay(self, "on_surface")
        self._ripple = RippleOverlay(self, "primary")
        M3Widget.__init__(self, parent)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        # 启动滑块动画
        target = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"anim_progress")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self._anim_progress)
        self._anim.setEndValue(target)
        self._anim.start()

    @pyqtProperty(float)
    def anim_progress(self) -> float:
        return self._anim_progress

    @anim_progress.setter
    def anim_progress(self, v: float):
        self._anim_progress = v
        self.update()

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self._scheme = scheme
        self._shape = shape
        # 透明背景
        self.setStyleSheet(f"""
            M3Switch {{
                background: transparent;
                border: none;
            }}
        """)

    def sizeHint(self) -> QSize:
        return QSize(self.TRACK_W, self.TRACK_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = self._scheme
        p = self._anim_progress
        checked = self.isChecked()
        disabled = not self.isEnabled()

        # 颜色插值
        track_color_off = QColor(s.surface_container_highest)
        track_color_on = QColor(s.primary)
        if disabled:
            track_color_off = QColor(s.rgba("on_surface", 0.12))
            track_color_on = QColor(s.rgba("on_surface", 0.12))
        # 线性插值
        track_color = _lerp_color(track_color_off, track_color_on, p)

        outline_off = QColor(s.outline)
        if disabled:
            outline_off = QColor(s.rgba("on_surface", 0.12))

        thumb_color_off = QColor(s.outline)
        thumb_color_on = QColor(s.on_primary)
        if disabled:
            thumb_color_off = QColor(s.rgba("on_surface", 0.38))
            thumb_color_on = QColor(s.surface)
        thumb_color = _lerp_color(thumb_color_off, thumb_color_on, p)

        # 轨道
        track_rect = QRectF(0, 0, self.TRACK_W, self.TRACK_H)
        # 关闭状态有边框
        if p < 0.5 and not disabled:
            painter.setPen(QPen(outline_off, 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, self.TRACK_H / 2, self.TRACK_H / 2)

        # 滑块
        thumb_size = _lerp(self.THUMB_OFF, self.THUMB_ON, p)
        if disabled:
            thumb_size = self.THUMB_OFF
        # 滑块位置：左边距 8px（关闭），右边距 8px（打开）
        margin = 8
        thumb_x_off = margin
        thumb_x_on = self.TRACK_W - margin - thumb_size
        thumb_x = _lerp(thumb_x_off, thumb_x_on, p)
        thumb_y = (self.TRACK_H - thumb_size) / 2

        # 状态层（在 thumb 下层）
        if self._state_layer:
            # 限制在 thumb 区域
            painter.save()
            painter.setClipRect(QRectF(thumb_x - 4, thumb_y - 4, thumb_size + 8, thumb_size + 8))
            self._state_layer.paint(painter)
            painter.restore()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb_color)
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_size, thumb_size))

        # 涟漪
        if self._ripple:
            painter.save()
            painter.setClipRect(QRectF(thumb_x - 4, thumb_y - 4, thumb_size + 8, thumb_size + 8))
            self._ripple.paint(painter)
            painter.restore()


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        int(_lerp(c1.red(), c2.red(), t)),
        int(_lerp(c1.green(), c2.green(), t)),
        int(_lerp(c1.blue(), c2.blue(), t)),
        int(_lerp(c1.alpha(), c2.alpha(), t)),
    )
