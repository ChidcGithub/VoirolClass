from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voirol.gui.theme import M3ColorScheme
from voirol.utils.i18n import t
from voirol.utils.resources import app_font_family


def _get_scheme() -> M3ColorScheme:
    """获取当前主题方案，失败时返回硬编码兜底（崩溃对话框需要高可靠）"""
    try:
        from voirol.gui.theme import get_theme_manager
        return get_theme_manager().current_scheme()
    except Exception:
        from voirol.gui.theme import _fallback_scheme
        return _fallback_scheme(True, "#A8C7FA")


class CrashDialog(QDialog):
    """M3 basic dialog — error icon, title, message, scrollable traceback, M3 buttons."""

    def __init__(self, details: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("crash.title"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 440)

        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

        self._details = details

        # 从当前主题获取颜色（崩溃对话框读取一次即可，无需订阅实时切换）
        s = _get_scheme()

        # ── Main layout: full-viewport scrim + centered card ──
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Card container (centered)
        card = QFrame()
        card.setObjectName("crashCard")
        card.setStyleSheet(f"""
            QFrame#crashCard {{
                background-color: {s.surface_container_high};
                border-radius: 16px;
                border: 1px solid {s.outline_variant};
            }}
        """)
        card.setFixedSize(520, 400)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 20)
        card_layout.setSpacing(0)

        # Error icon (filled circle with !)
        icon_label = QLabel("✕", card)
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {s.error};
                color: {s.on_error};
                border-radius: 18px;
                font-size: 18px;
                font-weight: bold;
            }}
        """)
        card_layout.addWidget(icon_label)
        card_layout.addSpacing(16)

        # Title
        title = QLabel(t("crash.title"), card)
        title_font = QFont(app_font_family(), 14, QFont.Weight.Medium)
        title_font.setStyleStrategy(QFont.StyleStrategy.PreferQuality)
        title.setFont(title_font)
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 500; color: {s.on_surface}; background: transparent;"
        )
        card_layout.addWidget(title)

        # Message
        msg = QLabel(t("crash.message"), card)
        msg.setFont(QFont(app_font_family(), 10))
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"font-size: 14px; color: {s.on_surface_variant}; background: transparent; margin-top: 8px;"
        )
        card_layout.addWidget(msg)
        card_layout.addSpacing(16)

        # Traceback container (M3 static surface — border-led)
        self._text = QPlainTextEdit(card)
        self._text.setReadOnly(True)
        self._text.setPlainText(details)
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                font-family: 'Roboto Mono', 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: {s.surface_container};
                color: {s.on_surface_variant};
                border: 1px solid {s.outline_variant};
                border-radius: 8px;
                padding: 12px;
                selection-background-color: {s.outline_variant};
            }}
        """)
        card_layout.addWidget(self._text)
        card_layout.addSpacing(20)

        # Button row (right-aligned)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        copy_btn = QPushButton(t("crash.copy"), card)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {s.primary};
                border: 1px solid {s.outline};
                border-radius: 9999px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {s.surface_container_high};
                color: {s.on_surface};
            }}
            QPushButton:pressed {{
                background-color: {s.surface_container};
            }}
        """)
        copy_btn.clicked.connect(self._on_copy)
        btn_row.addWidget(copy_btn)

        exit_btn = QPushButton(t("quit"), card)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {s.error};
                color: {s.on_error};
                border: none;
                border-radius: 9999px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {s.error_container};
                color: {s.on_error_container};
            }}
            QPushButton:pressed {{
                background-color: {s.on_error};
                color: {s.error};
            }}
        """)
        exit_btn.clicked.connect(QApplication.instance().quit)
        btn_row.addWidget(exit_btn)

        card_layout.addLayout(btn_row)

        outer.addStretch()
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

    def _on_copy(self):
        QApplication.clipboard().setText(self._details)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Scrim — dim the desktop behind the dialog (M3 scrim 0.32)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 82))

        painter.end()
