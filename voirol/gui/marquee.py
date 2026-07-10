import struct

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
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
        self._active = 0.0
        self._tick = 0

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._timer.start()

        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(16)
        self._fade_timer.timeout.connect(self._tick_fade)

    def set_active(self, active: bool):
        self._active_signal.emit(active)

    def _on_active_change(self, active: bool):
        if active and self._active < 1.0:
            self._active = 0.0
            self._fade_timer.start()
            self.show()
        elif not active:
            self._fade_timer.stop()
            self._fade_timer.timeout.connect(self._tick_out)
            self._fade_timer.start()

    def _tick_fade(self):
        self._active = min(1.0, self._active + 0.06)
        if self._active >= 1.0:
            self._fade_timer.stop()
            self._fade_timer.timeout.connect(self._tick_fade)
            self._fade_timer.disconnect()

    def _tick_out(self):
        self._active = max(0.0, self._active - 0.06)
        if self._active <= 0.0:
            self._fade_timer.stop()
            self._fade_timer.timeout.connect(self._tick_fade)
            self._fade_timer.disconnect()
            self.hide()

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
        self._tick += 1
        glClear(GL_COLOR_BUFFER_BIT)

        self._program.bind()
        self._program.setUniformValue("u_resolution", float(self.width()), float(self.height()))
        self._program.setUniformValue("u_time", self._tick / 30.0)
        self._program.setUniformValue("u_active", self._active)

        self._vao.bind()
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self._vao.release()
        self._program.release()
