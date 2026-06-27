import sys

import numpy as np

from voirol.core.config import load_config
from voirol.core.pipeline import VoicePipeline
from voirol.gui.theme import Theme, apply_theme, detect_system_theme
from voirol.gui.tray import create_tray_icon
from voirol.utils.i18n import state_name, t
from voirol.utils.logger import get_logger, setup_file_logger
from voirol.voice.model_download import check_model_status

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

    missing = [mid for mid in ["silero_vad", "sensevoice", "vosk_zh", "vosk_en"]
               if check_model_status(mid) == "missing"]
    if missing:
        logger.warning(f"Models not downloaded: {', '.join(missing)}")
        print(t("app.model_missing_hint"))

    from PyQt6.QtGui import QFont, QFontDatabase, QSurfaceFormat
    from PyQt6.QtWidgets import QApplication

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setApplicationName("VoirolClass")
    app.setQuitOnLastWindowClosed(False)

    cfg_theme = config.ui.get("theme", "system")
    if cfg_theme == "system":
        theme = detect_system_theme()
    else:
        theme = Theme(cfg_theme)
    apply_theme(app, theme, config.ui.get("border_radius", 5))

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

    from voirol.gui.indicator import ListeningIndicator
    indicator = ListeningIndicator()
    indicator.show()
    pipeline.on_state_change(lambda s: indicator.set_state(s))
    pipeline.on_audio_level(lambda lv: indicator.set_level(lv))

    print(t("app.running"))
    print(t("app.running_hint") + "\n")

    exit_code = app.exec()

    pipeline.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
