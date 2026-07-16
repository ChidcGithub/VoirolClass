import os
import sys


def resource_path(relative: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        relative,
    )


_GSF_FALLBACK = "Google Sans Flex"


def app_font_family() -> str:
    """Return the app-wide font family (set from fonts/GSF.ttf in main.py).

    Falls back to 'Google Sans Flex' if the QApplication/font isn't available yet.
    """
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            fam = app.font().family()
            if fam:
                return fam
    except Exception:
        pass
    return _GSF_FALLBACK
