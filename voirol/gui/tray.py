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

    icon = _create_icon()
    tray.setIcon(icon)
    tray.setToolTip(t("app.tooltip"))

    menu = _create_menu(app, pipeline)
    tray.setContextMenu(menu)

    tray.show()
    return tray, menu


def _create_icon():
    return QIcon("assets/img/icon.png")


def _create_menu(app: QApplication, pipeline: VoicePipeline):
    menu = QMenu()

    active = pipeline.verifier.get_active_name()
    status_key = "status.teacher" if active else "status.idle"
    menu._status_action = QAction(t(status_key, active=active or ""))
    menu._status_action.setEnabled(False)
    menu.addAction(menu._status_action)

    menu.addSeparator()

    menu._settings_action = QAction(t("settings.menu"))
    menu._settings_action.triggered.connect(
        lambda: _show_settings_dialog(pipeline)
    )
    menu.addAction(menu._settings_action)

    menu.addSeparator()

    menu._mute_action = QAction(t("mute.on"))
    menu._mute_action.setCheckable(True)
    menu._mute_action.triggered.connect(
        lambda checked: _toggle_mute(pipeline, menu._mute_action)
    )
    menu.addAction(menu._mute_action)

    menu.addSeparator()

    menu._quit_action = QAction(t("quit"))
    menu._quit_action.triggered.connect(app.quit)
    menu.addAction(menu._quit_action)

    return menu


def _toggle_mute(pipeline: VoicePipeline, action: QAction):
    pipeline.muted = not pipeline.muted
    if pipeline.muted:
        action.setText(t("mute.off"))
        logger.info("Muted")
    else:
        action.setText(t("mute.on"))
        logger.info("Unmuted")
