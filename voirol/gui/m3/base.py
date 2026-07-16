"""M3 组件基类：M3Widget + StateLayer + Ripple。

- M3Widget: 所有 M3 组件的基类，自动订阅 theme_changed 信号
- StateLayerOverlay: M3 状态层（hover/focus/pressed 的半透明叠加）
- RippleOverlay: M3 涟漪效果（press 时从鼠标位置扩散的圆形）
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QEnterEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from voirol.gui.theme import M3ThemeManager, get_theme_manager
from voirol.gui.tokens import (
    M3ColorScheme,
    M3ShapeTokens,
    STATE_LAYER_HOVER,
    STATE_LAYER_FOCUS,
    STATE_LAYER_PRESSED,
)


# ════════════════════════════════════════════════════════════════════════
# M3Widget 基类
# ════════════════════════════════════════════════════════════════════════


class M3Widget(QObject):
    """M3 组件 mixin 基类。

    作为 mixin 与具体 QWidget 子类（QPushButton、QLineEdit 等）一起使用，
    提供主题订阅与 apply_theme 钩子。不直接继承 QWidget，以避免多重继承时的
    MRO 冲突。

    功能：
        - 自动订阅 M3ThemeManager.theme_changed
        - 子类重写 apply_theme() 实现主题切换
        - 提供 retranslate_ui() 钩子用于实时语言切换
    """

    # 语言变化信号（由全局 i18n 触发）
    language_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        # 不调用 super().__init__()：具体 widget 子类的 __init__ 已负责 QObject 初始化。
        # 此处仅做主题订阅与初始应用。
        self._theme: M3ThemeManager = get_theme_manager()
        self._scheme: M3ColorScheme = self._theme.current_scheme()
        self._shape: M3ShapeTokens = self._theme.current_shape()
        # 订阅主题变化
        self._theme.theme_changed.connect(self._on_theme_changed)
        # 初始应用
        self.apply_theme(self._scheme, self._shape)

    def _on_theme_changed(
        self,
        scheme: M3ColorScheme,
        shape: M3ShapeTokens,
        motion,
    ):
        self._scheme = scheme
        self._shape = shape
        self.apply_theme(scheme, shape)
        self.update()

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens):
        """子类重写：应用新主题。默认实现为空。"""
        pass

    def retranslate_ui(self):
        """子类重写：刷新所有可见文本（语言切换时调用）。"""
        pass


# ════════════════════════════════════════════════════════════════════════
# StateLayerOverlay
# ════════════════════════════════════════════════════════════════════════


class StateLayerOverlay(QObject):
    """M3 状态层叠加。

    在父 widget 之上叠加一层半透明颜色，根据交互状态显示不同透明度：
        - hover:   8%
        - focus:   10%
        - pressed: 10%
        - dragged: 16%

    用法：作为父 widget 的子对象（QObject），监听父对象的事件。
    """

    def __init__(self, parent: QWidget, color_attr: str = "on_surface"):
        super().__init__(parent)
        self._parent = parent
        self._color_attr = color_attr  # scheme 上的属性名，如 "on_surface" / "on_primary"
        self._opacity: float = 0.0
        self._target_opacity: float = 0.0
        self._scheme = get_theme_manager().current_scheme()

        # 安装事件过滤器
        parent.installEventFilter(self)

        # 平滑动画
        self._anim = QPropertyAnimation(self, b"opacity")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 订阅主题
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, scheme, shape, motion):
        self._scheme = scheme
        if self._opacity > 0:
            self._parent.update()

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, v: float):
        self._opacity = v
        self._parent.update()

    def set_color_attr(self, attr: str):
        """切换状态层颜色对应的 scheme 属性"""
        self._color_attr = attr
        if self._opacity > 0:
            self._parent.update()

    def _set_target(self, target: float):
        if abs(self._target_opacity - target) < 0.001:
            return
        self._target_opacity = target
        self._anim.stop()
        self._anim.setStartValue(self._opacity)
        self._anim.setEndValue(target)
        self._anim.start()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._parent:
            return False

        t = event.type()
        if t == QEvent.Type.Enter:
            self._set_target(STATE_LAYER_HOVER)
        elif t == QEvent.Type.Leave:
            self._set_target(0.0)
        elif t == QEvent.Type.FocusIn:
            # focus 时叠加 10%，但保持 hover
            self._set_target(max(STATE_LAYER_FOCUS, self._target_opacity))
        elif t == QEvent.Type.FocusOut:
            self._set_target(STATE_LAYER_HOVER if self._is_hovered() else 0.0)
        elif t == QEvent.Type.MouseButtonPress:
            self._set_target(STATE_LAYER_PRESSED)
        elif t == QEvent.Type.MouseButtonRelease:
            self._set_target(STATE_LAYER_HOVER if self._is_hovered() else 0.0)

        return False

    def _is_hovered(self) -> bool:
        from PyQt6.QtGui import QEnterEvent
        pos = self._parent.mapFromGlobal(self._parent.cursor().pos())
        return self._parent.rect().contains(pos)

    def paint(self, painter: QPainter):
        """由父 widget 在 paintEvent 中调用"""
        if self._opacity < 0.001:
            return
        color = getattr(self._scheme, self._color_attr, "#000000")
        if not isinstance(color, QColor):
            if isinstance(color, str):
                c = QColor(color)
            else:
                c = QColor(*color)
        else:
            c = color
        c.setAlphaF(self._opacity)
        painter.fillRect(self._parent.rect(), c)


# ════════════════════════════════════════════════════════════════════════
# RippleOverlay
# ════════════════════════════════════════════════════════════════════════


class _Ripple:
    """单个涟漪实例。"""
    __slots__ = ("cx", "cy", "start_time", "max_radius", "color_attr")

    def __init__(self, cx: float, cy: float, max_radius: float, color_attr: str = "on_primary"):
        self.cx = cx
        self.cy = cy
        self.start_time = 0.0  # 由 RippleOverlay 设置
        self.max_radius = max_radius
        self.color_attr = color_attr


class RippleOverlay(QObject):
    """M3 涟漪效果。

    监听父 widget 的 MouseButtonPress，从鼠标位置扩散一个圆形涟漪，
    持续 600ms（M3 规范）后淡出。

    用法：
        self._ripple = RippleOverlay(self, color_attr="on_primary")
        # 父 widget 的 paintEvent 中调用：
        self._ripple.paint(painter)
    """

    DURATION_MS = 600  # 涟漪持续时间
    FADE_START = 0.6    # 60% 时间后开始淡出

    def __init__(self, parent: QWidget, color_attr: str = "on_primary"):
        super().__init__(parent)
        self._parent = parent
        self._color_attr = color_attr
        self._scheme = get_theme_manager().current_scheme()
        self._ripples: list[tuple[_Ripple, float, float]] = []  # [(ripple, elapsed, alpha)]
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)
        self._start_time = 0

        parent.installEventFilter(self)
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, scheme, shape, motion):
        self._scheme = scheme

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._parent:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position()
                # 计算到最远角的距离作为最大半径
                rect = self._parent.rect()
                corners = [
                    (rect.topLeft().x(), rect.topLeft().y()),
                    (rect.topRight().x(), rect.topRight().y()),
                    (rect.bottomLeft().x(), rect.bottomLeft().y()),
                    (rect.bottomRight().x(), rect.bottomRight().y()),
                ]
                max_r = max(
                    ((pos.x() - cx) ** 2 + (pos.y() - cy) ** 2) ** 0.5
                    for cx, cy in corners
                )
                ripple = _Ripple(pos.x(), pos.y(), max_r, self._color_attr)
                import time
                ripple.start_time = time.monotonic()
                self._ripples.append((ripple, 0.0, 0.12))  # 最大 alpha 12%
                if not self._timer.isActive():
                    self._timer.start()
        return False

    def _tick(self):
        import time
        now = time.monotonic()
        new_list = []
        for ripple, _, _ in self._ripples:
            elapsed = (now - ripple.start_time) * 1000  # ms
            if elapsed >= self.DURATION_MS:
                continue
            new_list.append((ripple, elapsed, 0.0))
        self._ripples = new_list
        if not self._ripples:
            self._timer.stop()
        self._parent.update()

    def paint(self, painter: QPainter):
        """由父 widget 在 paintEvent 中调用"""
        if not self._ripples:
            return
        import time
        now = time.monotonic()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for ripple, _, _ in self._ripples:
            elapsed_ms = (now - ripple.start_time) * 1000
            if elapsed_ms >= self.DURATION_MS:
                continue
            progress = elapsed_ms / self.DURATION_MS
            # 半径：ease-out 从 0 到 max_radius
            radius = ripple.max_radius * (1 - (1 - progress) ** 3)
            # alpha：前 60% 保持，后 40% 淡出
            if progress < self.FADE_START:
                alpha = 0.12
            else:
                fade_progress = (progress - self.FADE_START) / (1 - self.FADE_START)
                alpha = 0.12 * (1 - fade_progress)
            color = getattr(self._scheme, self._color_attr, "#000000")
            if isinstance(color, str):
                c = QColor(color)
            else:
                c = QColor(*color)
            c.setAlphaF(alpha)
            painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ripple.cx, ripple.cy), radius, radius)
