"""M3TextField — Material You 文本输入框。

两种变体：
    - Filled:   填充背景 + 下划线
    - Outlined: 透明背景 + outline 边框

支持浮动 label（label 在聚焦/有内容时上移）。
"""
from __future__ import annotations

import enum

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPalette
from PyQt6.QtWidgets import QLineEdit, QWidget

from voirol.gui.m3.base import M3Widget
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3TextField(QLineEdit, M3Widget):
    """M3 文本输入框。"""

    class Variant(enum.Enum):
        FILLED = "filled"
        OUTLINED = "outlined"

    def __init__(
        self,
        placeholder: str = "",
        label: str = "",
        variant: "M3TextField.Variant" = Variant.OUTLINED,
        parent=None,
    ):
        QLineEdit.__init__(self, parent)
        self._variant = variant
        self._label = label
        self._floating = False
        self.setPlaceholderText(placeholder)
        # 留出 label 空间
        if variant == self.Variant.OUTLINED and label:
            margins = self.textMargins()
            margins.setTop(8)
            self.setTextMargins(margins)
        M3Widget.__init__(self, parent)
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str):
        new_floating = bool(text) or self.hasFocus()
        if new_floating != self._floating:
            self._floating = new_floating
            self.update()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._floating = True
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._floating = bool(self.text())
        self.update()

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        v = self._variant
        self.setObjectName(v.value)
        if v == self.Variant.FILLED:
            self.setStyleSheet(f"""
                M3TextField#{v.value} {{
                    background-color: {scheme.surface_container};
                    color: {scheme.on_surface};
                    border: none;
                    border-bottom: 2px solid {scheme.on_surface_variant};
                    border-radius: {shape.xs}px {shape.xs}px 0 0;
                    padding: 12px 16px;
                    selection-background-color: {scheme.primary};
                    selection-color: {scheme.on_primary};
                }}
                M3TextField#{v.value}:focus {{
                    border-bottom: 2px solid {scheme.primary};
                }}
            """)
        else:  # OUTLINED
            self.setStyleSheet(f"""
                M3TextField#{v.value} {{
                    background-color: transparent;
                    color: {scheme.on_surface};
                    border: 1px solid {scheme.outline};
                    border-radius: {shape.xs}px;
                    padding: 12px 16px;
                    selection-background-color: {scheme.primary};
                    selection-color: {scheme.on_primary};
                }}
                M3TextField#{v.value}:hover {{
                    border-color: {scheme.on_surface};
                }}
                M3TextField#{v.value}:focus {{
                    border: 2px solid {scheme.primary};
                    padding: 11px 15px;
                }}
                M3TextField#{v.value}:disabled {{
                    color: {scheme.rgba("on_surface", 0.38)};
                    border-color: {scheme.rgba("on_surface", 0.12)};
                }}
            """)

    def sizeHint(self) -> QSize:
        sz = super().sizeHint()
        sz.setHeight(max(sz.height(), 56))
        return sz
