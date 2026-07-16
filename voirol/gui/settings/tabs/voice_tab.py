from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from voirol.core.config import save_config
from voirol.gui.m3 import M3Button, M3ElevatedCard, M3TextField
from voirol.gui.settings.base_tab import SettingsTab
from voirol.gui.settings.widgets import show_enroll_dialog
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger
from voirol.voice import model_download as md

logger = get_logger("gui.settings.voice_tab")


class VoiceTab(SettingsTab):
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        teacher_group = M3ElevatedCard(title=t("teacher.manage"))
        teacher_layout = QVBoxLayout(teacher_group)
        teacher_layout.setContentsMargins(16, 16, 16, 16)
        teacher_layout.setSpacing(12)

        self._teacher_card_title = QLabel(t("teacher.manage"))
        teacher_layout.addWidget(self._teacher_card_title)

        self._current_label = QLabel(
            t("teacher.current", name=self.pipeline.verifier.get_active_name() or t("teacher.none"))
        )
        teacher_layout.addWidget(self._current_label)

        self._teacher_list = QListWidget()
        teacher_layout.addWidget(self._teacher_list)

        btn_layout = QHBoxLayout()
        self._enroll_btn = M3Button(t("teacher.register"), variant=M3Button.Variant.FILLED)
        self._select_btn = M3Button(t("teacher.select"), variant=M3Button.Variant.TONAL)
        self._delete_btn = M3Button(t("teacher.delete"), variant=M3Button.Variant.ERROR)

        btn_layout.addWidget(self._enroll_btn)
        btn_layout.addWidget(self._select_btn)
        btn_layout.addWidget(self._delete_btn)
        teacher_layout.addLayout(btn_layout)

        layout.addWidget(teacher_group)

        asr_group = M3ElevatedCard(title=t("asr.mode"))
        asr_layout = QVBoxLayout(asr_group)
        asr_layout.setContentsMargins(16, 16, 16, 16)
        asr_layout.setSpacing(8)

        self._asr_card_title = QLabel(t("asr.mode"))
        asr_layout.addWidget(self._asr_card_title)

        mode_layout = QHBoxLayout()
        self._mode_label = QLabel(t("asr.mode"))
        mode_layout.addWidget(self._mode_label)

        self._asr_mode_combo = QComboBox()
        self._asr_mode_combo.addItem(t("asr.mode_offline"), "offline")
        self._asr_mode_combo.addItem(t("asr.mode_online"), "online")
        current_mode = self.pipeline.config.asr.get("mode", "offline")
        self._asr_mode_combo.setCurrentIndex(0 if current_mode == "offline" else 1)
        self._asr_mode_combo.currentIndexChanged.connect(self._on_asr_mode_changed)
        mode_layout.addWidget(self._asr_mode_combo)
        asr_layout.addLayout(mode_layout)

        engine_layout = QHBoxLayout()
        self._engine_label = QLabel(t("asr.engine_label"))
        engine_layout.addWidget(self._engine_label)

        self._asr_engine_combo = QComboBox()
        engine_layout.addWidget(self._asr_engine_combo)
        asr_layout.addLayout(engine_layout)

        asr_layout.addSpacing(6)

        self._api_stack = QStackedWidget()

        baidu_page = QWidget()
        baidu_form = QVBoxLayout(baidu_page)
        baidu_form.setContentsMargins(0, 0, 0, 0)
        self._baidu_api_label = QLabel(t("asr.baidu_api_key"))
        baidu_form.addWidget(self._baidu_api_label)
        self._baidu_api_input = M3TextField(placeholder=t("asr.baidu_api_key"))
        self._baidu_api_input.setText(self.pipeline.config.asr.get("baidu_api_key", ""))
        self._baidu_api_input.textChanged.connect(self._on_baidu_key_changed)
        baidu_form.addWidget(self._baidu_api_input)
        self._baidu_secret_label = QLabel(t("asr.baidu_secret_key"))
        baidu_form.addWidget(self._baidu_secret_label)
        self._baidu_secret_input = M3TextField(placeholder=t("asr.baidu_secret_key"))
        self._baidu_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._baidu_secret_input.setText(self.pipeline.config.asr.get("baidu_secret_key", ""))
        self._baidu_secret_input.textChanged.connect(self._on_baidu_key_changed)
        baidu_form.addWidget(self._baidu_secret_input)
        self._api_stack.addWidget(baidu_page)

        azure_page = QWidget()
        azure_form = QVBoxLayout(azure_page)
        azure_form.setContentsMargins(0, 0, 0, 0)
        self._azure_sub_label = QLabel(t("asr.azure_subscription_key"))
        azure_form.addWidget(self._azure_sub_label)
        self._azure_sub_input = M3TextField(placeholder=t("asr.azure_subscription_key"))
        self._azure_sub_input.setText(self.pipeline.config.asr.get("azure_subscription_key", ""))
        self._azure_sub_input.textChanged.connect(self._on_azure_key_changed)
        azure_form.addWidget(self._azure_sub_input)
        self._azure_region_label = QLabel(t("asr.azure_region"))
        azure_form.addWidget(self._azure_region_label)
        self._azure_region_input = M3TextField(placeholder="eastasia")
        self._azure_region_input.setText(self.pipeline.config.asr.get("azure_region", ""))
        self._azure_region_input.textChanged.connect(self._on_azure_key_changed)
        azure_form.addWidget(self._azure_region_input)
        self._api_stack.addWidget(azure_page)

        tencent_page = QWidget()
        tencent_form = QVBoxLayout(tencent_page)
        tencent_form.setContentsMargins(0, 0, 0, 0)
        self._tencent_id_label = QLabel(t("asr.tencent_secret_id"))
        tencent_form.addWidget(self._tencent_id_label)
        self._tencent_id_input = M3TextField(placeholder=t("asr.tencent_secret_id"))
        self._tencent_id_input.setText(self.pipeline.config.asr.get("tencent_secret_id", ""))
        self._tencent_id_input.textChanged.connect(self._on_tencent_key_changed)
        tencent_form.addWidget(self._tencent_id_input)
        self._tencent_key_label = QLabel(t("asr.tencent_secret_key"))
        tencent_form.addWidget(self._tencent_key_label)
        self._tencent_key_input = M3TextField(placeholder=t("asr.tencent_secret_key"))
        self._tencent_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._tencent_key_input.setText(self.pipeline.config.asr.get("tencent_secret_key", ""))
        self._tencent_key_input.textChanged.connect(self._on_tencent_key_changed)
        tencent_form.addWidget(self._tencent_key_input)
        self._api_stack.addWidget(tencent_page)

        asr_layout.addWidget(self._api_stack)

        layout.addWidget(asr_group)

        layout.addSpacing(6)

        self._rb_label = QLabel(t("voice.history_duration"))
        self._rb_label.setToolTip(t("voice.history_duration_desc"))
        layout.addWidget(self._rb_label)

        self._rb_spin = QDoubleSpinBox()
        self._rb_spin.setRange(0.5, 5.0)
        self._rb_spin.setSingleStep(0.5)
        self._rb_spin.setValue(self.pipeline.config.voice.get("ring_buffer_seconds", 2.0))
        self._rb_spin.valueChanged.connect(self._on_ring_buffer_changed)
        layout.addWidget(self._rb_spin)

        self._mu_label = QLabel(t("voice.max_utterance"))
        self._mu_label.setToolTip(t("voice.max_utterance_desc"))
        layout.addWidget(self._mu_label)

        self._mu_spin = QSpinBox()
        self._mu_spin.setRange(3, 60)
        self._mu_spin.setSuffix(" s")
        self._mu_spin.setValue(self.pipeline.config.voice.get("max_utterance_seconds", 15))
        self._mu_spin.valueChanged.connect(self._on_max_utterance_changed)
        layout.addWidget(self._mu_spin)

        layout.addStretch()

        self._enroll_btn.clicked.connect(self._on_enroll)
        self._select_btn.clicked.connect(self._on_select)
        self._delete_btn.clicked.connect(self._on_delete)

        self._refresh_asr_engine_list()
        self._asr_engine_combo.currentIndexChanged.connect(self._on_asr_engine_changed)
        self._refresh_asr_api_fields()

        self._refresh_teacher_list()

    def retranslate_ui(self):
        self._teacher_card_title.setText(t("teacher.manage"))
        self._asr_card_title.setText(t("asr.mode"))
        self._enroll_btn.setText(t("teacher.register"))
        self._select_btn.setText(t("teacher.select"))
        self._delete_btn.setText(t("teacher.delete"))
        self._current_label.setText(
            t("teacher.current", name=self.pipeline.verifier.get_active_name() or t("teacher.none"))
        )
        self._mode_label.setText(t("asr.mode"))
        self._engine_label.setText(t("asr.engine_label"))
        self._asr_mode_combo.setItemText(0, t("asr.mode_offline"))
        self._asr_mode_combo.setItemText(1, t("asr.mode_online"))
        self._refresh_asr_engine_list()
        self._baidu_api_label.setText(t("asr.baidu_api_key"))
        self._baidu_api_input.setPlaceholderText(t("asr.baidu_api_key"))
        self._baidu_secret_label.setText(t("asr.baidu_secret_key"))
        self._baidu_secret_input.setPlaceholderText(t("asr.baidu_secret_key"))
        self._azure_sub_label.setText(t("asr.azure_subscription_key"))
        self._azure_sub_input.setPlaceholderText(t("asr.azure_subscription_key"))
        self._azure_region_label.setText(t("asr.azure_region"))
        self._azure_region_input.setPlaceholderText("eastasia")
        self._tencent_id_label.setText(t("asr.tencent_secret_id"))
        self._tencent_id_input.setPlaceholderText(t("asr.tencent_secret_id"))
        self._tencent_key_label.setText(t("asr.tencent_secret_key"))
        self._tencent_key_input.setPlaceholderText(t("asr.tencent_secret_key"))
        self._rb_label.setText(t("voice.history_duration"))
        self._rb_label.setToolTip(t("voice.history_duration_desc"))
        self._mu_label.setText(t("voice.max_utterance"))
        self._mu_label.setToolTip(t("voice.max_utterance_desc"))
        self._refresh_teacher_list()

    def title(self) -> str:
        return t("tab.voice")

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
                dlg = self.window()
                nav = getattr(dlg, "_nav", None)
                if nav is not None:
                    nav.set_current(5)
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
        show_enroll_dialog(self.pipeline)
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

    def _on_max_utterance_changed(self, value: int):
        self.pipeline.config.voice["max_utterance_seconds"] = value
        save_config(self.pipeline.config)
        logger.info(f"Max utterance seconds set to {value}")

    def _on_baidu_key_changed(self):
        self.pipeline.config.asr["baidu_api_key"] = self._baidu_api_input.text()
        self.pipeline.config.asr["baidu_secret_key"] = self._baidu_secret_input.text()
        save_config(self.pipeline.config)

    def _on_azure_key_changed(self):
        self.pipeline.config.asr["azure_subscription_key"] = self._azure_sub_input.text()
        self.pipeline.config.asr["azure_region"] = self._azure_region_input.text()
        save_config(self.pipeline.config)

    def _on_tencent_key_changed(self):
        self.pipeline.config.asr["tencent_secret_id"] = self._tencent_id_input.text()
        self.pipeline.config.asr["tencent_secret_key"] = self._tencent_key_input.text()
        save_config(self.pipeline.config)
