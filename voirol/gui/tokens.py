"""Material You Design Token 体系。

提供颜色、形状、字体、海拔、动效 5 类 token，作为整个 GUI 的统一设计语言。
所有组件应从 token 取值，不硬编码颜色/尺寸。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from PyQt6.QtCore import QEasingCurve
from PyQt6.QtGui import QColor


# ════════════════════════════════════════════════════════════════════════
# 颜色 Token
# ════════════════════════════════════════════════════════════════════════


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """'#A8C7FA' / 'A8C7FA' / '#FFA8C7FA' → (r, g, b) 0-255"""
    h = hex_str.lstrip("#")
    if len(h) == 8:
        h = h[2:]
    if len(h) != 6:
        raise ValueError(f"invalid hex color: {hex_str!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_to_qcolor(hex_str: str) -> QColor:
    r, g, b = _hex_to_rgb(hex_str)
    return QColor(r, g, b)


def _hex_to_vec3(hex_str: str) -> tuple[float, float, float]:
    """'#A8C7FA' → (0.659, 0.780, 0.980)，供 OpenGL shader uniform 使用"""
    r, g, b = _hex_to_rgb(hex_str)
    return (r / 255.0, g / 255.0, b / 255.0)


def _with_alpha(hex_str: str, alpha: float) -> str:
    """hex 颜色 + alpha(0-1) → rgba() 字符串，供 QSS 使用"""
    r, g, b = _hex_to_rgb(hex_str)
    return f"rgba({r}, {g}, {b}, {alpha})"


@dataclass(frozen=True)
class M3ColorScheme:
    """Material You 完整颜色方案（由 seed color 经 HCT 生成）。"""

    # 主色系
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    primary_fixed: str
    primary_fixed_dim: str
    on_primary_fixed: str
    on_primary_fixed_variant: str

    # 次级色
    secondary: str
    on_secondary: str
    secondary_container: str
    on_secondary_container: str
    secondary_fixed: str
    secondary_fixed_dim: str
    on_secondary_fixed: str
    on_secondary_fixed_variant: str

    # 三级色
    tertiary: str
    on_tertiary: str
    tertiary_container: str
    on_tertiary_container: str
    tertiary_fixed: str
    tertiary_fixed_dim: str
    on_tertiary_fixed: str
    on_tertiary_fixed_variant: str

    # 错误色
    error: str
    on_error: str
    error_container: str
    on_error_container: str

    # 表面色（5 级 container + bright/dim）
    surface: str
    on_surface: str
    surface_variant: str
    on_surface_variant: str
    surface_dim: str
    surface_bright: str
    surface_container_lowest: str
    surface_container_low: str
    surface_container: str
    surface_container_high: str
    surface_container_highest: str

    # 轮廓
    outline: str
    outline_variant: str

    # 反色
    inverse_surface: str
    inverse_on_surface: str
    inverse_primary: str

    # 其他
    scrim: str
    shadow: str
    surface_tint: str

    # 元信息
    is_dark: bool
    source_color: str

    # ── 便捷访问 ──

    @property
    def primary_rgb(self) -> tuple[int, int, int]:
        return _hex_to_rgb(self.primary)

    @property
    def primary_vec3(self) -> tuple[float, float, float]:
        return _hex_to_vec3(self.primary)

    @property
    def on_primary_vec3(self) -> tuple[float, float, float]:
        return _hex_to_vec3(self.on_primary)

    def qcolor(self, name: str) -> QColor:
        return _hex_to_qcolor(getattr(self, name))

    def rgba(self, name: str, alpha: float) -> str:
        """带透明度的 rgba() 字符串"""
        return _with_alpha(getattr(self, name), alpha)

    def hover_overlay(self, name: str) -> str:
        return self.rgba(name, STATE_LAYER_HOVER)

    def focus_overlay(self, name: str) -> str:
        return self.rgba(name, STATE_LAYER_FOCUS)

    def pressed_overlay(self, name: str) -> str:
        return self.rgba(name, STATE_LAYER_PRESSED)


# 状态层透明度（M3 规范）
STATE_LAYER_HOVER = 0.08
STATE_LAYER_FOCUS = 0.10
STATE_LAYER_PRESSED = 0.10
STATE_LAYER_DRAGGED = 0.16
STATE_LAYER_SELECTED = 0.12


# ════════════════════════════════════════════════════════════════════════
# 形状 Token
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class M3ShapeTokens:
    """M3 形状 token：6 级圆角。"""

    xs: int = 4       # Badge / Chip
    sm: int = 8       # Text field / List item
    md: int = 12      # Card / Menu
    lg: int = 16      # Dialog / Large card
    xl: int = 28      # FAB / Large dialog
    full: int = 9999  # Button / Switch


SHAPE = M3ShapeTokens()


# ════════════════════════════════════════════════════════════════════════
# 字体 Token
# ════════════════════════════════════════════════════════════════════════


class M3TypeToken(NamedTuple):
    size: int        # px
    weight: int      # 400=Regular, 500=Medium, 700=Bold
    tracking: float  # 字间距 px
    line_height: float = 1.5


TYPE_SCALE: dict[str, M3TypeToken] = {
    # Display
    "display_large":   M3TypeToken(57, 400, -0.25, 1.12),
    "display_medium":  M3TypeToken(45, 400, 0,    1.15),
    "display_small":   M3TypeToken(36, 400, 0,    1.22),
    # Headline
    "headline_large":  M3TypeToken(32, 400, 0,    1.25),
    "headline_medium": M3TypeToken(28, 400, 0,    1.29),
    "headline_small":  M3TypeToken(24, 400, 0,    1.33),
    # Title
    "title_large":     M3TypeToken(22, 500, 0,    1.27),
    "title_medium":    M3TypeToken(16, 500, 0.15, 1.5),
    "title_small":     M3TypeToken(14, 500, 0.1,  1.43),
    # Body
    "body_large":      M3TypeToken(16, 400, 0.5,  1.5),
    "body_medium":     M3TypeToken(14, 400, 0.25, 1.43),
    "body_small":      M3TypeToken(12, 400, 0.4,  1.33),
    # Label
    "label_large":     M3TypeToken(14, 500, 0.1,  1.43),
    "label_medium":    M3TypeToken(12, 500, 0.5,  1.33),
    "label_small":     M3TypeToken(11, 500, 0.5,  1.45),
}


def type_css(name: str) -> str:
    """生成 QSS font 片段"""
    t = TYPE_SCALE[name]
    return f"font-size: {t.size}px; font-weight: {t.weight}; letter-spacing: {t.tracking}px;"


# ════════════════════════════════════════════════════════════════════════
# 海拔 Token
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class M3Elevation:
    """单级海拔：阴影 + 表面 tint。"""
    shadow_y: float = 0.0      # 阴影偏移
    shadow_blur: float = 0.0
    shadow_spread: float = 0.0
    shadow_alpha: float = 0.0
    surface_tint_alpha: float = 0.0  # primary 色叠加


ELEVATIONS: dict[int, M3Elevation] = {
    0: M3Elevation(0, 0, 0, 0, 0),
    1: M3Elevation(1, 3, 0, 0.30, 0.05),
    2: M3Elevation(2, 6, 0, 0.30, 0.08),
    3: M3Elevation(4, 8, 0, 0.30, 0.11),
    4: M3Elevation(6, 10, 0, 0.30, 0.12),
    5: M3Elevation(8, 12, 0, 0.30, 0.14),
}


def elevation_qss(level: int, scheme: M3ColorScheme) -> str:
    """生成海拔 QSS（box-shadow 用多层 border 模拟 + background tint）"""
    e = ELEVATIONS.get(level, ELEVATIONS[0])
    if level == 0:
        return ""
    # QSS 不支持 box-shadow，用 background tint 表达
    tint = _with_alpha(scheme.primary, e.surface_tint_alpha) if e.surface_tint_alpha > 0 else "transparent"
    return f"background-blend-mode: overlay;"


def elevation_shadow_pyqt(level: int, scheme: M3ColorScheme) -> list[tuple[float, float, float, QColor]]:
    """返回 [(dy, blur, spread, color)] 用于 QPainter 绘制多层阴影"""
    e = ELEVATIONS.get(level, ELEVATIONS[0])
    if level == 0:
        return []
    shadow_color = QColor(0, 0, 0, int(e.shadow_alpha * 255))
    return [
        (e.shadow_y, e.shadow_blur, e.shadow_spread, shadow_color),
        (e.shadow_y * 0.4, e.shadow_blur * 0.5, 0, QColor(0, 0, 0, int(e.shadow_alpha * 255 * 0.6))),
    ]


# ════════════════════════════════════════════════════════════════════════
# 动效 Token
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class M3MotionTokens:
    """M3 动效 token。"""
    # 持续时间（毫秒）
    duration_short1: int = 100   # 微交互（涟漪、状态层）
    duration_short2: int = 150
    duration_short3: int = 200
    duration_short4: int = 250

    duration_medium1: int = 300  # 元素出现/消失
    duration_medium2: int = 350
    duration_medium3: int = 400
    duration_medium4: int = 450

    duration_long1: int = 500    # 页面切换
    duration_long2: int = 550

    # 缓动曲线
    # PyQt6 没有 EmphasizedCurve，用自定义 bezier 近似
    easing_emphasized: QEasingCurve.Type = QEasingCurve.Type.OutCubic
    easing_emphasized_decelerate: QEasingCurve.Type = QEasingCurve.Type.OutQuart
    easing_emphasized_accelerate: QEasingCurve.Type = QEasingCurve.Type.InQuart
    easing_standard: QEasingCurve.Type = QEasingCurve.Type.OutCubic
    easing_standard_decelerate: QEasingCurve.Type = QEasingCurve.Type.OutQuart
    easing_standard_accelerate: QEasingCurve.Type = QEasingCurve.Type.InQuart


MOTION = M3MotionTokens()


# ════════════════════════════════════════════════════════════════════════
# 间距 Token
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class M3Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48


SPACING = M3Spacing()


# ════════════════════════════════════════════════════════════════════════
# 默认种子色（Google Blue）
# ════════════════════════════════════════════════════════════════════════


DEFAULT_SEED = "#A8C7FA"

# M3 Expressive 推荐预设种子色
PRESET_SEEDS: list[tuple[str, str, str]] = [
    # (id, 显示名, hex)
    ("google_blue", "Google Blue", "#A8C7FA"),
    ("green",       "Forest",      "#A8D8A8"),
    ("orange",      "Sunset",      "#FFB88C"),
    ("red",         "Crimson",     "#F5B8B5"),
    ("purple",      "Violet",      "#D0BCFF"),
    ("cyan",        "Ocean",       "#B0E0E6"),
    ("pink",        "Blossom",     "#F8BBD0"),
    ("amber",       "Amber",       "#FFE082"),
]
