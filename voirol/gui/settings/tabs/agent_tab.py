from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from voirol.core.config import save_config
from voirol.gui.m3 import M3Switch, M3TextField
from voirol.gui.settings.base_tab import SettingsTab
from voirol.utils.i18n import t


class AgentTab(SettingsTab):
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        agent_cfg = self.pipeline.config.agent

        enable_row = QHBoxLayout()
        self._agent_enable_label = QLabel(t("agent.enable"))
        self._agent_enabled_cb = M3Switch(checked=agent_cfg.get("enabled", False))
        self._agent_enabled_cb.toggled.connect(self._on_agent_config_changed)
        enable_row.addWidget(self._agent_enable_label)
        enable_row.addWidget(self._agent_enabled_cb)
        enable_row.addStretch()
        layout.addLayout(enable_row)

        self._agent_steps_label = QLabel(t("agent.max_steps"))
        layout.addWidget(self._agent_steps_label)

        self._agent_steps_spin = QSpinBox()
        self._agent_steps_spin.setRange(5, 100)
        self._agent_steps_spin.setValue(agent_cfg.get("max_steps", 30))
        self._agent_steps_spin.valueChanged.connect(self._on_agent_config_changed)
        layout.addWidget(self._agent_steps_spin)

        self._agent_ocr_label = QLabel(t("agent.ocr_lang"))
        layout.addWidget(self._agent_ocr_label)

        self._agent_ocr_input = M3TextField(placeholder="chi_sim+eng")
        self._agent_ocr_input.setText(agent_cfg.get("ocr_lang", "chi_sim+eng"))
        self._agent_ocr_input.textChanged.connect(self._on_agent_config_changed)
        layout.addWidget(self._agent_ocr_input)

        self._agent_temp_label = QLabel(t("agent.temperature"))
        layout.addWidget(self._agent_temp_label)

        self._agent_temp_spin = QDoubleSpinBox()
        self._agent_temp_spin.setRange(0.0, 2.0)
        self._agent_temp_spin.setSingleStep(0.1)
        self._agent_temp_spin.setDecimals(1)
        self._agent_temp_spin.setValue(agent_cfg.get("temperature", 0.1))
        self._agent_temp_spin.valueChanged.connect(self._on_agent_config_changed)
        layout.addWidget(self._agent_temp_spin)

        self._agent_timeout_label = QLabel(t("agent.timeout"))
        layout.addWidget(self._agent_timeout_label)

        self._agent_timeout_spin = QSpinBox()
        self._agent_timeout_spin.setRange(5, 120)
        self._agent_timeout_spin.setValue(agent_cfg.get("timeout", 15))
        self._agent_timeout_spin.valueChanged.connect(self._on_agent_config_changed)
        layout.addWidget(self._agent_timeout_spin)

        self._agent_restart_hint_label = QLabel(t("agent.restart_hint"))
        layout.addWidget(self._agent_restart_hint_label)

        layout.addStretch()

    def title(self) -> str:
        return t("agent.tab")

    def retranslate_ui(self):
        self._agent_enable_label.setText(t("agent.enable"))
        self._agent_steps_label.setText(t("agent.max_steps"))
        self._agent_ocr_label.setText(t("agent.ocr_lang"))
        self._agent_temp_label.setText(t("agent.temperature"))
        self._agent_timeout_label.setText(t("agent.timeout"))
        self._agent_restart_hint_label.setText(t("agent.restart_hint"))

    def _on_agent_config_changed(self):
        self.pipeline.config.agent["enabled"] = self._agent_enabled_cb.isChecked()
        self.pipeline.config.agent["max_steps"] = self._agent_steps_spin.value()
        self.pipeline.config.agent["ocr_lang"] = self._agent_ocr_input.text().strip()
        self.pipeline.config.agent["temperature"] = self._agent_temp_spin.value()
        self.pipeline.config.agent["timeout"] = self._agent_timeout_spin.value()
        save_config(self.pipeline.config)
