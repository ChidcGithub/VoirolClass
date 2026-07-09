from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel

from voirol.core.pipeline import PipelineState
from voirol.gui.base_indicator import BaseGlIndicatorWidget


class ListeningIndicator(BaseGlIndicatorWidget):
    _path_signal = pyqtSignal(str)

    EXPAND_W = 100
    BASE_H = 64

    def __init__(self):
        super().__init__()

        cx = self._screen_cx()
        self._idle_geo = QRect(cx - self.IDLE_W // 2, 0, self.IDLE_W, self.IDLE_H)
        self._expand_geo = QRect(cx - self.EXPAND_W // 2, 0, self.EXPAND_W, self.BASE_H)

        self._path_signal.connect(self._apply_path)

        self._path_label = QLabel(self)
        self._path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._path_label.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 160);
                color: white;
                font-size: 12px;
                padding: 3px 10px;
                border-radius: 4px;
            }
        """)
        self._path_label.setWordWrap(True)
        self._path_label.setMaximumWidth(400)
        self._path_label.hide()

        self.setGeometry(self._idle_geo)

    def set_path(self, text: str):
        self._path_signal.emit(text)

    def _on_idle(self):
        self._path_label.hide()

    def _apply_path(self, text: str):
        if not text or self._state == PipelineState.IDLE:
            self._path_label.hide()
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            return
        self._path_label.setText(text)
        label_h = min(self._path_label.sizeHint().height(), 28)
        self._path_label.setGeometry(
            0, self.height() - label_h - 2,
            self.width(), label_h,
        )
        self._path_label.show()

        needed_h = self.BASE_H + 6 + label_h
        if self.height() < needed_h:
            self.setFixedHeight(needed_h)
