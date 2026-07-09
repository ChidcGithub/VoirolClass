from PyQt6.QtCore import QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel

from voirol.core.pipeline import PipelineState
from voirol.gui.base_indicator import BaseGlIndicatorWidget


class ActivityCapsule(BaseGlIndicatorWidget):
    _asr_signal = pyqtSignal(str)
    _action_signal = pyqtSignal(str)
    _tts_signal = pyqtSignal(str)

    EXPAND_W = 360
    BASE_H = 68
    HIDE_DELAY_MS = 5000

    def __init__(self):
        super().__init__()

        cx = self._screen_cx()
        self._idle_geo = QRect(cx - self.IDLE_W // 2, 0, self.IDLE_W, self.IDLE_H)
        self._expand_geo = QRect(cx - self.EXPAND_W // 2, 0, self.EXPAND_W, self.BASE_H)

        self._asr_signal.connect(self._apply_asr)
        self._action_signal.connect(self._apply_action)
        self._tts_signal.connect(self._apply_tts)

        self._current_asr = ""
        self._current_action = ""
        self._hide_timer_active = False

        self._asr_label = QLabel(self)
        self._asr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._asr_label.setWordWrap(True)
        self._asr_label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 0px 12px;
            }
        """)
        self._asr_label.setMaximumWidth(self.EXPAND_W - 20)
        self._asr_label.hide()

        self._action_label = QLabel(self)
        self._action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._action_label.setWordWrap(True)
        self._action_label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: rgba(255, 255, 255, 180);
                font-size: 12px;
                padding: 0px 12px;
            }
        """)
        self._action_label.setMaximumWidth(self.EXPAND_W - 20)
        self._action_label.hide()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

        self.setGeometry(self._idle_geo)

    def set_asr(self, text: str):
        self._asr_signal.emit(text)

    def set_action(self, text: str):
        self._action_signal.emit(text)

    def set_tts_status(self, text: str):
        self._tts_signal.emit(text)

    def _on_idle(self):
        self._hide_timer.stop()
        self._hide_timer_active = False
        self._asr_label.hide()
        self._action_label.hide()
        self._current_asr = ""
        self._current_action = ""

    def _apply_asr(self, text: str):
        self._current_asr = text
        self._asr_label.setText(f'"{text}"')
        w = self.width()
        self._asr_label.setGeometry(6, 8, w - 12, 22)
        self._asr_label.show()
        self._refresh_expanded_size()
        self._restart_hide_timer()

    def _apply_action(self, text: str):
        self._current_action = text
        self._action_label.setText(text)
        w = self.width()
        label_top = 32 if self._asr_label.isVisible() else 8
        self._action_label.setGeometry(6, label_top, w - 12, 20)
        self._action_label.show()
        self._refresh_expanded_size()
        self._restart_hide_timer()

    def _apply_tts(self, text: str):
        from voirol.utils.i18n import t
        self._action_label.setText(f"{t('tts.tab')} {text}")
        w = self.width()
        label_top = 32 if self._asr_label.isVisible() else 8
        self._action_label.setGeometry(6, label_top, w - 12, 20)
        self._action_label.show()
        self._refresh_expanded_size()

    def _refresh_expanded_size(self):
        if self._state == PipelineState.IDLE:
            return
        lines = 0
        if self._asr_label.isVisible():
            lines += 1
        if self._action_label.isVisible():
            lines += 1
        needed_h = self.BASE_H + lines * 22
        w = self.width()
        cx = self._screen_cx()
        new_geo = QRect(cx - w // 2, 0, w, needed_h)
        if self.geometry() != new_geo:
            self._anim.stop()
            self._anim.setEndValue(new_geo)
            self._anim.start()
        self._expand_geo = new_geo

    def _restart_hide_timer(self):
        self._hide_timer.start(self.HIDE_DELAY_MS)
        self._hide_timer_active = True

    def _on_hide_timeout(self):
        self._hide_timer_active = False
        if self._state != PipelineState.IDLE:
            self._asr_label.hide()
            self._action_label.hide()
            self._current_asr = ""
            self._current_action = ""
            w = self.width()
            cx = self._screen_cx()
            self._expand_geo = QRect(cx - w // 2, 0, w, self.BASE_H)
            if self.geometry().height() != self.BASE_H:
                self._anim.stop()
                self._anim.setEndValue(self._expand_geo)
                self._anim.start()
