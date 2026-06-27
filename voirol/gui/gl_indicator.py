import struct

from PyQt6.QtCore import QElapsedTimer, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QVector3D
from PyQt6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFunctions_4_1_Core,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from voirol.gui.shaders import FRAGMENT_SHADER, VERTEX_SHADER

GL_FLOAT = 0x1406
GL_TRIANGLE_STRIP = 0x0005
GL_COLOR_BUFFER_BIT = 0x00004000


class GLIndicator(QOpenGLWidget):
    _state_signal = pyqtSignal(int)
    _level_signal = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAutoFillBackground(False)

        self._gl: QOpenGLFunctions_4_1_Core | None = None
        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._vao: QOpenGLVertexArrayObject | None = None

        self._state = 0
        self._levels = [0.0, 0.0, 0.0]
        self._transition = 0.0
        self._elapsed = QElapsedTimer()
        self._elapsed.start()

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self._timer.start()

        self._state_signal.connect(self._on_state)
        self._level_signal.connect(self._on_level)

    def initializeGL(self):
        self._gl = QOpenGLFunctions_4_1_Core()
        self._gl.initializeOpenGLFunctions()
        self._gl.glClearColor(0.0, 0.0, 0.0, 0.0)

        self._program = QOpenGLShaderProgram()
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, VERTEX_SHADER)
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENT_SHADER)
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
        if self._gl:
            self._gl.glViewport(0, 0, w, h)

    def paintGL(self):
        self._gl.glClear(GL_COLOR_BUFFER_BIT)

        self._program.bind()

        self._program.setUniformValue("u_resolution", float(self.width()), float(self.height()))
        elapsed = self._elapsed.elapsed() / 1000.0
        self._program.setUniformValue("u_time", elapsed)
        self._program.setUniformValue("u_state", self._state)
        self._program.setUniformValue(
            "u_levels",
            QVector3D(self._levels[0], self._levels[1], self._levels[2]),
        )
        self._program.setUniformValue("u_transition", self._transition)

        self._vao.bind()
        self._gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self._vao.release()

        self._program.release()

    def set_state(self, state_int: int):
        self._state_signal.emit(state_int)

    def set_level(self, level: float):
        self._level_signal.emit(level)

    def set_levels(self, levels):
        self._levels[:] = levels

    def set_transition(self, t: float):
        self._transition = t

    def _on_state(self, state_int: int):
        self._state = state_int

    def _on_level(self, level: float):
        pass
