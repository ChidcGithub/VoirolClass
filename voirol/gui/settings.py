import numpy as np
from PyQt6.QtCore import Qt
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
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from voirol.core.config import save_config
from voirol.core.pipeline import VoicePipeline
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
                background-color: #555;
                border-color: #aaa;
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

        self._baidu_api_label = QLabel(t("asr.baidu_api_key"))
        self._baidu_api_input = QLineEdit()
        self._baidu_api_input.setPlaceholderText(t("asr.baidu_api_key"))
        self._baidu_api_input.setText(self.pipeline.config.asr.get("baidu_api_key", ""))
        self._baidu_api_input.textChanged.connect(lambda: _on_baidu_key_changed(self, self._baidu_api_input, self._baidu_secret_input))
        asr_layout.addWidget(self._baidu_api_label)
        asr_layout.addWidget(self._baidu_api_input)

        self._baidu_secret_label = QLabel(t("asr.baidu_secret_key"))
        self._baidu_secret_input = QLineEdit()
        self._baidu_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._baidu_secret_input.setPlaceholderText(t("asr.baidu_secret_key"))
        self._baidu_secret_input.setText(self.pipeline.config.asr.get("baidu_secret_key", ""))
        self._baidu_secret_input.textChanged.connect(lambda: _on_baidu_key_changed(self, self._baidu_api_input, self._baidu_secret_input))
        asr_layout.addWidget(self._baidu_secret_label)
        asr_layout.addWidget(self._baidu_secret_input)

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
        else:
            self._asr_engine_combo.addItem(t("asr.engine_sensevoice"), "sensevoice")
            self._asr_engine_combo.addItem(t("asr.engine_vosk"), "vosk")
        current_engine = self.pipeline.config.asr.get("engine", "sensevoice")
        idx = self._asr_engine_combo.findData(current_engine)
        if idx >= 0:
            self._asr_engine_combo.setCurrentIndex(idx)
        self._asr_engine_combo.blockSignals(False)

    def _on_asr_mode_changed(self):
        self._refresh_asr_engine_list()
        self._refresh_asr_api_fields()
        self._save_asr_config()

    def _refresh_asr_api_fields(self):
        is_online = self._asr_mode_combo.currentData() == "online"
        for w in [self._baidu_api_label, self._baidu_api_input,
                  self._baidu_secret_label, self._baidu_secret_input]:
            w.setVisible(is_online)

    def _on_asr_engine_changed(self):
        self._save_asr_config()

    def _save_asr_config(self):
        self.pipeline.config.asr["mode"] = self._asr_mode_combo.currentData()
        self.pipeline.config.asr["engine"] = self._asr_engine_combo.currentData()
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
