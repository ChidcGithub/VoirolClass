import os

from PyQt6.QtCore import QUrl, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtQuickWidgets import QQuickWidget
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class StartupSplash(QWidget):
    W = 350
    H = 85

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.W // 2, screen.center().y() - self.H // 2)

        bg = QColor(30, 30, 30, 235)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch(1)

        title = QLabel("VoirolClass", self)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(6)

        row = QHBoxLayout()
        row.setContentsMargins(24, 0, 24, 0)
        row.setSpacing(0)

        self._status = QLabel(self)
        self._status.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 160);")
        row.addWidget(self._status)

        row.addStretch(1)

        qml_path = os.path.join(os.path.dirname(__file__), "spinner.qml")
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"
        self._spinner = QQuickWidget(self)
        self._spinner.setFixedSize(28, 28)
        self._spinner.setSource(QUrl.fromLocalFile(qml_path))
        self._spinner.setClearColor(bg)
        row.addWidget(self._spinner)

        layout.addLayout(row)

        layout.addStretch(1)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)
        self._progress.setFixedSize(self.W, 4)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 30);
                border: none;
                border-radius: 0;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(255, 255, 255, 80),
                    stop: 0.5 white,
                    stop: 1 rgba(255, 255, 255, 80)
                );
                border-radius: 0;
            }
        """)
        layout.addWidget(self._progress)

        self._error_details = QLabel(self)
        self._error_details.setStyleSheet(
            "font-size: 11px; color: #ff6b6b; padding: 4px 12px;"
        )
        self._error_details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_details.setWordWrap(True)
        self._error_details.setMaximumWidth(self.W - 40)
        self._error_details.hide()
        layout.addWidget(self._error_details)

    def set_status(self, text: str):
        self._status.setText(text)
        QApplication.processEvents()

    def set_error(self, text: str):
        root = self._spinner.rootObject()
        if root:
            root.setProperty("running", False)
        self._status.setStyleSheet("font-size: 12px; color: #ff6b6b;")
        self._error_details.setText(text)
        self._error_details.show()
        QApplication.processEvents()

    def close_with_delay(self, ms: int = 500):
        QTimer.singleShot(ms, self.close)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30, 235))
        pen = painter.pen()
        pen.setColor(QColor(255, 255, 255, 25))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()
