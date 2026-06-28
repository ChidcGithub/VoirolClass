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


class ListeningIndicator(QWidget):
    _state_signal = pyqtSignal(object)
    _level_signal = pyqtSignal(float)
    _path_signal = pyqtSignal(str)

    IDLE_W = 60
    IDLE_H = 4
    LISTEN_W = 120
    LISTEN_H = 82

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
        self._listen_geo = QRect(cx - self.LISTEN_W // 2, 10, self.LISTEN_W, self.LISTEN_H)

        self._state_signal.connect(self._apply_state)
        self._level_signal.connect(self._apply_level)
        self._path_signal.connect(self._apply_path)

        self._state = PipelineState.IDLE
        self._levels = [0.0, 0.0, 0.0]
        self._smooth_levels = [0.0, 0.0, 0.0]
        self._level_history = deque([0.0, 0.0, 0.0], maxlen=3)
        self._alpha = 0.35
        self._trans_value = 0.0

        self._gl_widget = GLIndicator(self)

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

    def set_path(self, text: str):
        self._path_signal.emit(text)

    def _apply_state(self, state: PipelineState):
        self._state = state

        state_int = 0 if state == PipelineState.IDLE else (1 if state == PipelineState.LISTENING else 2)
        self._gl_widget.set_state(state_int)

        target = 1.0 if state != PipelineState.IDLE else 0.0
        self._trans_anim.stop()
        self._trans_anim.setStartValue(self._trans_value)
        self._trans_anim.setEndValue(target)
        self._trans_anim.start()

        self._anim.stop()
        target_geo = self._listen_geo if state != PipelineState.IDLE else self._idle_geo
        if self.geometry() != target_geo:
            self._anim.setEndValue(target_geo)
            self._anim.start()

        if state == PipelineState.IDLE:
            self._path_label.hide()

    def _apply_level(self, level: float):
        self._level_history.appendleft(level)
        self._levels = list(self._level_history)

    def _apply_path(self, text: str):
        if not text or self._state == PipelineState.IDLE:
            self._path_label.hide()
            return
        self._path_label.setText(text)
        label_y = self.LISTEN_H + 6
        self._path_label.setGeometry(
            0, label_y,
            self.LISTEN_W, self._path_label.sizeHint().height(),
        )
        self._path_label.show()

    def _tick(self):
        for i in range(3):
            self._smooth_levels[i] += (self._levels[i] - self._smooth_levels[i]) * self._alpha
        self._gl_widget.set_levels(self._smooth_levels[:])
