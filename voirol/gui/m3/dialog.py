"""M3Dialog — Material You 对话框规范。

- 圆角 xl (28px)
- Scrim（背景遮罩）
- 标题 / 内容 / 按钮区
- 主题感知
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voirol.gui.m3.base import M3Widget
from voirol.gui.m3.button import M3Button
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3Dialog(QDialog, M3Widget):
    """M3 对话框基类。"""

    def __init__(self, title: str = "", parent=None):
        QDialog.__init__(self, parent)
        self._title = title
        # 无边框 + 半透明背景（自绘 scrim + card）
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        M3Widget.__init__(self, parent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 卡片容器
        from PyQt6.QtWidgets import QFrame
        self._card = QFrame(self)
        self._card.setObjectName("m3DialogCard")
        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(24, 24, 24, 20)
        self._card_layout.setSpacing(0)

        # 标题
        self._title_label = QLabel(self._title, self._card)
        self._title_label.setStyleSheet("font-size: 22px; font-weight: 500; background: transparent;")
        self._card_layout.addWidget(self._title_label)
        self._card_layout.addSpacing(16)

        # 内容区（子类填充）
        self._content_widget = QWidget(self._card)
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.addWidget(self._content_widget)

        # 按钮区
        self._card_layout.addSpacing(24)
        self._button_row = QHBoxLayout()
        self._button_row.setSpacing(8)
        self._button_row.addStretch()
        self._card_layout.addLayout(self._button_row)

        outer.addStretch()
        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

    def add_button(self, text: str, variant: M3Button.Variant = M3Button.Variant.TEXT,
                   on_click=None) -> M3Button:
        btn = M3Button(text, variant=variant, parent=self._card)
        if on_click:
            btn.clicked.connect(on_click)
        self._button_row.addWidget(btn)
        return btn

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self._card.setStyleSheet(f"""
            QFrame#m3DialogCard {{
                background-color: {scheme.surface_container_high};
                border-radius: {shape.xl}px;
            }}
            QLabel {{
                color: {scheme.on_surface};
                background: transparent;
            }}
        """)
        self._title_label.setStyleSheet(
            f"font-size: 22px; font-weight: 500; "
            f"color: {scheme.on_surface}; background: transparent;"
        )

    def paintEvent(self, event: QPaintEvent):
        # 绘制 scrim
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # M3 scrim: on_surface @ 32%
        painter.fillRect(self.rect(), QColor(0, 0, 0, 82))
        painter.end()


class M3AlertDialog(M3Dialog):
    """M3 警告对话框（带图标）。"""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(title, parent)
        msg = QLabel(message, self._content_widget)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"font-size: 14px; color: {self._scheme.on_surface_variant};"
            "background: transparent;"
        )
        self._content_layout.addWidget(msg)
