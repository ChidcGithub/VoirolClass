"""M3Button — Material You 规范按钮。

5 种变体：
    - Filled:   主色背景 + on-primary 文字（最强调）
    - Tonal:    secondary-container 背景（次强调）
    - Outlined: 透明背景 + outline 边框
    - Text:     透明背景，仅 primary 文字
    - Elevated: surface 背景 + 阴影

特性：
    - 圆角 full（9999px）
    - 涟漪效果（press 起点扩散）
    - 状态层（hover/focus/pressed 叠加）
    - 主题实时切换
    - 支持图标（左侧）
    - 支持禁用态
"""
from __future__ import annotations

import enum

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPainter, QPaintEvent
from PyQt6.QtWidgets import QPushButton

from voirol.gui.m3.base import M3Widget, StateLayerOverlay, RippleOverlay
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens


class M3Button(QPushButton, M3Widget):
    """Material You 按钮。"""

    class Variant(enum.Enum):
        FILLED = "filled"
        TONAL = "tonal"
        OUTLINED = "outlined"
        TEXT = "text"
        ELEVATED = "elevated"
        ERROR = "error"

    def __init__(
        self,
        text: str = "",
        icon: QIcon | None = None,
        variant: "M3Button.Variant" = Variant.FILLED,
        parent=None,
    ):
        # 注意：M3Widget.__init__ 会调用 apply_theme，QPushButton 必须先初始化
        QPushButton.__init__(self, text, parent)
        self._variant = variant
        self._icon = icon
        self._state_layer: StateLayerOverlay | None = None
        self._ripple: RippleOverlay | None = None
        # M3Widget 初始化（订阅主题 + 初始应用）
        M3Widget.__init__(self, parent)
        # 安装状态层 + 涟漪
        self._setup_overlays()

    def _setup_overlays(self):
        # 状态层颜色取决于变体
        color_attr = self._state_layer_color_attr()
        self._state_layer = StateLayerOverlay(self, color_attr)
        self._ripple = RippleOverlay(self, color_attr)

    def _state_layer_color_attr(self) -> str:
        """根据变体返回状态层应使用的颜色属性名"""
        return {
            self.Variant.FILLED: "on_primary",
            self.Variant.TONAL: "on_secondary_container",
            self.Variant.OUTLINED: "primary",
            self.Variant.TEXT: "primary",
            self.Variant.ELEVATED: "primary",
            self.Variant.ERROR: "on_error",
        }.get(self._variant, "on_primary")

    def set_variant(self, variant: "M3Button.Variant"):
        if variant == self._variant:
            return
        self._variant = variant
        # 更新 objectName 以兼容 QSS 选择器
        self.setObjectName(variant.value)
        # 更新状态层颜色
        if self._state_layer:
            self._state_layer.set_color_attr(self._state_layer_color_attr())
        if self._ripple:
            self._ripple._color_attr = self._state_layer_color_attr()
        self.apply_theme(self._scheme, self._shape)

    def variant(self) -> "M3Button.Variant":
        return self._variant

    def set_icon(self, icon: QIcon):
        self._icon = icon
        super().setIcon(icon)

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        """根据变体和主题生成内联 QSS（覆盖全局 QSS）"""
        v = self._variant
        self.setObjectName(v.value)

        if v == self.Variant.FILLED:
            self.setStyleSheet(f"""
                M3Button#{v.value} {{
                    background-color: {scheme.primary};
                    color: {scheme.on_primary};
                    border: none;
                    border-radius: {shape.full}px;
                    padding: 10px 24px;
                    font-weight: 500;
                    font-size: 14px;
                }}
                M3Button#{v.value}:disabled {{
                    background-color: {scheme.rgba("on_surface", 0.12)};
                    color: {scheme.rgba("on_surface", 0.38)};
                }}
            """)
        elif v == self.Variant.TONAL:
            self.setStyleSheet(f"""
                M3Button#{v.value} {{
                    background-color: {scheme.secondary_container};
                    color: {scheme.on_secondary_container};
                    border: none;
                    border-radius: {shape.full}px;
                    padding: 10px 24px;
                    font-weight: 500;
                    font-size: 14px;
                }}
                M3Button#{v.value}:disabled {{
                    background-color: {scheme.rgba("on_surface", 0.12)};
                    color: {scheme.rgba("on_surface", 0.38)};
                }}
            """)
        elif v == self.Variant.OUTLINED:
            self.setStyleSheet(f"""
                M3Button#{v.value} {{
                    background-color: transparent;
                    color: {scheme.primary};
                    border: 1px solid {scheme.outline};
                    border-radius: {shape.full}px;
                    padding: 10px 24px;
                    font-weight: 500;
                    font-size: 14px;
                }}
                M3Button#{v.value}:disabled {{
                    color: {scheme.rgba("on_surface", 0.38)};
                    border-color: {scheme.rgba("on_surface", 0.12)};
                }}
            """)
        elif v == self.Variant.TEXT:
            self.setStyleSheet(f"""
                M3Button#{v.value} {{
                    background-color: transparent;
                    color: {scheme.primary};
                    border: none;
                    border-radius: {shape.full}px;
                    padding: 10px 12px;
                    font-weight: 500;
                    font-size: 14px;
                }}
                M3Button#{v.value}:disabled {{
                    color: {scheme.rgba("on_surface", 0.38)};
                }}
            """)
        elif v == self.Variant.ELEVATED:
            self.setStyleSheet(f"""
                M3Button#{v.value} {{
                    background-color: {scheme.surface_container_low};
                    color: {scheme.primary};
                    border: none;
                    border-radius: {shape.full}px;
                    padding: 10px 24px;
                    font-weight: 500;
                    font-size: 14px;
                }}
                M3Button#{v.value}:disabled {{
                    background-color: {scheme.rgba("on_surface", 0.12)};
                    color: {scheme.rgba("on_surface", 0.38)};
                }}
            """)
        elif v == self.Variant.ERROR:
            self.setStyleSheet(f"""
                M3Button#{v.value} {{
                    background-color: {scheme.error};
                    color: {scheme.on_error};
                    border: none;
                    border-radius: {shape.full}px;
                    padding: 10px 24px;
                    font-weight: 500;
                    font-size: 14px;
                }}
                M3Button#{v.value}:disabled {{
                    background-color: {scheme.rgba("on_surface", 0.12)};
                    color: {scheme.rgba("on_surface", 0.38)};
                }}
            """)

    def sizeHint(self) -> QSize:
        sz = super().sizeHint()
        # M3 规范：高度 40px
        sz.setHeight(max(sz.height(), 40))
        return sz

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event: QPaintEvent):
        # 先让 QPushButton 绘制主体
        super().paintEvent(event)
        # 再叠加状态层 + 涟漪
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._state_layer:
            self._state_layer.paint(painter)
        if self._ripple:
            self._ripple.paint(painter)
        painter.end()
