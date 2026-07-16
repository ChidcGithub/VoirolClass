from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from voirol.gui.m3 import M3Button, M3ElevatedCard
from voirol.gui.settings.base_tab import SettingsTab
from voirol.utils.i18n import t


class AboutTab(SettingsTab):
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._version_label = QLabel(t("about.version"))
        self._version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._version_label.mousePressEvent = lambda e: self._on_version_click()
        layout.addWidget(self._version_label)

        self._description_label = QLabel(t("about.description"))
        layout.addWidget(self._description_label)
        layout.addWidget(QLabel(""))
        self._tech_label = QLabel(t("about.tech"))
        layout.addWidget(self._tech_label)

        layout.addSpacing(16)

        self._dev_group = M3ElevatedCard(title="Developer Options")
        self._dev_group.setVisible(False)
        dev_layout = QVBoxLayout(self._dev_group)
        self._dev_hint_label = QLabel("Test the fatal error crash dialog:")
        dev_layout.addWidget(self._dev_hint_label)
        crash_btn = M3Button("Trigger Fatal Error", variant=M3Button.Variant.ERROR)
        crash_btn.clicked.connect(self._on_dev_crash)
        dev_layout.addWidget(crash_btn)
        layout.addWidget(self._dev_group)

        layout.addStretch()

    def title(self) -> str:
        return t("tab.about")

    def retranslate_ui(self):
        self._version_label.setText(t("about.version"))
        self._description_label.setText(t("about.description"))
        self._tech_label.setText(t("about.tech"))

    def _on_version_click(self):
        self._version_clicks = getattr(self, "_version_clicks", 0) + 1
        if self._version_clicks >= 10:
            self._version_clicks = 0
            self._dev_group.setVisible(True)

    def _on_dev_crash(self):
        import sys
        import traceback

        try:
            raise RuntimeError("Manual crash triggered from Developer Options")
        except RuntimeError:
            details = "".join(traceback.format_exc())
            print(details, file=sys.stderr)
            from voirol.gui.crash_dialog import CrashDialog

            CrashDialog(details).exec()
