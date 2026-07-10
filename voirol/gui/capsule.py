import struct
from collections import deque
from ctypes import c_void_p

import numpy as np
from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtProperty,
)
from PyQt6.QtGui import QFont, QImage, QPainter, QColor
from PyQt6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import (
    glGenTextures, glDeleteTextures, glBindTexture, glTexImage2D,
    glTexParameteri, glActiveTexture,
    GL_TEXTURE0, GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
    GL_CLAMP_TO_EDGE, GL_NEAREST,
)
from PyQt6.QtWidgets import QApplication

from voirol.core.pipeline import PipelineState
from voirol.gui.shaders import VERTEX_SHADER, CAPSULE_FRAGMENT

GL_FLOAT = 0x1406
GL_TRIANGLE_STRIP = 0x0005
GL_COLOR_BUFFER_BIT = 0x00004000

_TEXT_CACHE_MAX = 8
_TEXT_CANVAS_W = 880
_TEXT_CANVAS_H = 104


class CapsuleWidget(QOpenGLWidget):
    _state_signal = pyqtSignal(int)
    _level_signal = pyqtSignal(float)

    IDLE_W = 68
    IDLE_H = 7
    EXPAND_W = 440
    EXPAND_H = 52

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(False)

        cx = QApplication.primaryScreen().geometry().width() // 2
        self._idle_geo = QRect(cx - self.IDLE_W // 2, 0, self.IDLE_W, self.IDLE_H)
        self._expand_geo = QRect(cx - self.EXPAND_W // 2, 0, self.EXPAND_W, self.EXPAND_H)

        self._state_signal.connect(self._on_state)
        self._level_signal.connect(self._on_level)

        self._state = 0
        self._levels = [0.0, 0.0, 0.0]
        self._smooth_levels = [0.0, 0.0, 0.0]
        self._level_history: deque[float] = deque([0.0, 0.0, 0.0], maxlen=3)
        self._alpha = 0.35
        self._trans_value = 0.0
        self._text_alpha = 0.0
        self._show_text = 0
        self._texture_id = 0
        self._texture_w = 1
        self._texture_h = 1

        # texture cache: text → (tex_id, w, h)
        self._tex_cache: dict[str, tuple[int, int, int]] = {}
        self._tex_cache_order: list[str] = []

        self._response_timer = QTimer(self)
        self._response_timer.setSingleShot(True)
        self._response_timer.timeout.connect(self._on_response_timeout)

        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(16)
        self._fade_timer.timeout.connect(self._tick_fade)

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._trans_anim = QPropertyAnimation(self, b"trans_value")
        self._trans_anim.setDuration(380)
        self._trans_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._vao: QOpenGLVertexArrayObject | None = None
        self._tick = 0

        self.setGeometry(self._idle_geo)

    @pyqtProperty(float)
    def trans_value(self) -> float:
        return self._trans_value

    @trans_value.setter
    def trans_value(self, v: float):
        self._trans_value = v

    def set_state(self, state: PipelineState):
        si = 0 if state == PipelineState.IDLE else (1 if state == PipelineState.LISTENING else 2)
        self._state_signal.emit(si)

    def set_level(self, level: float):
        self._level_signal.emit(max(0.0, min(1.0, level)))

    def set_recognized(self, text: str):
        self._upload_text(text)
        self._show_text = 1
        self._text_alpha = 0.0
        self._fade_timer.start()

    def set_response(self, text: str):
        self._upload_text(text)
        self._show_text = 1
        self._text_alpha = 0.0
        self._fade_timer.start()
        self._response_timer.start(5000)

    def _upload_text(self, text: str):
        key = text
        if key in self._tex_cache:
            self._texture_id, self._texture_w, self._texture_h = self._tex_cache[key]
            return
        img = QImage(_TEXT_CANVAS_W, _TEXT_CANVAS_H, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont()
        if len(text) < 20:
            f.setPixelSize(22)
        else:
            f.setPixelSize(16)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        p.end()

        ptr = img.bits()
        ptr.setsize(img.width() * img.height() * 4)
        tid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width(), img.height(), 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, c_void_p(int(ptr)))
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        self._texture_id = tid
        self._texture_w = img.width()
        self._texture_h = img.height()

        self._tex_cache[key] = (tid, img.width(), img.height())
        self._tex_cache_order.append(key)
        while len(self._tex_cache_order) > _TEXT_CACHE_MAX:
            old = self._tex_cache_order.pop(0)
            if old != key:
                oid, _, _ = self._tex_cache.pop(old, (0, 0, 0))
                if oid:
                    glDeleteTextures(1, oid)

    def _tick_fade(self):
        if self._text_alpha < 1.0 and self._show_text:
            self._text_alpha = min(1.0, self._text_alpha + 0.05)
            self.update()
        elif self._text_alpha >= 1.0:
            self._fade_timer.stop()
        elif self._text_alpha > 0.0 and not self._show_text:
            self._text_alpha = max(0.0, self._text_alpha - 0.04)
            self.update()
            if self._text_alpha <= 0.0:
                self._fade_timer.stop()
                self._texture_id = 0
                self.update()

    def _on_response_timeout(self):
        self._show_text = 0
        self._fade_timer.start()

    # ── OpenGL ──

    def initializeGL(self):
        from OpenGL.GL import glClearColor
        glClearColor(0.0, 0.0, 0.0, 0.0)

        self._program = QOpenGLShaderProgram()
        vs = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Vertex)
        vs.compileSourceCode(VERTEX_SHADER)
        fs = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Fragment)
        fs.compileSourceCode(CAPSULE_FRAGMENT)
        self._program.addShader(vs)
        self._program.addShader(fs)
        self._program.bindAttributeLocation("a_position", 0)
        self._program.link()

        self._vao = QOpenGLVertexArrayObject()
        self._vao.create()
        self._vao.bind()
        data = struct.pack('8f', -1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0)
        self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._vbo.create()
        self._vbo.bind()
        self._vbo.allocate(data, len(data))
        self._program.bind()
        self._program.enableAttributeArray("a_position")
        self._program.setAttributeBuffer("a_position", GL_FLOAT, 0, 2, 0)
        self._program.release()
        self._vao.release()
        self._vbo.release()

    def resizeGL(self, w: int, h: int):
        from OpenGL.GL import glViewport
        glViewport(0, 0, w, h)

    def paintGL(self):
        from OpenGL.GL import glClear, glDrawArrays
        glClear(GL_COLOR_BUFFER_BIT)

        self._program.bind()
        self._program.setUniformValue("u_resolution", float(self.width()), float(self.height()))
        self._program.setUniformValue("u_time", self._tick / 60.0)
        self._program.setUniformValue("u_state", self._state)
        self._program.setUniformValue("u_levels", self._smooth_levels[0], self._smooth_levels[1], self._smooth_levels[2])
        self._program.setUniformValue("u_transition", self._trans_value)
        self._program.setUniformValue("u_show_text", self._show_text if self._texture_id else 0)
        self._program.setUniformValue("u_text_alpha", self._text_alpha)

        if self._show_text and self._texture_id:
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._texture_id)
            self._program.setUniformValue("u_text", 0)

        self._vao.bind()
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self._vao.release()
        self._program.release()

        self._tick += 1

    # ── Qt signals ──

    def _on_state(self, si: int):
        prev = self._state
        self._state = si

        if si == 0:
            self._show_text = 0
            self._response_timer.stop()

        target = 1.0 if si != 0 else 0.0
        if abs(self._trans_value - target) > 0.001:
            self._trans_anim.stop()
            self._trans_anim.setStartValue(self._trans_value)
            self._trans_anim.setEndValue(target)
            self._trans_anim.start()

        target_geo = self._expand_geo if si != 0 else self._idle_geo
        if self.geometry() != target_geo:
            self._anim.stop()
            self._anim.setEndValue(target_geo)
            self._anim.start()

    def _on_level(self, level: float):
        self._level_history.appendleft(level)
        self._levels = list(self._level_history)

    # ── tick ──

    def tick_levels(self):
        for i in range(3):
            self._smooth_levels[i] += (self._levels[i] - self._smooth_levels[i]) * self._alpha
