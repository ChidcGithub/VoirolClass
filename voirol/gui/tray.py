from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from voirol.core.pipeline import VoicePipeline
from voirol.gui.settings import _show_settings_dialog
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger

logger = get_logger("gui.tray")


def create_tray_icon(
    app: QApplication,
    pipeline: VoicePipeline,
) -> tuple[QSystemTrayIcon, QMenu]:
    tray = QSystemTrayIcon()
    icon = QIcon("assets/img/icon.png")
    tray.setIcon(icon)
    tray.setToolTip(t("app.tooltip"))

    menu = _create_menu(app, pipeline)
    tray.setContextMenu(menu)
    tray.show()
    return tray, menu


def _create_menu(app: QApplication, pipeline: VoicePipeline):
    menu = QMenu()

    menu._status_action = QAction(t("status.running" if pipeline.is_running else "status.stopped"))
    menu._status_action.setEnabled(False)
    menu.addAction(menu._status_action)

    menu.addSeparator()

    menu._settings_action = QAction(t("settings.menu"))
    menu._settings_action.triggered.connect(lambda: _show_settings_dialog(pipeline))
    menu.addAction(menu._settings_action)

    menu.addSeparator()

    running = pipeline.is_running
    menu._service_action = QAction(t("service.stop") if running else t("service.start"))
    menu._service_action.triggered.connect(lambda: _toggle_service(pipeline, menu))
    menu.addAction(menu._service_action)

    menu.addSeparator()

    menu._quit_action = QAction(t("quit"))
    menu._quit_action.triggered.connect(app.quit)
    menu.addAction(menu._quit_action)

    return menu


def _toggle_service(pipeline: VoicePipeline, menu: QMenu):
    if pipeline.is_running:
        pipeline.stop()
        menu._service_action.setText(t("service.start"))
        menu._status_action.setText(t("status.stopped"))
        logger.info("Service stopped")
    else:
        try:
            pipeline.start()
            menu._service_action.setText(t("service.stop"))
            menu._status_action.setText(t("status.running"))
            logger.info("Service started")
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
