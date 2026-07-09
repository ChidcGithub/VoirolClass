from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from voirol.utils.i18n import t


class CrashDialog(QDialog):
    def __init__(self, details: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("crash.title"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setFixedSize(520, 380)

        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        msg = QLabel(t("crash.message"))
        msg.setStyleSheet("font-size: 13px; color: rgba(255,255,255,180);")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setPlainText(details)
        self._text.setStyleSheet("""
            QPlainTextEdit {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
                background: rgba(0,0,0,60);
                color: #ff6b6b;
                border: 1px solid rgba(255,255,255,30);
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self._text)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        copy_btn = QPushButton(t("crash.copy"))
        copy_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 18px;
                border: 1px solid rgba(255,255,255,40);
                border-radius: 4px;
                background: rgba(255,255,255,20);
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,40);
            }
        """)
        copy_btn.clicked.connect(self._on_copy)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        exit_btn = QPushButton(t("quit"))
        exit_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 18px;
                border: none;
                border-radius: 4px;
                background: #c62828;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #e53935;
            }
        """)
        exit_btn.clicked.connect(QApplication.instance().quit)
        btn_layout.addWidget(exit_btn)

        layout.addLayout(btn_layout)

        self._details = details

    def _on_copy(self):
        QApplication.clipboard().setText(self._details)
