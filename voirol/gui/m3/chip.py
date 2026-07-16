"""M3Chip — Material You 标签。

变体：
    - Assist:    辅助（默认）
    - Filter:    筛选（可选中）
    - Input:     输入（带删除按钮）
    - Suggestion: 建议
"""
from __future__ import annotations

import enum

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPaintEvent
from PyQt6.QtWidgets import QAbstractButton

from voirol.gui.m3.base import M3Widget, StateLayerOverlay, RippleOverlay
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3Chip(QAbstractButton, M3Widget):
    """M3 标签。"""

    class Variant(enum.Enum):
        ASSIST = "assist"
        FILTER = "filter"
        INPUT = "input"
        SUGGESTION = "suggestion"

    # 删除按钮点击信号（仅 INPUT 变体）
    delete_clicked = pyqtSignal()

    def __init__(
        self,
        text: str = "",
        variant: "M3Chip.Variant" = Variant.ASSIST,
        checkable: bool = False,
        parent=None,
    ):
        QAbstractButton.__init__(self, parent)
        self._variant = variant
        self.setText(text)
        self.setCheckable(variant == self.Variant.FILTER or checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._state_layer = StateLayerOverlay(self, "on_surface")
        self._ripple = RippleOverlay(self, "on_surface")
        M3Widget.__init__(self, parent)

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        v = self._variant
        self.setObjectName(v.value)

        if v == self.Variant.FILTER:
            self.setStyleSheet(f"""
                M3Chip#{v.value} {{
                    background-color: {scheme.surface_container_low};
                    color: {scheme.on_surface_variant};
                    border: 1px solid {scheme.outline_variant};
                    border-radius: {shape.sm}px;
                    padding: 8px 12px;
                    font-size: 14px;
                }}
                M3Chip#{v.value}:checked {{
                    background-color: {scheme.secondary_container};
                    color: {scheme.on_secondary_container};
                    border: none;
                    padding: 9px 12px;
                }}
                M3Chip#{v.value}:disabled {{
                    color: {scheme.rgba("on_surface", 0.38)};
                    background-color: {scheme.rgba("on_surface", 0.12)};
                }}
            """)
            # 切换状态层颜色
            if self._state_layer:
                self._state_layer.set_color_attr(
                    "on_secondary_container" if self.isChecked() else "on_surface_variant"
                )
        else:
            # ASSIST / INPUT / SUGGESTION 共用样式
            self.setStyleSheet(f"""
                M3Chip#{v.value} {{
                    background-color: {scheme.surface_container_low};
                    color: {scheme.on_surface_variant};
                    border: none;
                    border-radius: {shape.sm}px;
                    padding: 8px 12px;
                    font-size: 14px;
                }}
                M3Chip#{v.value}:disabled {{
                    color: {scheme.rgba("on_surface", 0.38)};
                }}
            """)

    def sizeHint(self) -> QSize:
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        w = fm.horizontalAdvance(self.text()) + 40
        return QSize(max(w, 60), 32)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._state_layer:
            self._state_layer.paint(painter)
        if self._ripple:
            self._ripple.paint(painter)
