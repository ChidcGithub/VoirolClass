import struct
import time
from ctypes import c_void_p

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
from PyQt6.QtGui import QVector3D
from PyQt6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication
from voirol.utils.resources import app_font_family
from OpenGL.GL import (
    glGenTextures, glBindTexture, glTexImage2D,
    glTexParameteri, glActiveTexture,
    GL_TEXTURE0, GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
)

from voirol.core.pipeline import PipelineState
from voirol.gui.shaders import VERTEX_SHADER, CAPSULE_FRAGMENT
from voirol.gui.theme import get_theme_manager, M3ColorScheme, M3ShapeTokens, M3MotionTokens

GL_FLOAT = 0x1406
GL_TRIANGLE_STRIP = 0x0005
GL_COLOR_BUFFER_BIT = 0x00004000

_TEXT_CANVAS_W = 880
_TEXT_CANVAS_H = 104


class CapsuleWidget(QOpenGLWidget):
    _state_signal = pyqtSignal(int)
    _level_signal = pyqtSignal(float)
    _text_signal = pyqtSignal(str, bool)

    # M3 规范尺寸：圆角 28dp (shape.xl)，展开高度 56dp (M3 Touch Target)
    IDLE_W = 64
    IDLE_H = 8
    EXPAND_W = 480
    EXPAND_H = 56

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
        self._text_signal.connect(self._on_text_update)

        self._state = 0
        self._target_level = 0.0
        self._smooth_level = 0.0
        self._trans_value = 0.0
        self._text_alpha = 0.0
        self._show_text = 0
        self._tex_id = 0
        self._tex_w = 1
        self._tex_h = 1
        self._pending_image: QImage | None = None
        self._text_needs_upload = False

        self._response_timer = QTimer(self)
        self._response_timer.setSingleShot(True)
        self._response_timer.timeout.connect(self._on_response_timeout)

        # geometry animation — M3 emphasized 缓动 + medium2 时长 (350ms)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuart)

        # transition value animation (drives shader morph)
        self._trans_anim = QPropertyAnimation(self, b"trans_value")
        self._trans_anim.setDuration(350)
        self._trans_anim.setEasingCurve(QEasingCurve.Type.OutQuart)

        # unified tick for level smoothing + text fade + shader time
        self._start_time = time.monotonic()
        self._last_tick = self._start_time
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._vao: QOpenGLVertexArrayObject | None = None

        # ── 主题感知：订阅 M3ThemeManager ──
        self._theme = get_theme_manager()
        self._palette: dict[str, tuple[float, float, float] | float] = self._theme.opengl_palette()
        self._theme.theme_changed.connect(self._on_theme_changed)

        self.setGeometry(self._idle_geo)

    @pyqtProperty(float)
    def trans_value(self) -> float:
        return self._trans_value

    @trans_value.setter
    def trans_value(self, v: float):
        self._trans_value = v

    # ── 主题切换 ──

    def _on_theme_changed(
        self, scheme: M3ColorScheme, shape: M3ShapeTokens, motion: M3MotionTokens
    ):
        """主题变化时更新 OpenGL 调色板并触发重绘"""
        self._palette = self._theme.opengl_palette()
        self.update()

    # ── public API ──

    def set_state(self, state: PipelineState):
        si = 0 if state == PipelineState.IDLE else (1 if state == PipelineState.LISTENING else 2)
        self._state_signal.emit(si)

    def set_level(self, level: float):
        self._level_signal.emit(max(0.0, min(1.0, level)))

    def set_recognized(self, text: str):
        self._text_signal.emit(text, False)

    def set_response(self, text: str):
        self._text_signal.emit(text, True)

    def tick_levels(self):
        pass  # smoothing done in _tick

    # ── signal handlers ──

    def _on_state(self, si: int):
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
        self._target_level = level

    def _on_text_update(self, text: str, is_response: bool):
        self._render_text_cpu(text)
        self._show_text = 1
        self._text_alpha = 0.0
        if is_response:
            self._response_timer.start(5000)

    def _on_response_timeout(self):
        self._show_text = 0

    # ── text rasterization ──

    def _render_text_cpu(self, text: str):
        img = QImage(_TEXT_CANVAS_W, _TEXT_CANVAS_H, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        # M3 Type Scale：短文本用 body_large (16px/400)，长文本用 body_medium (14px/400)
        f = QFont()
        if len(text) < 20:
            f.setPixelSize(16)   # body_large
            f.setWeight(QFont.Weight.Normal)  # 400
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        else:
            f.setPixelSize(14)   # body_medium
            f.setWeight(QFont.Weight.Normal)  # 400
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.25)
        f.setFamily(app_font_family())
        p.setFont(f)
        # 白色文本，shader 会根据状态应用正确 tint (on-primary / on-surface)
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        p.end()
        self._pending_image = img
        self._text_needs_upload = True

    # ── tick ──

    def _tick(self):
        now = time.monotonic()
        dt = min(now - self._last_tick, 0.05)
        self._last_tick = now

        # level smoothing (simple EMA)
        self._smooth_level += (self._target_level - self._smooth_level) * min(1.0, dt / 0.08)

        # text fade — M3 short4 (250ms) in, medium2 (350ms) out
        if self._show_text and self._text_alpha < 1.0:
            self._text_alpha = min(1.0, self._text_alpha + dt / 0.25)
        elif not self._show_text and self._text_alpha > 0.0:
            self._text_alpha = max(0.0, self._text_alpha - dt / 0.35)

        self.update()

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

        self._tex_id = glGenTextures(1)

    def resizeGL(self, w: int, h: int):
        from OpenGL.GL import glViewport
        glViewport(0, 0, w, h)

    def paintGL(self):
        from OpenGL.GL import glClear, glDrawArrays

        if self._text_needs_upload and self._pending_image is not None:
            img = self._pending_image
            ptr = img.bits()
            ptr.setsize(img.width() * img.height() * 4)
            glBindTexture(GL_TEXTURE_2D, self._tex_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width(), img.height(), 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, c_void_p(int(ptr)))
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            self._tex_w = img.width()
            self._tex_h = img.height()
            self._text_needs_upload = False

        glClear(GL_COLOR_BUFFER_BIT)

        t = time.monotonic() - self._start_time

        self._program.bind()
        self._program.setUniformValue("u_resolution", float(self.width()), float(self.height()))
        self._program.setUniformValue("u_time", float(t))
        self._program.setUniformValue("u_state", self._state)
        self._program.setUniformValue("u_levels_avg", float(self._smooth_level))
        self._program.setUniformValue("u_transition", float(self._trans_value))
        self._program.setUniformValue("u_show_text", self._show_text if self._tex_id else 0)
        self._program.setUniformValue("u_text_alpha", float(self._text_alpha))

        # M3 调色板 uniforms — 从 M3ThemeManager 动态获取（支持 light/dark + 任意种子色）
        for name, value in self._palette.items():
            if isinstance(value, tuple):
                self._program.setUniformValue(name, QVector3D(value[0], value[1], value[2]))
            else:
                self._program.setUniformValue(name, float(value))

        if self._show_text and self._tex_id:
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._tex_id)
            self._program.setUniformValue("u_text", 0)

        self._vao.bind()
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self._vao.release()
        self._program.release()
