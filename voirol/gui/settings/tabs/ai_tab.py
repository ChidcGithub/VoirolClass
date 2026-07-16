from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from voirol.ai.matcher import DEFAULT_SYSTEM_PROMPT
from voirol.gui.m3 import M3Button, M3Switch, M3TextField
from voirol.gui.settings.base_tab import SettingsTab
from voirol.utils.i18n import t


class AITab(SettingsTab):
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        ai_cfg = self.pipeline.config.ai

        enable_row = QHBoxLayout()
        self._ai_enable_label = QLabel(t("ai.enable"))
        self._ai_enabled_cb = M3Switch(checked=ai_cfg.get("enabled", False))
        self._ai_enabled_cb.toggled.connect(self._on_ai_config_changed)
        enable_row.addWidget(self._ai_enable_label)
        enable_row.addWidget(self._ai_enabled_cb)
        enable_row.addStretch()
        layout.addLayout(enable_row)

        self._ai_api_url_label = QLabel(t("ai.api_url"))
        layout.addWidget(self._ai_api_url_label)

        self._ai_api_url_input = M3TextField(placeholder="https://api.deepseek.com/v1")
        self._ai_api_url_input.setText(ai_cfg.get("api_url", ""))
        self._ai_api_url_input.textChanged.connect(self._on_ai_config_changed)
        layout.addWidget(self._ai_api_url_input)

        self._ai_api_key_label = QLabel(t("ai.api_key"))
        layout.addWidget(self._ai_api_key_label)

        self._ai_api_key_input = M3TextField(placeholder="sk-...")
        self._ai_api_key_input.setEchoMode(M3TextField.EchoMode.Password)
        self._ai_api_key_input.setText(ai_cfg.get("api_key", ""))
        self._ai_api_key_input.textChanged.connect(self._on_ai_config_changed)
        layout.addWidget(self._ai_api_key_input)

        self._ai_model_label = QLabel(t("ai.model"))
        layout.addWidget(self._ai_model_label)

        self._ai_model_input = M3TextField(placeholder="deepseek-chat")
        self._ai_model_input.setText(ai_cfg.get("model", "deepseek-chat"))
        self._ai_model_input.textChanged.connect(self._on_ai_config_changed)
        layout.addWidget(self._ai_model_input)

        self._ai_temp_label = QLabel(t("ai.temperature"))
        layout.addWidget(self._ai_temp_label)

        self._ai_temp_spin = QDoubleSpinBox()
        self._ai_temp_spin.setRange(0.0, 2.0)
        self._ai_temp_spin.setSingleStep(0.1)
        self._ai_temp_spin.setDecimals(1)
        self._ai_temp_spin.setValue(ai_cfg.get("temperature", 0.1))
        self._ai_temp_spin.valueChanged.connect(self._on_ai_config_changed)
        layout.addWidget(self._ai_temp_spin)

        self._ai_timeout_label = QLabel(t("ai.timeout"))
        layout.addWidget(self._ai_timeout_label)

        self._ai_timeout_spin = QSpinBox()
        self._ai_timeout_spin.setRange(5, 60)
        self._ai_timeout_spin.setValue(ai_cfg.get("timeout", 10))
        self._ai_timeout_spin.valueChanged.connect(self._on_ai_config_changed)
        layout.addWidget(self._ai_timeout_spin)

        layout.addSpacing(12)

        self._ai_prompt_label = QLabel(t("ai.system_prompt"))
        layout.addWidget(self._ai_prompt_label)

        self._ai_prompt_edit = QPlainTextEdit()
        self._ai_prompt_edit.setPlaceholderText("")
        prompt_text = ai_cfg.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT
        try:
            prompt_text.format(commands_list="test", user_text="test")
        except KeyError:
            prompt_text = DEFAULT_SYSTEM_PROMPT
            self.pipeline.config.ai["system_prompt"] = ""
        self._ai_prompt_edit.setPlainText(prompt_text)
        self._ai_prompt_edit.textChanged.connect(self._on_ai_config_changed)
        self._ai_prompt_edit.setMinimumHeight(120)
        layout.addWidget(self._ai_prompt_edit)

        self._ai_reset_btn = M3Button(
            t("ai.reset_default_prompt"), variant=M3Button.Variant.TONAL
        )
        self._ai_reset_btn.clicked.connect(self._on_ai_reset_prompt)
        layout.addWidget(self._ai_reset_btn)

        layout.addStretch()

    def title(self) -> str:
        return t("ai.tab")

    def retranslate_ui(self):
        self._ai_enable_label.setText(t("ai.enable"))
        self._ai_api_url_label.setText(t("ai.api_url"))
        self._ai_api_key_label.setText(t("ai.api_key"))
        self._ai_model_label.setText(t("ai.model"))
        self._ai_temp_label.setText(t("ai.temperature"))
        self._ai_timeout_label.setText(t("ai.timeout"))
        self._ai_prompt_label.setText(t("ai.system_prompt"))
        self._ai_reset_btn.setText(t("ai.reset_default_prompt"))

    def _on_ai_config_changed(self):
        self.pipeline.config.ai["enabled"] = self._ai_enabled_cb.isChecked()
        self.pipeline.config.ai["api_url"] = self._ai_api_url_input.text()
        self.pipeline.config.ai["api_key"] = self._ai_api_key_input.text()
        self.pipeline.config.ai["model"] = self._ai_model_input.text()
        self.pipeline.config.ai["temperature"] = self._ai_temp_spin.value()
        self.pipeline.config.ai["timeout"] = self._ai_timeout_spin.value()
        prompt = self._ai_prompt_edit.toPlainText()
        self.pipeline.config.ai["system_prompt"] = "" if prompt == DEFAULT_SYSTEM_PROMPT else prompt
        self._mark_changed()

    def _on_ai_reset_prompt(self):
        self._ai_prompt_edit.setPlainText(DEFAULT_SYSTEM_PROMPT)
