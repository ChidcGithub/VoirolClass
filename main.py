import multiprocessing
import os
import sys
import traceback

import numpy as np

from voirol.core.config import load_config
from voirol.core.pipeline import VoicePipeline
from voirol.gui.theme import Theme, apply_theme, detect_system_theme
from voirol.gui.tray import create_tray_icon
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger, setup_logger
from voirol.utils.resources import resource_path
from voirol.voice.model_download import check_model_status

logger = get_logger("main")

pipeline: VoicePipeline | None = None

_LOG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "VoirolClass", "logs",
)


def main():
    multiprocessing.freeze_support()

    if len(sys.argv) >= 2 and sys.argv[1] == "--splash":
        _run_splash(int(sys.argv[2]))
        return

    # Logger first — before any project code
    setup_logger(log_dir=_LOG_DIR, level=os.environ.get("VOIROL_LOG_LEVEL", "INFO"))

    config = load_config()

    # Re-apply with config values (dedup by handler type, no duplicates)
    setup_logger(
        log_dir=_LOG_DIR,
        level=config.logging.get("level", "INFO"),
    )

    print(f"""
    ╔══════════════════════════════════════╗
    ║         {t('app.banner_line1')}           ║
    ║       {t('app.banner_line2')}          ║
    ╚══════════════════════════════════════╝
    """)

    logger.info("Starting VoirolClass...")

    missing = [mid for mid in ["silero_vad", "sensevoice"]
               if check_model_status(mid) == "missing"]
    if missing:
        logger.warning(f"Models not downloaded: {', '.join(missing)}")
        print(t("app.model_missing_hint"))

    from PyQt6.QtGui import QFont, QFontDatabase, QSurfaceFormat
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("VoirolClass")
    app.setQuitOnLastWindowClosed(False)

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    def _crash_handler(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(f"Unhandled exception: {details}")
        global pipeline
        if pipeline:
            try:
                pipeline.stop()
            except Exception:
                pass
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication
        qapp = QApplication.instance()
        if qapp is not None:
            thread = QThread.currentThread()
            if thread == qapp.thread():
                from voirol.gui.crash_dialog import CrashDialog
                try:
                    CrashDialog(details).exec()
                except Exception:
                    pass
        sys.exit(1)

    sys.excepthook = _crash_handler

    from voirol.gui.splash_spawn import SplashProcess
    splash = SplashProcess()
    splash.set_status(t("splash.starting"))

    global pipeline
    pipeline = None
    try:
        cfg_theme = config.ui.get("theme", "system")
        if cfg_theme == "system":
            theme = detect_system_theme()
        else:
            theme = Theme(cfg_theme)
        apply_theme(app, theme, config.ui.get("border_radius", 5))

        font_id = QFontDatabase.addApplicationFont(resource_path("fonts/GSF.ttf"))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], config.ui.get("font_size", 13)))

        splash.set_status(t("splash.voice_engine"))

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

        if check_model_status("silero_vad") != "missing":
            pipeline.start()
        else:
            logger.info("VAD model not found — service not started. Start manually after download.")

        splash.set_status(t("splash.hotkeys"))

        ptt_key = config.hotkey.get("push_to_talk", "ctrl+alt+v")
        if pipeline.is_running:
            pipeline.setup_hotkeys(ptt_key)

        splash.set_status(t("splash.interface"))

        tray, tray_menu = create_tray_icon(app, pipeline)

        splash.set_status(t("splash.ready"))

        from voirol.gui.capsule import ActivityCapsule
        capsule = ActivityCapsule()
        splash.close_with_delay(500)
        capsule.show()
        pipeline.on_state_change(lambda s: capsule.set_state(s))
        pipeline.on_audio_level(lambda lv: capsule.set_level(lv))
        pipeline.on_asr_text(lambda t: capsule.set_asr(t))
        pipeline.on_action(lambda t: capsule.set_action(t))
        pipeline.on_command(lambda c: capsule.set_action(c[4:]) if c.startswith(("nav:", "cmd:")) else None)

        print(t("app.running"))
        print(t("app.running_hint") + "\n")

    except Exception:
        logger.exception("Startup failed")
        splash.close()
        from voirol.gui.crash_dialog import CrashDialog
        CrashDialog(traceback.format_exc()).exec()

    exit_code = app.exec()

    if pipeline:
        pipeline.stop()
    try:
        import keyboard as kb
        kb.unhook_all()
    except Exception:
        pass
    sys.exit(exit_code)


def _run_splash(port: int):
    authkey_hex = sys.argv[3] if len(sys.argv) > 3 else ""
    authkey = bytes.fromhex(authkey_hex) if authkey_hex else b"voirol"
    from multiprocessing.connection import Client
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QSurfaceFormat
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    from voirol.gui.splash import StartupSplash
    splash = StartupSplash()
    splash.show()

    try:
        conn = Client(("localhost", port), authkey=authkey)
    except Exception:
        app.quit()
        sys.exit(1)

    close_pending = False

    def poll():
        nonlocal close_pending
        if conn.poll(0.01):
            try:
                msg = conn.recv()
                tp = msg.get("type")
                if tp == "status":
                    splash.set_status(msg.get("text", ""))
                elif tp == "error":
                    splash.set_error(msg.get("text", ""))
                elif tp == "close":
                    delay = msg.get("delay", 0)
                    if delay > 0 and not close_pending:
                        close_pending = True
                        QTimer.singleShot(delay, app.quit)
                    elif delay == 0:
                        app.quit()
            except (EOFError, ConnectionResetError):
                app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
