import struct
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QVector3D
from PyQt6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import (
    glClear, glDrawArrays, glViewport,
    GL_FLOAT, GL_TRIANGLE_STRIP, GL_COLOR_BUFFER_BIT,
)

from voirol.gui.shaders import VERTEX_SHADER, MARQUEE_FRAGMENT
from voirol.gui.theme import get_theme_manager, M3ColorScheme, M3ShapeTokens, M3MotionTokens
from voirol.gui.tokens import _hex_to_vec3


class MarqueeWidget(QOpenGLWidget):
    _active_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(False)

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())

        self._active_signal.connect(self._on_active_change)

        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._vao: QOpenGLVertexArrayObject | None = None

        self._target_active = 0.0
        self._cur_active = 0.0
        self._running = False

        self._start_time = time.monotonic()
        self._last_tick = self._start_time

        # ── 主题感知：订阅 M3ThemeManager ──
        self._theme = get_theme_manager()
        self._primary_vec3 = _hex_to_vec3(self._theme.current_scheme().primary)
        self._theme.theme_changed.connect(self._on_theme_changed)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _on_theme_changed(
        self, scheme: M3ColorScheme, shape: M3ShapeTokens, motion: M3MotionTokens
    ):
        """主题变化时更新主色并触发重绘"""
        self._primary_vec3 = _hex_to_vec3(scheme.primary)
        self.update()

    # ── public API ──

    def set_active(self, active: bool):
        self._active_signal.emit(active)

    # ── fade logic (simple lerp) ──

    def _on_active_change(self, active: bool):
        self._target_active = 1.0 if active else 0.0
        if active and not self._running:
            self.show()
            self._running = True
            self._start_time = time.monotonic()
            self._last_tick = self._start_time
            self._timer.start()

    def _tick(self):
        now = time.monotonic()
        dt = min(now - self._last_tick, 0.05)
        self._last_tick = now

        alpha = min(1.0, dt / 0.12)
        self._cur_active += (self._target_active - self._cur_active) * alpha

        if self._target_active <= 0.0 and self._cur_active < 0.005:
            self._cur_active = 0.0
            self._timer.stop()
            self._running = False
            self.hide()
            return

        self.update()

    # ── OpenGL ──

    def initializeGL(self):
        from OpenGL.GL import glClearColor
        glClearColor(0.0, 0.0, 0.0, 0.0)

        self._program = QOpenGLShaderProgram()
        vs = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Vertex)
        vs.compileSourceCode(VERTEX_SHADER)
        fs = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Fragment)
        fs.compileSourceCode(MARQUEE_FRAGMENT)
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
        glViewport(0, 0, w, h)

    def paintGL(self):
        if self._cur_active < 0.003:
            glClear(GL_COLOR_BUFFER_BIT)
            return

        glClear(GL_COLOR_BUFFER_BIT)

        self._program.bind()
        self._program.setUniformValue("u_resolution", float(self.width()), float(self.height()))
        self._program.setUniformValue("u_active", float(self._cur_active))
        # breathing animation timebase
        self._program.setUniformValue("u_time", float(time.monotonic() - self._start_time))
        # 主题主色
        pv = self._primary_vec3
        self._program.setUniformValue("u_color_primary", QVector3D(pv[0], pv[1], pv[2]))

        self._vao.bind()
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self._vao.release()
        self._program.release()
