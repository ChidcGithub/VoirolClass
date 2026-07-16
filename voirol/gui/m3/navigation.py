"""M3NavigationBar — Material You 导航栏。

用于替代 QTabWidget，提供 M3 规范的导航：
    - 顶部 NavigationBar（图标 + 文字，水平排列）
    - 侧边 NavigationRail（仅图标，垂直排列）

特性：
    - 选中项使用 pill 形状的高亮容器
    - 状态层 + 涟漪
    - 主题感知
"""
from __future__ import annotations

import enum

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from voirol.gui.m3.base import M3Widget, StateLayerOverlay, RippleOverlay
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class _NavButton(QToolButton):
    """单个导航按钮。"""

    def __init__(self, label: str, icon: QIcon | None, index: int, parent=None):
        super().__init__(parent)
        self._index = index
        self._label = label
        self._icon = icon
        self.setCheckable(True)
        self.setText(label)
        if icon:
            self.setIcon(icon)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._state_layer = StateLayerOverlay(self, "on_surface")
        self._ripple = RippleOverlay(self, "on_surface")

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                color: {scheme.on_surface_variant};
                border: none;
                border-radius: {shape.full}px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
            }}
            QToolButton:checked {{
                background-color: {scheme.secondary_container};
                color: {scheme.on_secondary_container};
            }}
        """)
        if self._state_layer:
            self._state_layer.set_color_attr(
                "on_secondary_container" if self.isChecked() else "on_surface_variant"
            )

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._state_layer:
            self._state_layer.paint(painter)
        if self._ripple:
            self._ripple.paint(painter)


class M3NavigationBar(QWidget, M3Widget):
    """M3 顶部导航栏。"""

    # (index) — 选中项变化
    current_changed = pyqtSignal(int)

    class Style(enum.Enum):
        BAR = "bar"   # 顶部水平
        RAIL = "rail"  # 侧边垂直

    def __init__(self, style: "M3NavigationBar.Style" = Style.BAR, parent=None):
        QWidget.__init__(self, parent)
        self._style = style
        self._buttons: list[_NavButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.buttonClicked.connect(self._on_clicked)

        if style == self.Style.BAR:
            self._layout = QHBoxLayout(self)
        else:
            self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)

        M3Widget.__init__(self, parent)

    def add_item(self, label: str, icon: QIcon | None = None) -> int:
        btn = _NavButton(label, icon, len(self._buttons), self)
        self._buttons.append(btn)
        self._group.addButton(btn, len(self._buttons) - 1)
        self._layout.addWidget(btn)
        btn.apply_theme(self._scheme, self._shape)
        return len(self._buttons) - 1

    def set_current(self, index: int):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self.current_changed.emit(index)

    def set_item_label(self, index: int, label: str):
        """更新指定导航项的文本（用于实时语言切换）。"""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setText(label)
            self._buttons[index]._label = label

    def _on_clicked(self, btn: _NavButton):
        idx = self._buttons.index(btn)
        self.current_changed.emit(idx)
        # 切换状态层颜色
        for b in self._buttons:
            b.apply_theme(self._scheme, self._shape)

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        self.setStyleSheet(f"""
            M3NavigationBar {{
                background-color: {scheme.surface};
                border: none;
            }}
        """)
        for btn in self._buttons:
            btn.apply_theme(scheme, shape)

    def sizeHint(self) -> QSize:
        if self._style == self.Style.BAR:
            return QSize(400, 80)
        return QSize(80, 400)
