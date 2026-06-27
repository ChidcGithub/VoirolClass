import numpy as np
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)
from voirol.core.config import save_config

from voirol.core.pipeline import VoicePipeline
from voirol.voice import model_download as md
from voirol.utils.i18n import get_language, set_language, t
from voirol.utils.logger import get_logger

logger = get_logger("gui.settings")


def _show_settings_dialog(pipeline: VoicePipeline):
    dialog = SettingsDialog(pipeline)
    dialog.exec()


class SettingsDialog(QDialog):
    def __init__(self, pipeline: VoicePipeline):
        super().__init__()
        self.pipeline = pipeline
        self.setWindowTitle(t("settings.title"))
        self.setWindowIcon(QIcon("assets/img/icon.png"))

        self.setMinimumWidth(560)
        self.setMinimumHeight(500)

        br = self.pipeline.config.ui.get("border_radius", 5)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1e1e1e;
                color: #e0e0e0;
            }}
            QTabWidget::pane {{
                background-color: #1e1e1e;
                border: none;
            }}
            QTabBar::tab {{
                background-color: #2d2d2d;
                color: #999;
                padding: 8px 20px;
                border: none;
                min-width: 80px;
            }}
            QTabBar::tab:selected {{
                background-color: #3c3c3c;
                color: #ffffff;
                border-bottom: 2px solid #ffffff;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #353535;
                color: #ccc;
            }}
            QGroupBox {{
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: {br}px;
                margin-top: 12px;
                padding: 16px 12px 12px;
                font-weight: normal;
                color: #ffffff;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #ffffff;
            }}
            QPushButton {{
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: {br}px;
                padding: 6px 16px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: #4a4a4a;
                border-color: #777;
            }}
            QPushButton:pressed {{
                background-color: #555;
            }}
            QPushButton:disabled {{
                background-color: #2a2a2a;
                color: #666;
                border-color: #444;
            }}
            QListWidget {{
                background-color: #252525;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: {br}px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-radius: 2px;
            }}
            QListWidget::item:selected {{
                background-color: #4a4a4a;
                color: #ffffff;
            }}
            QListWidget::item:hover:!selected {{
                background-color: #333;
            }}
            QCheckBox {{
                color: #e0e0e0;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid #777;
                border-radius: 2px;
                background-color: #2d2d2d;
            }}
            QCheckBox::indicator:checked {{
                background-color: #4a90d9;
                border-color: #4a90d9;
                image: url(assets/img/checkmark.svg);
            }}
            QLabel {{
                color: #e0e0e0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tabs)

        self._add_voice_tab()
        self._add_general_tab()
        self._add_model_tab()
        self._add_about_tab()



    def _add_voice_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        teacher_group = QGroupBox(t("teacher.manage"))
        teacher_layout = QVBoxLayout(teacher_group)

        self._current_label = QLabel(
            t("teacher.current", name=self.pipeline.verifier.get_active_name() or t("teacher.none"))
        )
        teacher_layout.addWidget(self._current_label)

        self._teacher_list = QListWidget()
        teacher_layout.addWidget(self._teacher_list)

        btn_layout = QHBoxLayout()
        enroll_btn = QPushButton(t("teacher.register"))
        select_btn = QPushButton(t("teacher.select"))
        delete_btn = QPushButton(t("teacher.delete"))

        btn_layout.addWidget(enroll_btn)
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(delete_btn)
        teacher_layout.addLayout(btn_layout)

        layout.addWidget(teacher_group)

        asr_group = QGroupBox(t("asr.mode"))
        asr_layout = QVBoxLayout(asr_group)
        asr_layout.setSpacing(8)

        mode_layout = QHBoxLayout()
        mode_label = QLabel(t("asr.mode"))
        mode_layout.addWidget(mode_label)

        self._asr_mode_combo = QComboBox()
        self._asr_mode_combo.addItem(t("asr.mode_offline"), "offline")
        self._asr_mode_combo.addItem(t("asr.mode_online"), "online")
        current_mode = self.pipeline.config.asr.get("mode", "offline")
        self._asr_mode_combo.setCurrentIndex(0 if current_mode == "offline" else 1)
        self._asr_mode_combo.currentIndexChanged.connect(self._on_asr_mode_changed)
        mode_layout.addWidget(self._asr_mode_combo)
        asr_layout.addLayout(mode_layout)

        engine_layout = QHBoxLayout()
        engine_label = QLabel(t("asr.engine_label"))
        engine_layout.addWidget(engine_label)

        self._asr_engine_combo = QComboBox()
        engine_layout.addWidget(self._asr_engine_combo)
        asr_layout.addLayout(engine_layout)

        asr_layout.addSpacing(6)

        self._api_stack = QStackedWidget()

        baidu_page = QWidget()
        baidu_form = QVBoxLayout(baidu_page)
        baidu_form.setContentsMargins(0, 0, 0, 0)
        baidu_form.addWidget(QLabel(t("asr.baidu_api_key")))
        self._baidu_api_input = QLineEdit()
        self._baidu_api_input.setPlaceholderText(t("asr.baidu_api_key"))
        self._baidu_api_input.setText(self.pipeline.config.asr.get("baidu_api_key", ""))
        self._baidu_api_input.textChanged.connect(lambda: _on_baidu_key_changed(self, self._baidu_api_input, self._baidu_secret_input))
        baidu_form.addWidget(self._baidu_api_input)
        baidu_form.addWidget(QLabel(t("asr.baidu_secret_key")))
        self._baidu_secret_input = QLineEdit()
        self._baidu_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._baidu_secret_input.setPlaceholderText(t("asr.baidu_secret_key"))
        self._baidu_secret_input.setText(self.pipeline.config.asr.get("baidu_secret_key", ""))
        self._baidu_secret_input.textChanged.connect(lambda: _on_baidu_key_changed(self, self._baidu_api_input, self._baidu_secret_input))
        baidu_form.addWidget(self._baidu_secret_input)
        self._api_stack.addWidget(baidu_page)

        azure_page = QWidget()
        azure_form = QVBoxLayout(azure_page)
        azure_form.setContentsMargins(0, 0, 0, 0)
        azure_form.addWidget(QLabel(t("asr.azure_subscription_key")))
        self._azure_sub_input = QLineEdit()
        self._azure_sub_input.setPlaceholderText(t("asr.azure_subscription_key"))
        self._azure_sub_input.setText(self.pipeline.config.asr.get("azure_subscription_key", ""))
        self._azure_sub_input.textChanged.connect(lambda: _on_azure_key_changed(self, self._azure_sub_input, self._azure_region_input))
        azure_form.addWidget(self._azure_sub_input)
        azure_form.addWidget(QLabel(t("asr.azure_region")))
        self._azure_region_input = QLineEdit()
        self._azure_region_input.setPlaceholderText("eastasia")
        self._azure_region_input.setText(self.pipeline.config.asr.get("azure_region", ""))
        self._azure_region_input.textChanged.connect(lambda: _on_azure_key_changed(self, self._azure_sub_input, self._azure_region_input))
        azure_form.addWidget(self._azure_region_input)
        self._api_stack.addWidget(azure_page)

        tencent_page = QWidget()
        tencent_form = QVBoxLayout(tencent_page)
        tencent_form.setContentsMargins(0, 0, 0, 0)
        tencent_form.addWidget(QLabel(t("asr.tencent_secret_id")))
        self._tencent_id_input = QLineEdit()
        self._tencent_id_input.setPlaceholderText(t("asr.tencent_secret_id"))
        self._tencent_id_input.setText(self.pipeline.config.asr.get("tencent_secret_id", ""))
        self._tencent_id_input.textChanged.connect(lambda: _on_tencent_key_changed(self, self._tencent_id_input, self._tencent_key_input))
        tencent_form.addWidget(self._tencent_id_input)
        tencent_form.addWidget(QLabel(t("asr.tencent_secret_key")))
        self._tencent_key_input = QLineEdit()
        self._tencent_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._tencent_key_input.setPlaceholderText(t("asr.tencent_secret_key"))
        self._tencent_key_input.setText(self.pipeline.config.asr.get("tencent_secret_key", ""))
        self._tencent_key_input.textChanged.connect(lambda: _on_tencent_key_changed(self, self._tencent_id_input, self._tencent_key_input))
        tencent_form.addWidget(self._tencent_key_input)
        self._api_stack.addWidget(tencent_page)

        asr_layout.addWidget(self._api_stack)

        layout.addWidget(asr_group)

        layout.addSpacing(6)

        rb_label = QLabel(t("voice.history_duration"))
        rb_label.setToolTip(t("voice.history_duration_desc"))
        layout.addWidget(rb_label)

        self._rb_spin = QDoubleSpinBox()
        self._rb_spin.setRange(0.5, 5.0)
        self._rb_spin.setSingleStep(0.5)
        self._rb_spin.setValue(self.pipeline.config.voice.get("ring_buffer_seconds", 2.0))
        self._rb_spin.valueChanged.connect(self._on_ring_buffer_changed)
        layout.addWidget(self._rb_spin)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("border: none; border-top: 1px solid #555;")
        layout.addWidget(line)

        self._mute_cb = QCheckBox(t("mute.mic"))
        self._mute_cb.setChecked(self.pipeline.muted)
        self._mute_cb.toggled.connect(self._on_mute_toggled)
        layout.addWidget(self._mute_cb)

        layout.addStretch()

        self.tabs.addTab(tab, t("tab.voice"))

        enroll_btn.clicked.connect(self._on_enroll)
        select_btn.clicked.connect(self._on_select)
        delete_btn.clicked.connect(self._on_delete)

        self._refresh_asr_engine_list()
        self._asr_engine_combo.currentIndexChanged.connect(self._on_asr_engine_changed)
        self._refresh_asr_api_fields()

        self._refresh_teacher_list()

    def _refresh_asr_engine_list(self):
        self._asr_engine_combo.blockSignals(True)
        self._asr_engine_combo.clear()
        is_online = self._asr_mode_combo.currentData() == "online"
        if is_online:
            self._asr_engine_combo.addItem(t("asr.engine_baidu"), "baidu")
            self._asr_engine_combo.addItem(t("asr.engine_azure"), "azure")
            self._asr_engine_combo.addItem(t("asr.engine_tencent"), "tencent")
        else:
            self._asr_engine_combo.addItem(t("asr.engine_sensevoice"), "sensevoice")
            self._asr_engine_combo.addItem(t("asr.engine_vosk"), "vosk")
        current_engine = self.pipeline.config.asr.get("engine", "sensevoice")
        idx = self._asr_engine_combo.findData(current_engine)
        if idx >= 0:
            self._asr_engine_combo.setCurrentIndex(idx)
        self._asr_engine_combo.blockSignals(False)

    def _on_asr_mode_changed(self):
        if self._asr_mode_combo.currentData() == "offline":
            engine = self._asr_engine_combo.currentData()
            if not self._check_offline_model(engine):
                self._asr_mode_combo.blockSignals(True)
                self._asr_mode_combo.setCurrentIndex(1)
                self._asr_mode_combo.blockSignals(False)
                return
        self._refresh_asr_engine_list()
        self._refresh_asr_api_fields()
        self._save_asr_config()

    def _refresh_asr_api_fields(self):
        is_online = self._asr_mode_combo.currentData() == "online"
        self._api_stack.setVisible(is_online)
        if is_online:
            engine = self._asr_engine_combo.currentData()
            if engine == "baidu":
                self._api_stack.setCurrentIndex(0)
            elif engine == "azure":
                self._api_stack.setCurrentIndex(1)
            elif engine == "tencent":
                self._api_stack.setCurrentIndex(2)

    def _on_asr_engine_changed(self):
        if self._asr_mode_combo.currentData() == "offline":
            engine = self._asr_engine_combo.currentData()
            if not self._check_offline_model(engine):
                self._asr_engine_combo.blockSignals(True)
                prev = self.pipeline.config.asr.get("engine", "sensevoice")
                idx = self._asr_engine_combo.findData(prev)
                if idx >= 0:
                    self._asr_engine_combo.setCurrentIndex(idx)
                self._asr_engine_combo.blockSignals(False)
                return
        self._refresh_asr_api_fields()
        self._save_asr_config()

    def _check_offline_model(self, engine: str) -> bool:
        mid = {"sensevoice": "sensevoice"}.get(engine)
        if engine == "vosk":
            lang = self.pipeline.config.asr.get("vosk_language", "zh-cn")
            mid = "vosk_en" if lang.startswith("en") else "vosk_zh"
        if mid and md.check_model_status(mid) == md.DownloadState.MISSING:
            name = md.MODELS[mid].name
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(t("prompt.title"))
            msg.setText(t("model.engine_needs_model", engine=name))
            go_btn = msg.addButton(t("model.go_download"), QMessageBox.ButtonRole.ActionRole)
            msg.addButton(t("close"), QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == go_btn:
                self.tabs.setCurrentIndex(2)
            return False
        return True

    def _save_asr_config(self):
        old_mode = self.pipeline.config.asr.get("mode")
        old_engine = self.pipeline.config.asr.get("engine")
        new_mode = self._asr_mode_combo.currentData()
        new_engine = self._asr_engine_combo.currentData()
        if old_mode == new_mode and old_engine == new_engine:
            return
        self.pipeline.config.asr["mode"] = new_mode
        self.pipeline.config.asr["engine"] = new_engine
        save_config(self.pipeline.config)
        QMessageBox.information(self, t("prompt.title"), t("asr.restart_hint"))

    def _on_mute_toggled(self, checked: bool):
        self.pipeline.muted = checked
        logger.info(f"{'Muted' if checked else 'Unmuted'}")

    def _refresh_teacher_list(self):
        self._teacher_list.clear()
        teachers = self.pipeline.enrollment.list_profiles()
        if not teachers:
            self._teacher_list.addItem(t("teacher.no_teachers"))
            self._teacher_list.setEnabled(False)
        else:
            self._teacher_list.setEnabled(True)
            for name in teachers:
                self._teacher_list.addItem(name)
            current = self.pipeline.verifier.get_active_name()
            if current and current in teachers:
                items = self._teacher_list.findItems(
                    current, Qt.MatchFlag.MatchExactly
                )
                if items:
                    self._teacher_list.setCurrentItem(items[0])
        self._current_label.setText(
            t("teacher.current", name=self.pipeline.verifier.get_active_name() or t("teacher.none"))
        )

    def _on_enroll(self):
        _show_enroll_dialog(self.pipeline)
        self._refresh_teacher_list()

    def _on_select(self):
        item = self._teacher_list.currentItem()
        if not item or not item.text() or item.text().startswith("("):
            QMessageBox.warning(self, t("prompt.title"), t("teacher.prompt_select"))
            return
        name = item.text()
        if self.pipeline.set_teacher(name):
            QMessageBox.information(self, t("success.title"), t("teacher.switched", name=name))
            self._refresh_teacher_list()
        else:
            QMessageBox.warning(self, t("error.title"), t("teacher.switch_failed", name=name))

    def _on_delete(self):
        item = self._teacher_list.currentItem()
        if not item or not item.text() or item.text().startswith("("):
            QMessageBox.warning(self, t("prompt.title"), t("teacher.prompt_select"))
            return
        name = item.text()

        reply = QMessageBox.question(
            self, t("teacher.confirm_delete"),
            t("teacher.confirm_delete_text", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.pipeline.enrollment.delete_profile(name)
        if self.pipeline.verifier.get_active_name() == name:
            self.pipeline.verifier.set_profile(None)
            self.pipeline.config.teacher["current_teacher"] = ""

        logger.info(t("teacher.deleted", name=name))
        self._refresh_teacher_list()

    def _on_ring_buffer_changed(self, value: float):
        self.pipeline.config.voice["ring_buffer_seconds"] = value
        save_config(self.pipeline.config)
        logger.info(f"Ring buffer seconds set to {value}")

    def _on_mirror_changed(self):
        self.pipeline.config.download["mirror_url"] = self._mirror_input.text().strip()
        save_config(self.pipeline.config)

    def _on_test_mirror(self):
        url = self._mirror_input.text().strip()
        if not url:
            self._mirror_status.setText(t("model.test_fail", error="no input"))
            return
        self._test_mirror_btn.setEnabled(False)
        self._mirror_status.setText("...")
        QApplication.processEvents()
        ok, msg = md.test_mirror(url)
        self._mirror_status.setText(
            t("model.test_success", status=msg) if ok
            else t("model.test_fail", error=msg)
        )
        self._mirror_status.setStyleSheet("color: #4caf50;" if ok else "color: #f44336;")
        self._test_mirror_btn.setEnabled(True)

    def _refresh_model_table(self):
        self._model_table.setRowCount(0)
        model_ids = ["silero_vad", "sensevoice", "vosk_zh", "vosk_en", "campplus"]
        for mid in model_ids:
            entry = md.MODELS.get(mid)
            if not entry:
                continue
            status = md.check_model_status(mid)
            row = self._model_table.rowCount()
            self._model_table.insertRow(row)
            self._model_table.setItem(row, 0, QTableWidgetItem(entry.name))
            self._model_table.setItem(row, 1, QTableWidgetItem(entry.size))
            if status == md.DownloadState.DOWNLOADED:
                status_text = t("model.status_downloaded")
            elif status == md.DownloadState.AUTO:
                status_text = t("model.status_auto")
            else:
                status_text = t("model.status_missing")
            item = QTableWidgetItem(status_text)
            self._model_table.setItem(row, 2, item)
            name_item = self._model_table.item(row, 0)
            name_item.setData(256, mid)
            if status == md.DownloadState.AUTO:
                grey = QColor("#888")
                for col in range(3):
                    self._model_table.item(row, col).setForeground(grey)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

    def _get_selected_model_id(self) -> str | None:
        row = self._model_table.currentRow()
        if row < 0:
            return None
        return self._model_table.item(row, 0).data(256)

    def _check_resume_queue(self):
        pending = md.load_queue()
        if not pending:
            return
        reply = QMessageBox.question(
            self, t("model.resume_title"),
            t("model.resume_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_queue(pending)

    def _on_download_selected(self):
        mid = self._get_selected_model_id()
        if not mid:
            QMessageBox.warning(self, t("prompt.title"), t("model.select_hint"))
            return
        entry = md.MODELS.get(mid)
        if entry and entry.auto:
            QMessageBox.information(self, t("prompt.title"), t("model.status_auto"))
            return
        self._start_queue([mid])

    def _on_download_all(self):
        pending = [mid for mid in md.DOWNLOAD_ORDER
                   if md.check_model_status(mid) == md.DownloadState.MISSING]
        if not pending:
            return
        self._start_queue(pending)

    def _start_queue(self, model_ids: list[str]):
        mirror = self._mirror_input.text().strip()
        md.save_queue(model_ids)

        self._progress_group.setVisible(True)
        for mid in md.DOWNLOAD_ORDER:
            bar, status = self._dl_rows[mid]
            st = md.check_model_status(mid)
            if mid in model_ids:
                if mid == model_ids[0]:
                    bar.setValue(0)
                    status.setText("0%")
                else:
                    bar.setValue(0)
                    status.setText(t("model.waiting"))
            elif st == md.DownloadState.DOWNLOADED:
                bar.setValue(100)
                status.setText(t("model.status_downloaded"))
            elif st == md.DownloadState.AUTO:
                bar.setValue(100)
                status.setText(t("model.status_auto"))
            else:
                bar.setValue(0)
                status.setText("—")
        self._download_btn.setEnabled(False)
        self._download_all_btn.setEnabled(False)

        self._dl_thread = QThread()
        self._dl_worker = md.DownloadWorker(model_ids, mirror)
        self._dl_worker.moveToThread(self._dl_thread)
        self._dl_thread.started.connect(self._dl_worker.run)
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.model_finished.connect(self._on_dl_model_finished)
        self._dl_worker.all_finished.connect(self._on_dl_all_finished)
        self._dl_worker.all_finished.connect(self._dl_thread.quit)
        self._dl_worker.all_finished.connect(self._dl_worker.deleteLater)
        self._dl_thread.finished.connect(self._dl_thread.deleteLater)
        self._dl_thread.start()

    def _on_dl_progress(self, model_id: str, pct: int):
        if model_id in self._dl_rows:
            bar, status = self._dl_rows[model_id]
            if pct == -1:
                bar.setValue(0)
                status.setText(t("model.extracting"))
            else:
                bar.setValue(pct)
                status.setText(t("model.progress", pct=pct))

    def _on_dl_model_finished(self, model_id: str, success: bool):
        if model_id in self._dl_rows:
            bar, status = self._dl_rows[model_id]
            ok = success and md.check_model_status(model_id) == md.DownloadState.DOWNLOADED
            bar.setValue(100 if ok else 0)
            status.setText(t("model.done") if ok else t("model.failed"))
        queue = md.load_queue()
        if model_id in queue:
            queue.remove(model_id)
            if queue:
                md.save_queue(queue)
            else:
                md.clear_queue()
        self._refresh_model_table()

    def _on_dl_all_finished(self):
        self._download_btn.setEnabled(True)
        self._download_all_btn.setEnabled(True)
        md.clear_queue()

    def _add_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        lang_label = QLabel(t("general.language"))
        layout.addWidget(lang_label)

        lang_combo = QComboBox()
        lang_combo.addItem("English", "en")
        lang_combo.addItem("中文", "zh")
        current = get_language()
        lang_combo.setCurrentIndex(0 if current == "en" else 1)
        lang_combo.currentIndexChanged.connect(
            lambda i: _on_lang_changed(self, lang_combo.itemData(i))
        )
        layout.addWidget(lang_combo)

        layout.addSpacing(12)

        fs_label = QLabel(t("ui.font_size"))
        layout.addWidget(fs_label)

        fs_spin = QSpinBox()
        fs_spin.setRange(10, 24)
        fs_spin.setValue(self.pipeline.config.ui.get("font_size", 13))
        fs_spin.valueChanged.connect(
            lambda v: _on_ui_changed(self, "font_size", v)
        )
        layout.addWidget(fs_spin)

        layout.addSpacing(12)

        br_label = QLabel(t("ui.border_radius"))
        layout.addWidget(br_label)

        br_spin = QSpinBox()
        br_spin.setRange(0, 16)
        br_spin.setValue(self.pipeline.config.ui.get("border_radius", 5))
        br_spin.valueChanged.connect(
            lambda v: _on_ui_changed(self, "border_radius", v)
        )
        layout.addWidget(br_spin)

        layout.addStretch()
        self.tabs.addTab(tab, t("tab.general"))

    def _add_model_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        mirror_label = QLabel(t("model.mirror_url"))
        layout.addWidget(mirror_label)

        mirror_layout = QHBoxLayout()
        self._mirror_input = QLineEdit()
        self._mirror_input.setPlaceholderText("https://ghproxy.com")
        self._mirror_input.setText(self.pipeline.config.download.get("mirror_url", ""))
        self._mirror_input.textChanged.connect(self._on_mirror_changed)
        mirror_layout.addWidget(self._mirror_input)

        self._test_mirror_btn = QPushButton(t("model.test_mirror"))
        self._test_mirror_btn.clicked.connect(self._on_test_mirror)
        mirror_layout.addWidget(self._test_mirror_btn)

        self._mirror_status = QLabel("")
        mirror_layout.addWidget(self._mirror_status)
        layout.addLayout(mirror_layout)

        layout.addSpacing(8)

        self._model_table = QTableWidget()
        self._model_table.setColumnCount(3)
        self._model_table.setHorizontalHeaderLabels([
            t("model.name"), t("model.size"), t("model.status")
        ])
        self._model_table.horizontalHeader().setStretchLastSection(True)
        self._model_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._model_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._model_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._model_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self._model_table)

        btn_layout = QHBoxLayout()
        self._download_btn = QPushButton(t("model.download_selected"))
        self._download_btn.clicked.connect(self._on_download_selected)
        btn_layout.addWidget(self._download_btn)

        self._download_all_btn = QPushButton(t("model.download_all"))
        self._download_all_btn.clicked.connect(self._on_download_all)
        btn_layout.addWidget(self._download_all_btn)
        layout.addLayout(btn_layout)

        self._progress_group = QGroupBox(t("model.progress_panel"))
        self._progress_group.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_group)
        progress_layout.setSpacing(4)
        self._dl_rows: dict[str, tuple[QProgressBar, QLabel]] = {}
        for mid in md.DOWNLOAD_ORDER:
            row_layout = QHBoxLayout()
            name_label = QLabel(md.MODELS[mid].name)
            name_label.setFixedWidth(120)
            row_layout.addWidget(name_label)
            bar = QProgressBar()
            bar.setMinimum(0)
            bar.setMaximum(100)
            bar.setValue(0)
            row_layout.addWidget(bar, stretch=1)
            status_label = QLabel("")
            status_label.setFixedWidth(80)
            row_layout.addWidget(status_label)
            progress_layout.addLayout(row_layout)
            self._dl_rows[mid] = (bar, status_label)
        layout.addWidget(self._progress_group)

        layout.addStretch()
        self.tabs.addTab(tab, t("model.tab"))

        self._refresh_model_table()
        self._check_resume_queue()

    def _add_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel(t("about.version")))
        layout.addWidget(QLabel(t("about.description")))
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel(t("about.tech")))
        layout.addStretch()
        self.tabs.addTab(tab, t("tab.about"))


def _on_lang_changed(dialog: SettingsDialog, lang_code: str):
    set_language(lang_code)
    dialog.pipeline.config.general["language"] = lang_code
    save_config(dialog.pipeline.config)
    QMessageBox.information(dialog, t("prompt.title"), t("general.restart_hint"))


def _on_ui_changed(dialog: SettingsDialog, key: str, value: int):
    dialog.pipeline.config.ui[key] = value
    save_config(dialog.pipeline.config)
    QMessageBox.information(dialog, t("prompt.title"), t("ui.restart_hint"))


def _on_baidu_key_changed(dialog: SettingsDialog, api_input, secret_input):
    dialog.pipeline.config.asr["baidu_api_key"] = api_input.text()
    dialog.pipeline.config.asr["baidu_secret_key"] = secret_input.text()
    save_config(dialog.pipeline.config)


def _on_azure_key_changed(dialog: SettingsDialog, sub_input, region_input):
    dialog.pipeline.config.asr["azure_subscription_key"] = sub_input.text()
    dialog.pipeline.config.asr["azure_region"] = region_input.text()
    save_config(dialog.pipeline.config)


def _on_tencent_key_changed(dialog: SettingsDialog, id_input, key_input):
    dialog.pipeline.config.asr["tencent_secret_id"] = id_input.text()
    dialog.pipeline.config.asr["tencent_secret_key"] = key_input.text()
    save_config(dialog.pipeline.config)


def _show_enroll_dialog(pipeline: VoicePipeline):
    dialog = QDialog()
    dialog.setWindowTitle("注册新老师")
    dialog.setMinimumWidth(350)

    layout = QVBoxLayout(dialog)

    form = QFormLayout()
    name_input = QLineEdit()
    name_input.setPlaceholderText("输入老师姓名")
    form.addRow("姓名:", name_input)
    layout.addLayout(form)

    info_label = QLabel("点击「开始注册」后，请依次读出以下句子：")
    info_label.setWordWrap(True)
    layout.addWidget(info_label)

    sentences = [
        "今天我们来学习新的一课",
        "请大家打开课本第20页",
        "注意看黑板上的重点内容",
        "这个问题谁来回答",
        "下课之前我们来总结一下",
    ]

    sentence_list = QListWidget()
    for s in sentences:
        sentence_list.addItem(s)
    layout.addWidget(sentence_list)

    start_btn = QPushButton("开始注册")
    layout.addWidget(start_btn)
    result_label = QLabel("")
    layout.addWidget(result_label)

    def on_start():
        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(dialog, "提示", "请输入老师姓名")
            return

        pipeline.pause()

        import sounddevice as sd

        sample_rate = pipeline.config.general["sample_rate"]
        duration = 3
        collected = []

        for i, sentence in enumerate(sentences):
            result_label.setText(
                f"第 {i+1}/{len(sentences)} 句: 3秒后请读出「{sentence}」"
            )
            result_label.repaint()
            QApplication.processEvents()

            QMessageBox.information(
                dialog, "录音",
                f"点击确定后开始录音 ({duration}秒)\n\n请读出: 「{sentence}」"
            )

            audio = sd.rec(
                int(sample_rate * duration),
                samplerate=sample_rate,
                channels=1,
                dtype=np.float32,
            )
            sd.wait()

            audio = audio.flatten()
            if np.max(np.abs(audio)) > 0.01:
                pipeline.enrollment.save_enrollment_audio(
                    name, i, audio, sample_rate
                )
                from voirol.audio.processor import preprocess
                collected.append(preprocess(audio, sample_rate))
                result_label.setText(f"✓ 第 {i+1} 句已录制")
            else:
                result_label.setText(f"✗ 未检测到声音，跳过第 {i+1} 句")
            QApplication.processEvents()

        if len(collected) < 2:
            QMessageBox.warning(
                dialog, "失败", "有效录音太少，请重试。确保麦克风正常工作。"
            )
            pipeline.resume()
            return

        from voirol.voice.verifier import create_profile_from_audio
        profile = create_profile_from_audio(
            collected, name, sample_rate,
            model_path=pipeline.config.voice.get("model_path", "campplus-zh-en"),
        )
        pipeline.enrollment.save_profile(profile)

        result_label.setText(f"注册完成！已为 {name} 创建声纹模型")
        QMessageBox.information(
            dialog, "完成", f"老师 {name} 注册成功！"
        )

        pipeline.resume()

    start_btn.clicked.connect(on_start)
    dialog.exec()
