"""Material You 主题管理器。

提供 seed color → HCT 色彩空间 → 完整 M3ColorScheme → QSS + 信号广播 的完整链路。
支持：
  - light / dark / system 三种模式
  - 自定义种子色（8 个预设 + QColorDialog）
  - 从 Windows 壁纸动态提取种子色
  - 主题变化时通过信号广播给所有订阅组件（含 OpenGL）
  - 实时切换，无需重启
"""
from __future__ import annotations

import ctypes
import os
import struct
from ctypes import wintypes
from enum import Enum

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QWidget

from voirol.gui.tokens import (
    DEFAULT_SEED,
    M3ColorScheme,
    M3ShapeTokens,
    M3MotionTokens,
    SHAPE,
    MOTION,
    PRESET_SEEDS,
    STATE_LAYER_HOVER,
    STATE_LAYER_FOCUS,
    STATE_LAYER_PRESSED,
    _hex_to_rgb,
    _hex_to_vec3,
    _with_alpha,
)
from voirol.utils.logger import get_logger

logger = get_logger("gui.theme")


# ════════════════════════════════════════════════════════════════════════
# 主题模式枚举
# ════════════════════════════════════════════════════════════════════════


class ThemeMode(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


# 向后兼容：保留旧 Theme 枚举名
Theme = ThemeMode


# ════════════════════════════════════════════════════════════════════════
# 系统主题检测
# ════════════════════════════════════════════════════════════════════════


def detect_system_theme() -> ThemeMode:
    """检测当前 Windows 是 light 还是 dark 模式"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return ThemeMode.LIGHT if value == 1 else ThemeMode.DARK
    except Exception:
        pass
    try:
        scheme = QApplication.styleHints().colorScheme()
        return ThemeMode.LIGHT if scheme == Qt.ColorScheme.Light else ThemeMode.DARK
    except Exception:
        return ThemeMode.DARK


def resolve_theme(mode: ThemeMode | str) -> ThemeMode:
    """将字符串或 ThemeMode 解析为具体的 light/dark（system 会被解析）"""
    if isinstance(mode, str):
        mode = ThemeMode(mode)
    if mode == ThemeMode.SYSTEM:
        return detect_system_theme()
    return mode


# ════════════════════════════════════════════════════════════════════════
# HCT 调色板生成
# ════════════════════════════════════════════════════════════════════════


def generate_scheme(seed_hex: str, is_dark: bool) -> M3ColorScheme:
    """从种子色经 HCT 色彩空间生成完整 M3 调色板。

    Args:
        seed_hex: 种子色，如 '#A8C7FA'
        is_dark: 是否生成暗色方案

    Returns:
        M3ColorScheme 完整调色板
    """
    try:
        from material_color_utilities import (
            argb_from_hex,
            theme_from_argb_color,
        )

        argb = argb_from_hex(seed_hex)
        theme = theme_from_argb_color(argb)
        s = theme.schemes.dark if is_dark else theme.schemes.light

        def g(attr: str) -> str:
            v = getattr(s, attr)
            # 库返回值可能已经是 hex 字符串（如 '#a6c8ff'）
            if isinstance(v, str):
                return v if v.startswith("#") else f"#{v}"
            # 兜底：转 int 再转 hex
            return f"#{int(v):06x}"

        return M3ColorScheme(
            # 主色系
            primary=g("primary"),
            on_primary=g("on_primary"),
            primary_container=g("primary_container"),
            on_primary_container=g("on_primary_container"),
            primary_fixed=g("primary_fixed"),
            primary_fixed_dim=g("primary_fixed_dim"),
            on_primary_fixed=g("on_primary_fixed"),
            on_primary_fixed_variant=g("on_primary_fixed_variant"),
            # 次级色
            secondary=g("secondary"),
            on_secondary=g("on_secondary"),
            secondary_container=g("secondary_container"),
            on_secondary_container=g("on_secondary_container"),
            secondary_fixed=g("secondary_fixed"),
            secondary_fixed_dim=g("secondary_fixed_dim"),
            on_secondary_fixed=g("on_secondary_fixed"),
            on_secondary_fixed_variant=g("on_secondary_fixed_variant"),
            # 三级色
            tertiary=g("tertiary"),
            on_tertiary=g("on_tertiary"),
            tertiary_container=g("tertiary_container"),
            on_tertiary_container=g("on_tertiary_container"),
            tertiary_fixed=g("tertiary_fixed"),
            tertiary_fixed_dim=g("tertiary_fixed_dim"),
            on_tertiary_fixed=g("on_tertiary_fixed"),
            on_tertiary_fixed_variant=g("on_tertiary_fixed_variant"),
            # 错误色
            error=g("error"),
            on_error=g("on_error"),
            error_container=g("error_container"),
            on_error_container=g("on_error_container"),
            # 表面色
            surface=g("surface"),
            on_surface=g("on_surface"),
            surface_variant=g("surface_variant"),
            on_surface_variant=g("on_surface_variant"),
            surface_dim=g("surface_dim"),
            surface_bright=g("surface_bright"),
            surface_container_lowest=g("surface_container_lowest"),
            surface_container_low=g("surface_container_low"),
            surface_container=g("surface_container"),
            surface_container_high=g("surface_container_high"),
            surface_container_highest=g("surface_container_highest"),
            # 轮廓
            outline=g("outline"),
            outline_variant=g("outline_variant"),
            # 反色
            inverse_surface=g("inverse_surface"),
            inverse_on_surface=g("inverse_on_surface"),
            inverse_primary=g("inverse_primary"),
            # 其他
            scrim=g("scrim"),
            shadow=g("shadow"),
            surface_tint=g("surface_tint"),
            # 元信息
            is_dark=is_dark,
            source_color=seed_hex,
        )
    except Exception as e:
        logger.warning(f"HCT scheme generation failed ({e}), falling back to hardcoded Google Blue")
        return _fallback_scheme(is_dark, seed_hex)


def _fallback_scheme(is_dark: bool, seed_hex: str) -> M3ColorScheme:
    """HCT 生成失败时的兜底方案（硬编码 Google Blue M3 dark/light）。"""
    if is_dark:
        return M3ColorScheme(
            primary="#A8C7FA", on_primary="#062E6F",
            primary_container="#0842A0", on_primary_container="#D3E3FD",
            primary_fixed="#D3E3FD", primary_fixed_dim="#A8C7FA",
            on_primary_fixed="#001D3F", on_primary_fixed_variant="#002F6C",
            secondary="#CAC4D0", on_secondary="#332D41",
            secondary_container="#4A4458", on_secondary_container="#E7E0EC",
            secondary_fixed="#E7E0EC", secondary_fixed_dim="#CAC4D0",
            on_secondary_fixed="#1D1A22", on_secondary_fixed_variant="#332D41",
            tertiary="#EFB8C8", on_tertiary="#492532",
            tertiary_container="#633B48", on_tertiary_container="#FFD8E4",
            tertiary_fixed="#FFD8E4", tertiary_fixed_dim="#EFB8C8",
            on_tertiary_fixed="#31101D", on_tertiary_fixed_variant="#633B48",
            error="#F2B8B5", on_error="#601410",
            error_container="#8C1D18", on_error_container="#F9DEDC",
            surface="#141218", on_surface="#E6E0E9",
            surface_variant="#49454F", on_surface_variant="#CAC4D0",
            surface_dim="#141218", surface_bright="#3B383E",
            surface_container_lowest="#0F0D13",
            surface_container_low="#1D1B20",
            surface_container="#211F26",
            surface_container_high="#2B2930",
            surface_container_highest="#36343B",
            outline="#938F99", outline_variant="#49454F",
            inverse_surface="#E6E0E9", inverse_on_surface="#322F35",
            inverse_primary="#0842A0",
            scrim="#000000", shadow="#000000", surface_tint="#E6E0E9",
            is_dark=True, source_color=seed_hex,
        )
    return M3ColorScheme(
        primary="#1A73E8", on_primary="#FFFFFF",
        primary_container="#D3E3FD", on_primary_container="#041E49",
        primary_fixed="#D3E3FD", primary_fixed_dim="#1A73E8",
        on_primary_fixed="#001D3F", on_primary_fixed_variant="#002F6C",
        secondary="#565F71", on_secondary="#FFFFFF",
        secondary_container="#DAE2F9", on_secondary_container="#131C2B",
        secondary_fixed="#DAE2F9", secondary_fixed_dim="#BDC7DC",
        on_secondary_fixed="#131C2B", on_secondary_fixed_variant="#3C4758",
        tertiary="#6C5536", on_tertiary="#FFFFFF",
        tertiary_container="#F8DEB6", on_tertiary_container="#251A07",
        tertiary_fixed="#F8DEB6", tertiary_fixed_dim="#DBC197",
        on_tertiary_fixed="#251A07", on_tertiary_fixed_variant="#41331B",
        error="#BA1A1A", on_error="#FFFFFF",
        error_container="#FFDAD6", on_error_container="#410002",
        surface="#FEFBFF", on_surface="#1C1B1F",
        surface_variant="#E7E0EC", on_surface_variant="#49454F",
        surface_dim="#DED8E1", surface_bright="#FEFBFF",
        surface_container_lowest="#FFFFFF",
        surface_container_low="#F7F2FA",
        surface_container="#F3EDF7",
        surface_container_high="#ECE6F0",
        surface_container_highest="#E6E0E9",
        outline="#79747E", outline_variant="#CAC4D0",
        inverse_surface="#322F35", inverse_on_surface="#F5EFF7",
        inverse_primary="#A8C7FA",
        scrim="#000000", shadow="#000000", surface_tint="#6750A4",
        is_dark=False, source_color=seed_hex,
    )


# ════════════════════════════════════════════════════════════════════════
# 壁纸种子色提取
# ════════════════════════════════════════════════════════════════════════


def get_windows_wallpaper_path() -> str | None:
    """获取当前 Windows 桌面壁纸文件路径"""
    try:
        SPI_GETDESKWALLPAPER = 0x0073
        MAX_PATH = 260
        buf = ctypes.create_unicode_buffer(MAX_PATH)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETDESKWALLPAPER, MAX_PATH, buf, 0
        )
        path = buf.value
        if path and os.path.exists(path):
            return path
    except Exception as e:
        logger.debug(f"get wallpaper path failed: {e}")
    return None


def extract_color_from_wallpaper(path: str, sample_size: int = 64) -> str:
    """从壁纸图像中提取主色作为种子色。

    采用缩放采样 + 颜色量化 + 频率统计的方式，避免引入 scikit-learn 等大依赖。

    Args:
        path: 壁纸文件路径
        sample_size: 缩放后的采样边长（像素），越小越快但精度越低

    Returns:
        种子色 hex 字符串，如 '#A8C7FA'
    """
    try:
        from PyQt6.QtGui import QPixmap, QImage
        from PyQt6.QtCore import Qt

        img = QImage(path)
        if img.isNull():
            raise ValueError("QImage load failed")

        # 缩放到小尺寸加速处理
        img = img.scaled(
            sample_size, sample_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        img = img.convertToFormat(QImage.Format.Format_RGB32)

        # 颜色量化到 4x4x4=64 桶（每通道 4 档：0/64/128/192），统计频率
        buckets: dict[tuple[int, int, int], int] = {}
        ptr = img.bits()
        ptr.setsize(img.sizeInBytes())
        data = bytes(ptr)

        # Format_RGB32 是 BGRA 字节序
        for i in range(0, len(data), 4):
            b = data[i]
            g = data[i + 1]
            r = data[i + 2]
            # 量化
            qr = (r >> 6) << 6
            qg = (g >> 6) << 6
            qb = (b >> 6) << 6
            # 略去极端暗/亮的颜色
            if qr + qg + qb < 30 or qr + qg + qb > 720:
                continue
            key = (qr, qg, qb)
            buckets[key] = buckets.get(key, 0) + 1

        if not buckets:
            # 全部被过滤：取所有像素的均值
            r_sum = g_sum = b_sum = 0
            n = 0
            for i in range(0, len(data), 4):
                b_sum += data[i]
                g_sum += data[i + 1]
                r_sum += data[i + 2]
                n += 1
            if n == 0:
                raise ValueError("empty image")
            r, g, b = r_sum // n, g_sum // n, b_sum // n
            return f"#{r:02X}{g:02X}{b:02X}"

        # 取频率最高的桶，用桶内中心色
        (r, g, b), _ = max(buckets.items(), key=lambda x: x[1])
        # 加 32 拉到桶中心
        r = min(255, r + 32)
        g = min(255, g + 32)
        b = min(255, b + 32)
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception as e:
        logger.warning(f"wallpaper color extraction failed: {e}")
        return DEFAULT_SEED


def detect_wallpaper_seed() -> str:
    """从当前 Windows 壁纸提取种子色"""
    path = get_windows_wallpaper_path()
    if not path:
        return DEFAULT_SEED
    return extract_color_from_wallpaper(path)


# ════════════════════════════════════════════════════════════════════════
# M3ThemeManager
# ════════════════════════════════════════════════════════════════════════


class M3ThemeManager(QObject):
    """统一主题管理器。

    职责：
      - 持有当前 seed / mode / scheme / shape / motion
      - 提供 QSS 生成（基于 token 动态拼接，不再用固定模板）
      - 主题变化时通过 theme_changed 信号广播给所有订阅组件
      - 支持壁纸动态取色
    """

    # 参数：scheme, shape, motion
    theme_changed = pyqtSignal(M3ColorScheme, M3ShapeTokens, M3MotionTokens)

    def __init__(self):
        super().__init__()
        self._seed: str = DEFAULT_SEED
        self._mode: ThemeMode = ThemeMode.SYSTEM
        self._dynamic_color: bool = False
        self._shape: M3ShapeTokens = SHAPE
        self._motion: M3MotionTokens = MOTION
        self._scheme: M3ColorScheme = generate_scheme(
            self._seed, resolve_theme(self._mode) == ThemeMode.DARK
        )

    # ── 访问器 ──

    def current_scheme(self) -> M3ColorScheme:
        return self._scheme

    def current_shape(self) -> M3ShapeTokens:
        return self._shape

    def current_motion(self) -> M3MotionTokens:
        return self._motion

    def current_seed(self) -> str:
        return self._seed

    def current_mode(self) -> ThemeMode:
        return self._mode

    def is_dark(self) -> bool:
        return self._scheme.is_dark

    def is_dynamic_color(self) -> bool:
        return self._dynamic_color

    # ── 设置 ──

    def set_seed(self, hex_color: str, broadcast: bool = True):
        """设置种子色并重新生成调色板"""
        if hex_color == self._seed and not self._dynamic_color:
            return
        self._seed = hex_color
        self._regenerate(broadcast)
        logger.info(f"Seed color set to {hex_color}")

    def set_mode(self, mode: ThemeMode | str, broadcast: bool = True):
        """设置主题模式（light/dark/system）"""
        if isinstance(mode, str):
            mode = ThemeMode(mode)
        if mode == self._mode:
            return
        self._mode = mode
        self._regenerate(broadcast)
        logger.info(f"Theme mode set to {mode.value}")

    def set_dynamic_color(self, enabled: bool, broadcast: bool = True):
        """启用/禁用壁纸动态取色"""
        if enabled == self._dynamic_color:
            return
        self._dynamic_color = enabled
        if enabled:
            seed = detect_wallpaper_seed()
            self._seed = seed
        self._regenerate(broadcast)
        logger.info(f"Dynamic color {'enabled' if enabled else 'disabled'}")

    def refresh_wallpaper_color(self, broadcast: bool = True):
        """重新从壁纸提取种子色（壁纸切换时调用）"""
        if not self._dynamic_color:
            return
        self._seed = detect_wallpaper_seed()
        self._regenerate(broadcast)

    def _regenerate(self, broadcast: bool):
        """重新生成调色板并广播"""
        resolved = resolve_theme(self._mode)
        self._scheme = generate_scheme(self._seed, resolved == ThemeMode.DARK)
        if broadcast:
            self.theme_changed.emit(self._scheme, self._shape, self._motion)

    # ── QSS 生成 ──

    def generate_qss(self) -> str:
        """基于当前 scheme 动态生成完整 QSS"""
        s = self._scheme
        br = self._shape
        return _build_qss(s, br)

    def apply_to(self, widget: QWidget):
        """应用主题到指定 widget"""
        widget.setStyleSheet(self.generate_qss())

    # ── OpenGL palette ──

    def opengl_palette(self) -> dict[str, tuple[float, float, float] | float]:
        """返回 OpenGL shader 需要的 uniform 字典。

        大部分为 vec3（颜色），u_is_dark 为标量 float。
        """
        s = self._scheme
        return {
            "u_color_primary": _hex_to_vec3(s.primary),
            "u_color_on_primary": _hex_to_vec3(s.on_primary),
            "u_color_primary_container": _hex_to_vec3(s.primary_container),
            "u_color_on_primary_container": _hex_to_vec3(s.on_primary_container),
            "u_color_surface_highest": _hex_to_vec3(s.surface_container_highest),
            "u_color_surface_high": _hex_to_vec3(s.surface_container_high),
            "u_color_surface_container": _hex_to_vec3(s.surface_container),
            "u_color_outline_variant": _hex_to_vec3(s.outline_variant),
            "u_color_on_surface": _hex_to_vec3(s.on_surface),
            "u_color_on_surface_variant": _hex_to_vec3(s.on_surface_variant),
            "u_color_secondary": _hex_to_vec3(s.secondary),
            "u_color_error": _hex_to_vec3(s.error),
            "u_color_surface": _hex_to_vec3(s.surface),
            "u_color_inverse_primary": _hex_to_vec3(s.inverse_primary),
            "u_is_dark": 1.0 if s.is_dark else 0.0,
        }


# ════════════════════════════════════════════════════════════════════════
# 单例
# ════════════════════════════════════════════════════════════════════════


_theme_manager: M3ThemeManager | None = None


def get_theme_manager() -> M3ThemeManager:
    """获取全局 M3ThemeManager 单例"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = M3ThemeManager()
    return _theme_manager


# 向后兼容：旧的 ThemeManager API
class ThemeManager(M3ThemeManager):
    """旧 ThemeManager 的兼容包装（已弃用，使用 M3ThemeManager）。"""

    changed = pyqtSignal(M3ColorScheme, int)  # 旧信号签名

    def broadcast(self, theme: ThemeMode, br: int):
        """旧 API：广播主题"""
        self.set_mode(theme)


# ════════════════════════════════════════════════════════════════════════
# 便捷函数（兼容旧 API）
# ════════════════════════════════════════════════════════════════════════


def apply_theme(widget: QWidget, theme: ThemeMode | str, br: int = 5) -> None:
    """旧 API：应用主题到 widget（基于 M3ThemeManager 单例）。"""
    mgr = get_theme_manager()
    if isinstance(theme, str):
        theme = ThemeMode(theme)
    # 仅当 mode 真正变化时才切换
    if mgr.current_mode() != theme:
        mgr.set_mode(theme)
    mgr.apply_to(widget)


def theme_qss(theme: ThemeMode | str, br: int = 5) -> str:
    """旧 API：返回 QSS（使用全局 M3ThemeManager 生成）"""
    mgr = get_theme_manager()
    if isinstance(theme, str):
        theme = ThemeMode(theme)
    if mgr.current_mode() != theme:
        mgr.set_mode(theme, broadcast=False)
    return mgr.generate_qss()


# ════════════════════════════════════════════════════════════════════════
# QSS 生成器
# ════════════════════════════════════════════════════════════════════════


def _build_qss(s: M3ColorScheme, shape: M3ShapeTokens) -> str:
    """基于 M3ColorScheme 动态生成完整 QSS。

    相比旧版的固定模板，这里所有颜色都从 scheme 取值，
    支持 light/dark + 任意种子色。
    """
    # 预计算状态层 rgba 值（str.format 不支持调用方法）
    ctx = {
        "s": s,
        "shape": shape,
        "hover_on_primary": _with_alpha(s.on_primary, STATE_LAYER_HOVER),
        "hover_on_surface": _with_alpha(s.on_surface, STATE_LAYER_HOVER),
        "pressed_on_primary": _with_alpha(s.on_primary, STATE_LAYER_PRESSED),
        "hover_on_secondary": _with_alpha(s.on_secondary, STATE_LAYER_HOVER),
        "hover_on_error": _with_alpha(s.on_error, STATE_LAYER_HOVER),
    }
    return _QSS_TEMPLATE.format(**ctx)


# QSS 模板：所有颜色引用 {s.xxx}，所有圆角引用 {shape.xxx}
_QSS_TEMPLATE = """
/* ════════════════════════════════════════════════════════════════
   Material You QSS — 由 M3ThemeManager.generate_qss() 动态生成
   seed={s.source_color}  is_dark={s.is_dark}
   ════════════════════════════════════════════════════════════════ */

QWidget {{
    background-color: {s.surface};
    color: {s.on_surface};
    font-size: 14px;
}}

QDialog, QMainWindow {{
    background-color: {s.surface};
    color: {s.on_surface};
}}

/* ── Tab ── */
QTabWidget::pane {{
    background-color: {s.surface};
    border: none;
    border-top: 1px solid {s.outline_variant};
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {s.on_surface_variant};
    padding: 10px 24px;
    border: none;
    border-radius: {shape.full}px;
    min-width: 80px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
}}
QTabBar::tab:hover:!selected {{
    background-color: {hover_on_surface};
    color: {s.on_surface};
}}
QTabBar::tab:disabled {{
    color: {s.outline_variant};
}}

/* ── GroupBox → M3 Outlined Card ── */
QGroupBox {{
    background-color: {s.surface_container_low};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    margin-top: 16px;
    padding: 20px 16px 16px;
    font-weight: 500;
    color: {s.on_surface};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: {s.primary};
    background-color: {s.surface};
}}

/* ── Button — Filled (默认) ── */
QPushButton {{
    background-color: {s.primary};
    color: {s.on_primary};
    border: none;
    border-radius: {shape.full}px;
    padding: 10px 24px;
    min-height: 24px;
    font-weight: 500;
    font-size: 14px;
}}
QPushButton:hover {{
    background-color: {s.primary};
    color: {s.on_primary};
}}
QPushButton:pressed {{
    background-color: {s.primary};
    color: {s.on_primary};
}}
QPushButton:disabled {{
    background-color: {s.on_surface};
    color: {s.surface};
    opacity: 0.38;
}}
QPushButton:checked {{
    background-color: {s.primary};
    color: {s.on_primary};
}}

/* ── Outlined Button 变体（通过 objectName == "outlined"） ── */
QPushButton#outlined {{
    background-color: transparent;
    color: {s.primary};
    border: 1px solid {s.outline};
    border-radius: {shape.full}px;
}}
QPushButton#outlined:hover {{
    background-color: {s.primary};
    color: {s.on_primary};
    border-color: {s.primary};
}}
QPushButton#outlined:pressed {{
    background-color: {s.primary};
    color: {s.on_primary};
}}
QPushButton#outlined:disabled {{
    color: {s.on_surface};
    opacity: 0.38;
    border-color: {s.on_surface};
}}

/* ── Text Button 变体 ── */
QPushButton#text {{
    background-color: transparent;
    color: {s.primary};
    border: none;
    border-radius: {shape.full}px;
    padding: 10px 12px;
}}
QPushButton#text:hover {{
    background-color: {s.primary_container};
    color: {s.on_primary_container};
}}
QPushButton#text:pressed {{
    background-color: {s.primary_container};
    color: {s.on_primary_container};
}}
QPushButton#text:disabled {{
    color: {s.on_surface};
    opacity: 0.38;
}}

/* ── Tonal Button 变体 ── */
QPushButton#tonal {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
    border: none;
    border-radius: {shape.full}px;
    padding: 10px 24px;
}}
QPushButton#tonal:hover {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
}}
QPushButton#tonal:disabled {{
    background-color: {s.on_surface};
    color: {s.surface};
    opacity: 0.38;
}}

/* ── Error Button 变体 ── */
QPushButton#error {{
    background-color: {s.error};
    color: {s.on_error};
    border: none;
    border-radius: {shape.full}px;
    padding: 10px 24px;
}}
QPushButton#error:hover {{
    background-color: {s.error_container};
    color: {s.on_error_container};
}}

/* ── LineEdit → M3 Outlined Text Field ── */
QLineEdit {{
    background-color: {s.surface_container};
    color: {s.on_surface};
    border: 1px solid {s.outline};
    border-radius: {shape.sm}px;
    padding: 12px 12px;
    selection-background-color: {s.primary};
    selection-color: {s.on_primary};
}}
QLineEdit:hover {{
    border-color: {s.on_surface};
}}
QLineEdit:focus {{
    border-color: {s.primary};
    border-width: 2px;
    padding: 11px 11px;
}}
QLineEdit:disabled {{
    color: {s.on_surface};
    background-color: {s.on_surface};
    opacity: 0.38;
    border-color: {s.on_surface};
}}

/* ── ComboBox ── */
QComboBox {{
    background-color: {s.surface_container};
    color: {s.on_surface};
    border: 1px solid {s.outline};
    border-radius: {shape.sm}px;
    padding: 10px 12px;
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: {s.on_surface};
}}
QComboBox:focus {{
    border-color: {s.primary};
    border-width: 2px;
    padding: 9px 11px;
}}
QComboBox:disabled {{
    color: {s.on_surface};
    background-color: {s.on_surface};
    opacity: 0.38;
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {s.on_surface_variant};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {s.surface_container_high};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    padding: 8px;
    selection-background-color: {s.secondary_container};
    selection-color: {s.on_secondary_container};
    outline: none;
}}

/* ── SpinBox ── */
QSpinBox, QDoubleSpinBox {{
    background-color: {s.surface_container};
    color: {s.on_surface};
    border: 1px solid {s.outline};
    border-radius: {shape.sm}px;
    padding: 10px 12px;
    min-height: 24px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {s.on_surface};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {s.primary};
    border-width: 2px;
    padding: 9px 11px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    border: none;
    border-left: 1px solid {s.outline_variant};
    background-color: transparent;
    width: 22px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    border-left: 1px solid {s.outline_variant};
    background-color: transparent;
    width: 22px;
}}

/* ── ListWidget ── */
QListWidget {{
    background-color: {s.surface_container_low};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    padding: 8px;
    outline: none;
}}
QListWidget::item {{
    padding: 10px 12px;
    border-radius: {shape.sm}px;
    margin: 2px 0;
}}
QListWidget::item:selected {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
}}
QListWidget::item:hover:!selected {{
    background-color: {s.surface_container_high};
}}
QListWidget::item:focus {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
}}

/* ── CheckBox ── */
QCheckBox {{
    color: {s.on_surface};
    spacing: 12px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {s.on_surface_variant};
    border-radius: {shape.xs}px;
    background-color: transparent;
}}
QCheckBox::indicator:hover {{
    border-color: {s.primary};
}}
QCheckBox::indicator:checked {{
    background-color: {s.primary};
    border-color: {s.primary};
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+CiAgPHBhdGggZmlsbD0ie29uX3ByaW1hcnl9IiBkPSJNNiAxMS45TDIuNSA4LjQgMy45IDcgNiA5LjEgMTIuMSAzbDEuNCAxLjR6Ii8+Cjwvc3ZnPgo=);
}}
QCheckBox:disabled {{
    color: {s.on_surface};
    opacity: 0.38;
}}

/* ── ScrollArea ── */
QScrollArea {{
    background-color: {s.surface};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {s.surface};
}}

/* ── Label ── */
QLabel {{
    color: {s.on_surface};
    background: transparent;
}}

/* ── TableWidget ── */
QTableWidget {{
    background-color: {s.surface_container_low};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    gridline-color: {s.outline_variant};
    outline: none;
}}
QTableWidget::item {{
    padding: 8px;
}}
QTableWidget::item:selected {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
}}
QHeaderView::section {{
    background-color: {s.surface_container};
    color: {s.on_surface_variant};
    border: none;
    border-bottom: 1px solid {s.outline_variant};
    padding: 10px 8px;
    font-weight: 500;
}}

/* ── ProgressBar ── */
QProgressBar {{
    background-color: {s.surface_container_highest};
    border: none;
    border-radius: {shape.full}px;
    text-align: center;
    color: {s.on_surface};
    min-height: 4px;
    max-height: 4px;
}}
QProgressBar::chunk {{
    background-color: {s.primary};
    border-radius: {shape.full}px;
}}

/* ── ScrollBar ── */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px;
}}
QScrollBar::handle:vertical {{
    background-color: {s.outline_variant};
    border-radius: {shape.full}px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {s.outline};
}}
QScrollBar::handle:vertical:pressed {{
    background-color: {s.outline};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 4px;
}}
QScrollBar::handle:horizontal {{
    background-color: {s.outline_variant};
    border-radius: {shape.full}px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {s.outline};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: transparent;
}}

/* ── Menu ── */
QMenu {{
    background-color: {s.surface_container_high};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    padding: 8px 0;
    min-width: 200px;
}}
QMenu::item {{
    padding: 10px 16px 10px 14px;
    margin: 0 8px;
    border-radius: {shape.sm}px;
}}
QMenu::item:selected {{
    background-color: {s.surface_container_highest};
    color: {s.on_surface};
}}
QMenu::item:disabled {{
    color: {s.on_surface_variant};
    opacity: 0.38;
}}
QMenu::separator {{
    height: 1px;
    background-color: {s.outline_variant};
    margin: 8px 12px;
}}
QMenu::icon {{
    padding-left: 4px;
}}

/* ── ToolButton ── */
QToolButton {{
    background-color: transparent;
    color: {s.on_surface_variant};
    border: none;
    border-radius: {shape.full}px;
    padding: 8px;
}}
QToolButton:hover {{
    background-color: {s.surface_container_high};
    color: {s.on_surface};
}}
QToolButton:checked {{
    background-color: {s.secondary_container};
    color: {s.on_secondary_container};
}}

/* ── Frame ── */
QFrame[frameShape="4"] {{
    border: none;
    border-top: 1px solid {s.outline_variant};
}}

/* ── ToolTip ── */
QToolTip {{
    background-color: {s.inverse_surface};
    color: {s.inverse_on_surface};
    border: none;
    border-radius: {shape.sm}px;
    padding: 8px 12px;
}}

/* ── PlainTextEdit (log view) ── */
QPlainTextEdit {{
    background-color: {s.surface_container_low};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    padding: 12px;
    selection-background-color: {s.primary};
    selection-color: {s.on_primary};
}}

/* ── TextEdit ── */
QTextEdit {{
    background-color: {s.surface_container_low};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: {shape.md}px;
    padding: 12px;
    selection-background-color: {s.primary};
    selection-color: {s.on_primary};
}}

/* ── StackedWidget ── */
QStackedWidget {{
    background-color: {s.surface};
    border: none;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {s.outline_variant};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ── Slider ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {s.surface_container_highest};
    border-radius: {shape.full}px;
}}
QSlider::sub-page:horizontal {{
    background: {s.primary};
    border-radius: {shape.full}px;
}}
QSlider::handle:horizontal {{
    background: {s.primary};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: {shape.full}px;
}}
QSlider::handle:horizontal:hover {{
    background: {s.primary};
    border: 4px solid {s.primary_container};
    margin: -10px -4px;
}}

/* ── RadioButton ── */
QRadioButton {{
    color: {s.on_surface};
    spacing: 12px;
    background: transparent;
}}
QRadioButton::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {s.on_surface_variant};
    border-radius: {shape.full}px;
    background-color: transparent;
}}
QRadioButton::indicator:checked {{
    border-color: {s.primary};
    background-color: {s.primary};
}}

/* ── 滚动区域 ── */
QAbstractScrollArea {{
    background-color: {s.surface};
    color: {s.on_surface};
}}
"""
