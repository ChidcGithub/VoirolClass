"""M3Snackbar — Material You 底部通知。

用法：
    M3Snackbar.show(parent, "已保存", action_text="撤销", on_action=callback)

特性：
    - 从底部滑入
    - 4 秒后自动消失
    - 可选 action 按钮
    - 主题感知
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from voirol.gui.m3.base import M3Widget
from voirol.gui.m3.button import M3Button
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3Snackbar(QWidget, M3Widget):
    """M3 Snackbar。"""

    DURATION_MS = 4000

    _instances: list["M3Snackbar"] = []

    def __init__(self, parent: QWidget):
        QWidget.__init__(self, parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._message = ""
        self._action_text = ""
        self._action_callback = None
        self._y_offset = 60.0  # 起始 Y 偏移（在屏幕底部之下）

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(16)

        self._label = QLabel(self)
        self._label.setStyleSheet("font-size: 14px; background: transparent;")
        self._layout.addWidget(self._label, stretch=1)

        self._action_btn: M3Button | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DURATION_MS)
        self._timer.timeout.connect(self.hide_anim)

        M3Widget.__init__(self, parent)

    @classmethod
    def show(
        cls,
        parent: QWidget,
        message: str,
        action_text: str = "",
        on_action=None,
        duration: int | None = None,
    ):
        """显示一个 snackbar"""
        sb = cls(parent)
        sb._message = message
        sb._action_text = action_text
        sb._action_callback = on_action
        if duration:
            sb._timer.setInterval(duration)

        sb._label.setText(message)
        if action_text:
            sb._action_btn = M3Button(action_text, variant=M3Button.Variant.TEXT, parent=sb)
            if on_action:
                sb._action_btn.clicked.connect(on_action)
            sb._action_btn.clicked.connect(sb.hide_anim)
            sb._layout.addWidget(sb._action_btn)

        sb.apply_theme(sb._scheme, sb._shape)

        # 调整位置：底部居中
        parent_rect = parent.rect()
        w = max(280, sb.sizeHint().width())
        h = sb.sizeHint().height()
        sb.setGeometry(
            (parent_rect.width() - w) // 2,
            parent_rect.height() - h - 24,
            w,
            h,
        )
        QWidget.show(sb)
        sb.raise_()

        # 滑入动画
        sb._y_offset = float(sb.y() + 60)
        sb._anim = QPropertyAnimation(sb, b"slide_y")
        sb._anim.setDuration(250)
        sb._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        sb._anim.setStartValue(sb._y_offset)
        sb._anim.setEndValue(float(sb.y()))
        sb._anim.start()

        sb._timer.start()
        cls._instances.append(sb)
        return sb

    def hide_anim(self):
        if not self.isVisible():
            return
        self._timer.stop()
        target = self.y() + 60
        self._anim = QPropertyAnimation(self, b"slide_y")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.setStartValue(float(self.y()))
        self._anim.setEndValue(float(target))
        self._anim.finished.connect(self._on_hidden)
        self._anim.start()

    def _on_hidden(self):
        self.hide()
        if self in M3Snackbar._instances:
            M3Snackbar._instances.remove(self)
        self.deleteLater()

    @pyqtProperty(float)
    def slide_y(self) -> float:
        return float(self.y())

    @slide_y.setter
    def slide_y(self, v: float):
        self.move(self.x(), int(v))

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self.setStyleSheet(f"""
            M3Snackbar {{
                background-color: {scheme.inverse_surface};
                border-radius: {shape.xs}px;
            }}
        """)
        self._label.setStyleSheet(
            f"color: {scheme.inverse_on_surface}; font-size: 14px; background: transparent;"
        )
        if self._action_btn:
            self._action_btn.apply_theme(scheme, shape)
            # 反色背景下的按钮使用 inverse_primary
            self._action_btn.setStyleSheet(f"""
                M3Button#text {{
                    background: transparent;
                    color: {scheme.inverse_primary};
                    border: none;
                    border-radius: {shape.full}px;
                    padding: 8px 12px;
                    font-weight: 500;
                }}
            """)

    def sizeHint(self):
        sz = super().sizeHint()
        sz.setHeight(48)
        return sz

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
