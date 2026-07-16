"""Tesseract OCR 安装后台线程。"""
from PyQt6.QtCore import QThread, pyqtSignal

from voirol.utils.i18n import t
from voirol.utils.logger import get_logger

logger = get_logger("gui.settings.workers.tesseract")


class TesseractInstallThread(QThread):
    """后台安装 Tesseract OCR 引擎及语言包。"""

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, mirror_url: str = "", parent=None):
        super().__init__(parent)
        self.mirror_url = mirror_url

    def run(self):
        try:
            from voirol.utils.tesseract_download import (
                download_tesseract_exe, extract_and_setup,
                download_tessdata, TESSEL_DIR,
            )

            self.status.emit(t("tesseract.downloading"))
            exe_path = download_tesseract_exe(
                progress_callback=lambda p: self.progress.emit(p),
                mirror_url=self.mirror_url,
            )
            self.progress.emit(100)
            self.status.emit(t("tesseract.extracting"))
            ok = extract_and_setup(exe_path, progress_callback=lambda p: self.progress.emit(p))
            if not ok:
                self.finished.emit(False)
                return

            self.status.emit(t("tesseract.downloading_lang", lang="eng"))
            download_tessdata("eng",
                progress_callback=lambda p: self.progress.emit(50 + p // 2),
                mirror_url=self.mirror_url,
            )
            self.status.emit(t("tesseract.downloading_lang", lang="chi_sim"))
            download_tessdata("chi_sim",
                progress_callback=lambda p: self.progress.emit(75 + p // 4),
                mirror_url=self.mirror_url,
            )
            self.progress.emit(100)
            self.finished.emit(True)
        except Exception as e:
            logger.error(f"Tesseract install failed: {e}")
            self.finished.emit(False)
