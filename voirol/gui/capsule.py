from collections import deque

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtProperty,
)
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from voirol.core.pipeline import PipelineState
from voirol.gui.gl_indicator import GLIndicator


class ActivityCapsule(QWidget):
    _state_signal = pyqtSignal(object)
    _level_signal = pyqtSignal(float)
    _asr_signal = pyqtSignal(str)
    _action_signal = pyqtSignal(str)
    _tts_signal = pyqtSignal(str)

    IDLE_W = 60
    IDLE_H = 4
    EXPAND_W = 360
    BASE_H = 68
    HIDE_DELAY_MS = 5000

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        screen = QApplication.primaryScreen().geometry()
        cx = screen.width() // 2
        self._idle_geo = QRect(cx - self.IDLE_W // 2, 0, self.IDLE_W, self.IDLE_H)
        self._expand_geo = QRect(cx - self.EXPAND_W // 2, 0, self.EXPAND_W, self.BASE_H)

        self._state_signal.connect(self._apply_state)
        self._level_signal.connect(self._apply_level)
        self._asr_signal.connect(self._apply_asr)
        self._action_signal.connect(self._apply_action)
        self._tts_signal.connect(self._apply_tts)

        self._state = PipelineState.IDLE
        self._levels = [0.0, 0.0, 0.0]
        self._smooth_levels = [0.0, 0.0, 0.0]
        self._level_history = deque([0.0, 0.0, 0.0], maxlen=3)
        self._alpha = 0.35
        self._trans_value = 0.0
        self._current_asr = ""
        self._current_action = ""
        self._hide_timer_active = False

        self._gl_widget = GLIndicator(self)

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._gl_widget)
        self.setLayout(layout)

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)

        self._trans_anim = QPropertyAnimation(self, b"trans_value")
        self._trans_anim.setDuration(400)
        self._trans_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

        self._update_timer = QTimer(self)
        self._update_timer.setInterval(40)
        self._update_timer.timeout.connect(self._tick)
        self._update_timer.start()

        self.setGeometry(self._idle_geo)

    @pyqtProperty(float)
    def trans_value(self):
        return self._trans_value

    @trans_value.setter
    def trans_value(self, v):
        self._trans_value = v
        self._gl_widget.set_transition(v)

    def set_state(self, state: PipelineState):
        self._state_signal.emit(state)

    def set_level(self, level: float):
        self._level_signal.emit(max(0.0, min(1.0, level)))

    def set_asr(self, text: str):
        self._asr_signal.emit(text)

    def set_action(self, text: str):
        self._action_signal.emit(text)

    def set_tts_status(self, text: str):
        self._tts_signal.emit(text)

    def _apply_state(self, state: PipelineState):
        self._state = state

        state_int = 0 if state == PipelineState.IDLE else (1 if state == PipelineState.LISTENING else 2)
        self._gl_widget.set_state(state_int)

        target = 1.0 if state != PipelineState.IDLE else 0.0
        self._trans_anim.stop()
        self._trans_anim.setStartValue(self._trans_value)
        self._trans_anim.setEndValue(target)
        self._trans_anim.start()

        target_geo = self._expand_geo if state != PipelineState.IDLE else self._idle_geo
        if self.geometry() != target_geo:
            self._anim.stop()
            self._anim.setEndValue(target_geo)
            self._anim.start()

        if state == PipelineState.IDLE:
            self._hide_timer.stop()
            self._hide_timer_active = False
            self._asr_label.hide()
            self._action_label.hide()
            self._current_asr = ""
            self._current_action = ""

    def _apply_level(self, level: float):
        self._level_history.appendleft(level)
        self._levels = list(self._level_history)

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
        self._action_label.setText(f"[TTS] {text}")
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
        cx = QApplication.primaryScreen().geometry().width() // 2
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
            cx = QApplication.primaryScreen().geometry().width() // 2
            self._expand_geo = QRect(cx - w // 2, 0, w, self.BASE_H)
            if self.geometry().height() != self.BASE_H:
                self._anim.stop()
                self._anim.setEndValue(self._expand_geo)
                self._anim.start()

    def _tick(self):
        for i in range(3):
            self._smooth_levels[i] += (self._levels[i] - self._smooth_levels[i]) * self._alpha
        self._gl_widget.set_levels(self._smooth_levels[:])