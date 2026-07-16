from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPen
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from voirol.gui.theme import get_theme_manager, M3ColorScheme, M3ShapeTokens, M3MotionTokens
from voirol.gui.tokens import _hex_to_qcolor
from voirol.utils.resources import app_font_family


class StartupSplash(QWidget):
    """M3 floating card splash — Google Sans title, circular + linear progress with shimmer."""

    W = 360
    H = 200

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.W // 2, screen.center().y() - self.H // 2)

        self._progress_pct = 0
        self._is_error = False
        self._angle = 0.0
        self._shimmer_t = 0.0

        # ── 主题感知：订阅 M3ThemeManager ──
        self._theme = get_theme_manager()
        self._colors: dict[str, QColor] = {}
        self._apply_theme(self._theme.current_scheme())
        self._theme.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(0)

        # VoirolClass wordmark
        self._title = QLabel("VoirolClass", self)
        title_font = QFont(app_font_family(), 11, QFont.Weight.Medium)
        title_font.setStyleStrategy(QFont.StyleStrategy.PreferQuality)
        self._title.setFont(title_font)
        layout.addWidget(self._title)

        # Subtitle
        self._subtitle = QLabel("语音控制教室辅助系统", self)
        self._subtitle.setFont(QFont(app_font_family(), 9))
        layout.addWidget(self._subtitle)

        layout.addSpacing(24)

        # Status row — spinner is painted in paintEvent; text here
        row = QHBoxLayout()
        row.setContentsMargins(28, 0, 0, 0)  # leave room for painted spinner
        row.setSpacing(12)

        self._status = QLabel(self)
        self._status.setFont(QFont(app_font_family(), 10))
        row.addWidget(self._status)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addSpacing(20)

        # Error detail label (hidden by default)
        self._error_details = QLabel(self)
        self._error_details.setFont(QFont(app_font_family(), 8))
        self._error_details.setWordWrap(True)
        self._error_details.setMaximumWidth(self.W - 64)
        self._error_details.hide()
        layout.addWidget(self._error_details)

        layout.addStretch(1)

        # 初始化标签样式（使用当前主题颜色）
        self._update_label_styles()

        # Animation tick — drives spinner rotation + shimmer sweep
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick_anim)
        self._anim_timer.start()

    # ── 主题感知 ──

    def _on_theme_changed(
        self, scheme: M3ColorScheme, shape: M3ShapeTokens, motion: M3MotionTokens
    ):
        """主题变化时更新颜色并重绘"""
        self._apply_theme(scheme)

    def _apply_theme(self, scheme: M3ColorScheme):
        """从 M3ColorScheme 提取所需 QColor 并更新 UI"""
        self._colors = {
            "primary": _hex_to_qcolor(scheme.primary),
            "surface_container_high": _hex_to_qcolor(scheme.surface_container_high),
            "surface_container_highest": _hex_to_qcolor(scheme.surface_container_highest),
            "on_surface": _hex_to_qcolor(scheme.on_surface),
            "on_surface_variant": _hex_to_qcolor(scheme.on_surface_variant),
            "error": _hex_to_qcolor(scheme.error),
        }
        if hasattr(self, "_title"):
            self._update_label_styles()
        self.update()

    def _update_label_styles(self):
        """更新所有 QLabel 的 stylesheet 以匹配当前主题"""
        c = self._colors
        self._title.setStyleSheet(
            f"font-size: 24px; font-weight: 500; color: {c['on_surface'].name()}; "
            "letter-spacing: -0.3px; background: transparent;"
        )
        self._subtitle.setStyleSheet(
            f"font-size: 13px; color: {c['on_surface_variant'].name()}; "
            "background: transparent; margin-top: 4px;"
        )
        if self._is_error:
            self._status.setStyleSheet(
                f"font-size: 14px; color: {c['error'].name()}; background: transparent;"
            )
        else:
            self._status.setStyleSheet(
                f"font-size: 14px; color: {c['on_surface_variant'].name()}; background: transparent;"
            )
        self._error_details.setStyleSheet(
            f"font-size: 11px; color: {c['error'].name()}; padding: 4px 0 0 0; background: transparent;"
        )

    def _tick_anim(self):
        # M3 circular spinner: 360° per 1.4s linear
        self._angle = (self._angle + 360.0 * 16.0 / 1400.0) % 360.0
        # shimmer: 1.6s ease-in-out sweep
        self._shimmer_t = (self._shimmer_t + 16.0 / 1600.0) % 1.0
        self.update()

    def set_status(self, text: str):
        self._status.setText(text)
        self._progress_pct = min(100, self._progress_pct + 18)
        self.update()
        QApplication.processEvents()

    def set_error(self, text: str):
        self._is_error = True
        self._status.setStyleSheet(
            f"font-size: 14px; color: {self._colors['error'].name()}; background: transparent;"
        )
        self._error_details.setText(text)
        self._error_details.show()
        self.update()
        QApplication.processEvents()

    def close_with_delay(self, ms: int = 500):
        QTimer.singleShot(ms, self.close)

    def paintEvent(self, event: QPaintEvent):
        from PyQt6.QtCore import QPointF

        c = self._colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = 16.0

        # ── M3 floating card: surface-container-high, radius-lg, elevation-3 ──
        # Use QRectF throughout — QPainter.drawRoundedRect/fillPath accept floats,
        # and QRectF.translated() supports float offsets (QRect doesn't).
        card_rect = QRectF(rect).adjusted(0, 0, -1, -1)

        # elevation shadow (soft, multi-layer approximating M3 elevation-3)
        for (dy, spread, alpha) in [(4.0, 1.6, 46), (1.5, 0.8, 77)]:
            shadow_color = QColor(0, 0, 0, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            path = QPainterPath()
            shadow_rect = card_rect.translated(0, dy).adjusted(
                -spread, -spread * 0.4, spread, spread * 0.4
            )
            path.addRoundedRect(shadow_rect, radius, radius)
            painter.fillPath(path, shadow_color)

        # Card surface fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c["surface_container_high"])
        painter.drawRoundedRect(card_rect, radius, radius)

        # ── Circular M3 progress spinner (left of status text) ──
        if not self._is_error:
            spinner_cx = 32 + 12
            spinner_cy = 32 + self._title.height() + 4 + self._subtitle.height() + 24 + 12
            r = 11.0
            # track
            painter.setPen(QPen(c["surface_container_highest"], 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(spinner_cx, spinner_cy), r, r)
            # arc (270° sweep, rotating)
            painter.setPen(QPen(c["primary"], 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            start = int(self._angle * 16)
            span = int(270 * 16)
            painter.drawArc(
                int(spinner_cx - r), int(spinner_cy - r), int(r * 2), int(r * 2),
                -start, -span,
            )

        # ── Linear progress bar at bottom (4px track) ──
        bar_y = self.H - 24
        bar_x = 32
        bar_w = self.W - 64
        bar_h = 4
        # track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c["surface_container_highest"])
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 2, 2)

        if self._progress_pct > 0:
            fill_w = int(bar_w * self._progress_pct / 100.0)
            # fill
            painter.setBrush(c["primary"])
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)
            # shimmer sweep across the fill
            if fill_w > 8 and not self._is_error:
                shimmer_x = bar_x + (self._shimmer_t - 0.5) * fill_w * 2
                grad = QLinearGradient(shimmer_x - 20, 0, shimmer_x + 20, 0)
                grad.setColorAt(0.0, QColor(255, 255, 255, 0))
                grad.setColorAt(0.5, QColor(255, 255, 255, 115))
                grad.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setBrush(grad)
                painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)

        # progress percentage (right-aligned, above bar)
        if self._progress_pct > 0:
            painter.setPen(c["on_surface_variant"])
            painter.setFont(QFont(app_font_family(), 9))
            pct_text = f"{self._progress_pct}%"
            painter.drawText(
                bar_x, bar_y - 6, bar_w, 14,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                pct_text,
            )

        painter.end()
