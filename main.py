import sys

import numpy as np

from voirol.core.config import load_config
from voirol.core.pipeline import VoicePipeline
from voirol.gui.tray import create_tray_icon
from voirol.utils.i18n import state_name, t
from voirol.utils.logger import get_logger, setup_file_logger
from voirol.voice.models import ensure_silero_vad

logger = get_logger("main")


def main():
    print(f"""
    ╔══════════════════════════════════════╗
    ║         {t('app.banner_line1')}           ║
    ║       {t('app.banner_line2')}          ║
    ╚══════════════════════════════════════╝
    """)

    config = load_config()

    if config.logging.get("file"):
        setup_file_logger(
            config.logging["file"],
            config.logging.get("level", "INFO"),
        )

    logger.info("Starting VoirolClass...")

    logger.info("Ensuring Silero VAD model...")
    try:
        ensure_silero_vad("models")
    except Exception as e:
        logger.error(f"Failed to get VAD model: {e}")
        print(t("app.download_error", e=e))
        input(t("app.press_enter"))
        return

    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("VoirolClass")
    app.setQuitOnLastWindowClosed(False)

    font_id = QFontDatabase.addApplicationFont("fonts/GSF.ttf")
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], config.ui.get("font_size", 13)))

    pipeline = VoicePipeline(config)

    if not pipeline.verifier.get_active_name():
        teachers = pipeline.enrollment.list_profiles()
        if teachers:
            first = teachers[0]
            pipeline.set_teacher(first)
            logger.info(f"Auto-selected first teacher: {first}")
        else:
            logger.warning("No teacher enrolled. Use tray menu to register.")
            print(t("app.startup_no_teacher"))
            print(t("app.startup_hint"))

    pipeline.start()

    ptt_key = config.hotkey.get("push_to_talk", "ctrl+alt+v")
    pipeline.setup_hotkeys(ptt_key)

    tray, tray_menu = create_tray_icon(app, pipeline)

    def update_tray_state(state):
        tray_menu._status_action.setText(state_name(state.value))
    pipeline.on_state_change(update_tray_state)

    print(t("app.running"))
    print(t("app.running_hint") + "\n")

    exit_code = app.exec()

    pipeline.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
