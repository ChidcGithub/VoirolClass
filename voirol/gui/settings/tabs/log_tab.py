from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from voirol.gui.m3 import M3Button, M3Switch
from voirol.gui.settings.base_tab import SettingsTab
from voirol.utils.i18n import t
from voirol.utils.logger import _global_log_buffer, _log_signal


class LogTab(SettingsTab):
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        filter_layout = QHBoxLayout()
        self._filter_label = QLabel(t("log.filter"))
        filter_layout.addWidget(self._filter_label)

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItem(t("log.level_all"), "")
        self._log_level_combo.addItem(t("log.level_debug"), "DEBUG")
        self._log_level_combo.addItem(t("log.level_info"), "INFO")
        self._log_level_combo.addItem(t("log.level_warning"), "WARNING")
        self._log_level_combo.addItem(t("log.level_error"), "ERROR")
        self._log_level_combo.currentIndexChanged.connect(self._on_log_filter_changed)
        filter_layout.addWidget(self._log_level_combo)

        self._log_auto_scroll_switch = M3Switch(checked=True)
        filter_layout.addWidget(self._log_auto_scroll_switch)
        self._auto_scroll_label = QLabel(t("log.auto_scroll"))
        filter_layout.addWidget(self._auto_scroll_label)

        filter_layout.addStretch()

        self._clear_btn = M3Button(t("log.clear"), variant=M3Button.Variant.TEXT)
        self._clear_btn.clicked.connect(self._on_log_clear)
        filter_layout.addWidget(self._clear_btn)

        layout.addLayout(filter_layout)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)
        self._log_view.setFont(QFont("Consolas", 9))
        layout.addWidget(self._log_view)

        self._log_buffer: list[str] = []

        for msg in _global_log_buffer:
            self._log_buffer.append(msg)
            self._log_view.appendPlainText(msg)
        if _global_log_buffer:
            from PyQt6.QtGui import QTextCursor

            self._log_view.moveCursor(QTextCursor.MoveOperation.End)

        _log_signal.emitted.connect(self._on_log_message)

    def title(self) -> str:
        return t("tab.log")

    def _on_log_message(self, msg: str):
        self._log_buffer.append(msg)
        if len(self._log_buffer) > 10000:
            self._log_buffer = self._log_buffer[-5000:]
        level_filter = self._log_level_combo.currentData()
        if level_filter and f"[{level_filter}]" not in msg:
            return
        self._log_view.appendPlainText(msg)
        if self._log_auto_scroll_switch.isChecked():
            from PyQt6.QtGui import QTextCursor

            self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _on_log_filter_changed(self):
        level_filter = self._log_level_combo.currentData()
        self._log_view.clear()
        for msg in self._log_buffer:
            if level_filter and f"[{level_filter}]" not in msg:
                continue
            self._log_view.appendPlainText(msg)

    def _on_log_clear(self):
        self._log_buffer.clear()
        self._log_view.clear()

    def retranslate_ui(self):
        self._filter_label.setText(t("log.filter"))
        self._log_level_combo.setItemText(0, t("log.level_all"))
        self._log_level_combo.setItemText(1, t("log.level_debug"))
        self._log_level_combo.setItemText(2, t("log.level_info"))
        self._log_level_combo.setItemText(3, t("log.level_warning"))
        self._log_level_combo.setItemText(4, t("log.level_error"))
        self._auto_scroll_label.setText(t("log.auto_scroll"))
        self._clear_btn.setText(t("log.clear"))

    def cleanup(self):
        try:
            _log_signal.emitted.disconnect(self._on_log_message)
        except (TypeError, RuntimeError):
            pass
