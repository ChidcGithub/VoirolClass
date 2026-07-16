"""M3Card — Material You 卡片。

4 种变体：
    - Elevated:  surface-container-low + 阴影
    - Filled:    surface-container-highest
    - Outlined:  surface + outline 边框
    - Default:   surface-container-low（无阴影无边框）
"""
from __future__ import annotations

import enum

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPainterPath
from PyQt6.QtWidgets import QFrame

from voirol.gui.m3.base import M3Widget
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens, ELEVATIONS


class M3Card(QFrame, M3Widget):
    """M3 卡片容器。"""

    class Variant(enum.Enum):
        DEFAULT = "default"
        ELEVATED = "elevated"
        FILLED = "filled"
        OUTLINED = "outlined"

    def __init__(
        self,
        title: str = "",
        variant: "M3Card.Variant" = Variant.ELEVATED,
        elevation: int = 1,
        parent=None,
    ):
        QFrame.__init__(self, parent)
        self._variant = variant
        self._elevation = elevation
        self._title = title
        M3Widget.__init__(self, parent)

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        v = self._variant
        self.setObjectName(v.value)

        if v == self.Variant.ELEVATED:
            bg = scheme.surface_container_low
            border = "none"
            shadow_alpha = ELEVATIONS[self._elevation].shadow_alpha
        elif v == self.Variant.FILLED:
            bg = scheme.surface_container_highest
            border = "none"
            shadow_alpha = 0
        elif v == self.Variant.OUTLINED:
            bg = scheme.surface
            border = f"1px solid {scheme.outline_variant}"
            shadow_alpha = 0
        else:  # DEFAULT
            bg = scheme.surface_container_low
            border = "none"
            shadow_alpha = 0

        self.setStyleSheet(f"""
            M3Card#{v.value} {{
                background-color: {bg};
                border: {border};
                border-radius: {shape.md}px;
            }}
        """)

    def set_elevation(self, level: int):
        self._elevation = max(0, min(5, level))
        self.apply_theme(self._scheme, self._shape)

    def paintEvent(self, event: QPaintEvent):
        # 绘制阴影（QSS 不支持 box-shadow）
        if self._variant == self.Variant.ELEVATED and self._elevation > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            e = ELEVATIONS[self._elevation]
            rect = QRectF(self.rect()).adjusted(0, 0, -1, -1)
            # 多层阴影模拟
            for i in range(3):
                offset = e.shadow_y * (1 + i * 0.5)
                blur = e.shadow_blur * (1 + i * 0.3)
                alpha = int(e.shadow_alpha * 255 * (1 - i * 0.3))
                color = QColor(0, 0, 0, alpha)
                painter.setBrush(color)
                painter.setPen(__import__("PyQt6").QtCore.Qt.PenStyle.NoPen)
                path = QPainterPath()
                shadow_rect = rect.translated(0, offset).adjusted(
                    -blur * 0.3, -blur * 0.1, blur * 0.3, blur * 0.3
                )
                path.addRoundedRect(shadow_rect, self._shape.md, self._shape.md)
                painter.fillPath(path, color)
            painter.end()
        # 然后由 QFrame 绘制背景+内容
        super().paintEvent(event)


class M3ElevatedCard(M3Card):
    def __init__(self, title: str = "", parent=None):
        super().__init__(title, M3Card.Variant.ELEVATED, elevation=1, parent=parent)


class M3FilledCard(M3Card):
    def __init__(self, title: str = "", parent=None):
        super().__init__(title, M3Card.Variant.FILLED, parent=parent)


class M3OutlinedCard(M3Card):
    def __init__(self, title: str = "", parent=None):
        super().__init__(title, M3Card.Variant.OUTLINED, parent=parent)
