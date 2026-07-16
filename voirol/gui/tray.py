from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidgetAction,
)

from voirol.core.pipeline import VoicePipeline
from voirol.gui.settings import _show_settings_dialog
from voirol.gui.theme import get_theme_manager, M3ColorScheme, M3ShapeTokens, M3MotionTokens
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger
from voirol.utils.resources import app_font_family, resource_path

logger = get_logger("gui.tray")


def _tray_qss(s: M3ColorScheme) -> str:
    """从 M3ColorScheme 动态生成托盘菜单 QSS"""
    return f"""
QMenu {{
    background-color: {s.surface_container};
    border: 1px solid {s.outline_variant};
    border-radius: 8px;
    padding: 8px 0;
    min-width: 240px;
}}
QMenu::item {{
    background-color: transparent;
    color: {s.on_surface};
    padding: 10px 16px 10px 14px;
    margin: 0 8px;
    border-radius: 6px;
    font-size: 14px;
}}
QMenu::item:selected {{
    background-color: {s.surface_container_highest};
}}
QMenu::item:disabled {{
    color: {s.on_surface_variant};
}}
QMenu::separator {{
    height: 1px;
    background-color: {s.outline_variant};
    margin: 6px 12px;
}}
QMenu::icon {{
    padding-left: 4px;
}}
"""


_HEADER_QSS = """
QFrame#trayHeader {
    background: transparent;
    border: none;
}
"""


class _ClickableLabel(QLabel):
    """A QLabel that emits `clicked` on left mouse press (for custom-colored menu items)."""

    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._hover_color: str = "#36343B"

    def set_hover_color(self, hex_color: str):
        self._hover_color = hex_color

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(self._base_style + f"background-color: {self._hover_color};")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._base_style)
        super().leaveEvent(event)


def create_tray_icon(
    app: QApplication,
    pipeline: VoicePipeline,
) -> tuple[QSystemTrayIcon, QMenu]:
    tray = QSystemTrayIcon()
    icon = QIcon(resource_path("assets/img/icon.png"))
    tray.setIcon(icon)
    tray.setToolTip(t("app.tooltip"))

    menu = _create_menu(app, pipeline)
    tray.setContextMenu(menu)
    tray.show()
    return tray, menu


def _build_header_widget(running: bool, s: M3ColorScheme) -> tuple[QFrame, QLabel, QLabel, QLabel]:
    """Build the M3 tray header: [status dot] [VoirolClass] [stretch] [status text]."""
    frame = QFrame()
    frame.setObjectName("trayHeader")
    frame.setStyleSheet(_HEADER_QSS)

    lay = QHBoxLayout(frame)
    lay.setContentsMargins(16, 10, 16, 10)
    lay.setSpacing(10)

    # Status dot — primary when running, outline when stopped
    dot = QLabel()
    dot.setFixedSize(10, 10)
    dot_color = s.primary if running else s.outline
    dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 5px;")
    lay.addWidget(dot)

    # Title
    title = QLabel("VoirolClass")
    title_font = title.font()
    title_font.setFamily(app_font_family())
    title_font.setBold(True)
    title_font.setPointSize(10)
    title.setFont(title_font)
    title.setStyleSheet(f"color: {s.on_surface}; background: transparent;")
    lay.addWidget(title)

    lay.addStretch(1)

    # Status text
    status_text = t("status.running") if running else t("status.stopped")
    status = QLabel(status_text)
    status_color = s.primary if running else s.on_surface_variant
    status.setStyleSheet(
        f"color: {status_color}; background: transparent; font-size: 12px;"
    )
    lay.addWidget(status)

    return frame, dot, title, status


def _create_menu(app: QApplication, pipeline: VoicePipeline):
    theme = get_theme_manager()
    scheme = theme.current_scheme()

    menu = QMenu()
    menu.setStyleSheet(_tray_qss(scheme))

    running = pipeline.is_running

    # ── Header (widget action, non-interactive) ──
    header_frame, dot_label, title_label, status_label = _build_header_widget(running, scheme)
    header_action = QWidgetAction(menu)
    header_action.setDefaultWidget(header_frame)
    menu.addAction(header_action)

    menu.addSeparator()

    # ── Settings ──
    menu._settings_action = QAction(t("settings.menu"))
    menu._settings_action.triggered.connect(lambda: _show_settings_dialog(pipeline))
    menu.addAction(menu._settings_action)

    # ── Start/Stop service ──
    menu._service_action = QAction(t("service.stop") if running else t("service.start"))
    menu._service_action.triggered.connect(lambda: _toggle_service(pipeline, menu))
    menu.addAction(menu._service_action)

    menu.addSeparator()

    # ── Quit (destructive — error-colored clickable label) ──
    quit_label = _ClickableLabel(t("quit"))
    quit_font = quit_label.font()
    quit_font.setFamily(app_font_family())
    quit_font.setPointSize(10)
    quit_label.setFont(quit_font)
    quit_label.set_hover_color(scheme.surface_container_highest)
    base_style = (
        f"color: {scheme.error}; background: transparent;"
        "padding: 10px 16px 10px 14px; margin: 0 8px; border-radius: 6px;"
    )
    quit_label._base_style = base_style
    quit_label.setStyleSheet(base_style)
    quit_action = QWidgetAction(menu)
    quit_action.setDefaultWidget(quit_label)
    quit_label.clicked.connect(app.quit)
    menu.addAction(quit_action)

    # keep references for status updates + theme switching
    menu._pipeline = pipeline
    menu._header_dot = dot_label
    menu._header_status = status_label
    menu._quit_label = quit_label
    menu._theme = theme

    # 订阅主题变化
    theme.theme_changed.connect(
        lambda s, sh, m: _on_tray_theme_changed(menu, s)
    )

    return menu


def _on_tray_theme_changed(menu: QMenu, scheme: M3ColorScheme):
    """主题变化时更新托盘菜单 QSS 和各组件颜色"""
    menu.setStyleSheet(_tray_qss(scheme))

    # 更新 quit label 颜色
    ql = menu._quit_label
    ql.set_hover_color(scheme.surface_container_highest)
    ql._base_style = (
        f"color: {scheme.error}; background: transparent;"
        "padding: 10px 16px 10px 14px; margin: 0 8px; border-radius: 6px;"
    )
    ql.setStyleSheet(ql._base_style)

    # 更新 header 颜色（重新构建）
    running = menu._pipeline.is_running
    _, dot, title, status = _build_header_widget(running, scheme)
    menu._header_dot.setStyleSheet(dot.styleSheet())
    menu._header_status.setStyleSheet(status.styleSheet())


def _toggle_service(pipeline: VoicePipeline, menu: QMenu):
    if pipeline.is_running:
        pipeline.stop()
        menu._service_action.setText(t("service.start"))
        _update_header(menu, running=False)
        logger.info("Service stopped")
    else:
        try:
            pipeline.start()
            menu._service_action.setText(t("service.stop"))
            _update_header(menu, running=True)
            logger.info("Service started")
        except Exception as e:
            logger.error(f"Failed to start service: {e}")


def _update_header(menu: QMenu, running: bool):
    """Update the header status dot + text after service toggle."""
    s = menu._theme.current_scheme()
    dot_color = s.primary if running else s.outline
    menu._header_dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 5px;")
    status_text = t("status.running") if running else t("status.stopped")
    menu._header_status.setText(status_text)
    status_color = s.primary if running else s.on_surface_variant
    menu._header_status.setStyleSheet(
        f"color: {status_color}; background: transparent; font-size: 12px;"
    )
