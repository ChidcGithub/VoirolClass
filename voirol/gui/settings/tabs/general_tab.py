from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from voirol.core.config import save_config
from voirol.gui.m3 import M3Button, M3Switch
from voirol.gui.settings.base_tab import SettingsTab
from voirol.gui.tokens import PRESET_SEEDS
from voirol.gui.theme import (
    apply_theme as _apply_theme_to_widget,
    get_theme_manager,
    resolve_theme,
)
from voirol.utils.i18n import get_language, set_language, t
from voirol.utils.logger import get_logger

logger = get_logger("gui.settings.general_tab")


class _ColorSwatch(QWidget):
    """单个预设色块 — 点击选中并发信号。"""

    clicked = pyqtSignal(str)  # 发射 hex 颜色

    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self._selected = False
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._hex)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 色块主体
        painter.setBrush(QColor(self._hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        # 选中指示器（外圈）
        if self._selected:
            from voirol.gui.theme import get_theme_manager

            scheme = get_theme_manager().current_scheme()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(scheme.primary))
            painter.drawEllipse(self.rect().adjusted(0, 0, -1, -1))


class GeneralTab(SettingsTab):
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        running = self.pipeline.is_running
        self._service_btn = M3Button(
            t("service.stop") if running else t("service.start"),
            variant=M3Button.Variant.ERROR if running else M3Button.Variant.FILLED,
        )
        self._service_btn.clicked.connect(self._on_service_toggle)
        layout.addWidget(self._service_btn)

        layout.addSpacing(12)

        # ── 语言 ──
        self._lang_label = QLabel(t("general.language"))
        layout.addWidget(self._lang_label)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("English", "en")
        self._lang_combo.addItem("中文", "zh")
        current = get_language()
        self._lang_combo.setCurrentIndex(0 if current == "en" else 1)
        self._lang_combo.currentIndexChanged.connect(
            lambda i: self._on_lang_changed(self._lang_combo.itemData(i))
        )
        layout.addWidget(self._lang_combo)

        layout.addSpacing(12)

        # ── 字体大小 ──
        self._fs_label = QLabel(t("ui.font_size"))
        layout.addWidget(self._fs_label)

        fs_spin = QSpinBox()
        fs_spin.setRange(10, 24)
        fs_spin.setValue(self.pipeline.config.ui.get("font_size", 13))
        fs_spin.valueChanged.connect(lambda v: self._on_ui_changed("font_size", v))
        layout.addWidget(fs_spin)

        layout.addSpacing(12)

        # ── 圆角 ──
        self._br_label = QLabel(t("ui.border_radius"))
        layout.addWidget(self._br_label)

        br_spin = QSpinBox()
        br_spin.setRange(0, 16)
        br_spin.setValue(self.pipeline.config.ui.get("border_radius", 5))
        br_spin.valueChanged.connect(lambda v: self._on_ui_changed("border_radius", v))
        layout.addWidget(br_spin)

        layout.addSpacing(12)

        # ── 主题模式 ──
        self._theme_label = QLabel(t("ui.theme"))
        layout.addWidget(self._theme_label)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem(t("ui.theme_system"), "system")
        self._theme_combo.addItem(t("ui.theme_light"), "light")
        self._theme_combo.addItem(t("ui.theme_dark"), "dark")
        current_theme = self.pipeline.config.ui.get("theme", "system")
        self._theme_combo.setCurrentIndex(
            ["system", "light", "dark"].index(current_theme)
            if current_theme in ("system", "light", "dark") else 0
        )
        self._theme_combo.currentIndexChanged.connect(
            lambda i: self._on_theme_mode_changed(self._theme_combo.itemData(i))
        )
        layout.addWidget(self._theme_combo)

        layout.addSpacing(12)

        # ── 种子色选择器 ──
        self._seed_label = QLabel(t("ui.seed_color"))
        layout.addWidget(self._seed_label)

        self._swatches: list[_ColorSwatch] = []
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(8)
        current_seed = self.pipeline.config.ui.get("seed_color", "#A8C7FA")
        for _id, _name, hex_color in PRESET_SEEDS:
            sw = _ColorSwatch(hex_color)
            sw.set_selected(hex_color.lower() == current_seed.lower())
            sw.clicked.connect(self._on_seed_selected)
            self._swatches.append(sw)
            swatch_row.addWidget(sw)
        swatch_row.addStretch()

        self._custom_color_btn = M3Button(
            t("ui.custom_color"), variant=M3Button.Variant.OUTLINED
        )
        self._custom_color_btn.clicked.connect(self._on_custom_color)
        swatch_row.addWidget(self._custom_color_btn)

        layout.addLayout(swatch_row)

        layout.addSpacing(8)

        # ── 动态取色开关 ──
        dyn_row = QHBoxLayout()
        self._dyn_label = QLabel(t("ui.dynamic_color"))
        dyn_row.addWidget(self._dyn_label)
        dyn_row.addStretch()
        self._dyn_switch = M3Switch(
            checked=self.pipeline.config.ui.get("dynamic_color", False)
        )
        self._dyn_switch.toggled.connect(self._on_dynamic_color_toggled)
        dyn_row.addWidget(self._dyn_switch)
        layout.addLayout(dyn_row)

        layout.addStretch()

    def title(self) -> str:
        return t("tab.general")

    # ── 事件处理 ──

    def _on_service_toggle(self):
        if self.pipeline.is_running:
            self.pipeline.stop()
            self._service_btn.setText(t("service.start"))
            self._service_btn.set_variant(M3Button.Variant.FILLED)
            logger.info("Service stopped from settings")
        else:
            try:
                self.pipeline.start()
                self._service_btn.setText(t("service.stop"))
                self._service_btn.set_variant(M3Button.Variant.ERROR)
                logger.info("Service started from settings")
            except Exception as e:
                QMessageBox.warning(self, t("error.title"), str(e))

    def _on_lang_changed(self, lang_code: str):
        set_language(lang_code)
        self.pipeline.config.general["language"] = lang_code
        save_config(self.pipeline.config)
        # 实时语言切换：i18n.language_changed 信号会触发 SettingsDialog._on_language_changed

    def _on_theme_mode_changed(self, theme_value: str):
        self.pipeline.config.ui["theme"] = theme_value
        save_config(self.pipeline.config)
        mgr = get_theme_manager()
        mgr.set_mode(theme_value)
        logger.info(f"Theme mode changed to: {theme_value}")

    def _on_ui_changed(self, key: str, value: int):
        self.pipeline.config.ui[key] = value
        save_config(self.pipeline.config)
        QMessageBox.information(self, t("prompt.title"), t("ui.restart_hint"))

    def _on_seed_selected(self, hex_color: str):
        """预设色块点击 — 设置种子色"""
        self.pipeline.config.ui["seed_color"] = hex_color
        self.pipeline.config.ui["dynamic_color"] = False
        save_config(self.pipeline.config)
        # 更新色块选中状态
        for sw in self._swatches:
            sw.set_selected(sw._hex.lower() == hex_color.lower())
        self._dyn_switch.blockSignals(True)
        self._dyn_switch.setChecked(False)
        self._dyn_switch.blockSignals(False)
        # 应用到主题管理器
        mgr = get_theme_manager()
        mgr.set_dynamic_color(False, broadcast=False)
        mgr.set_seed(hex_color)
        logger.info(f"Seed color set to: {hex_color}")

    def _on_custom_color(self):
        """自定义颜色 — 打开 QColorDialog"""
        current = self.pipeline.config.ui.get("seed_color", "#A8C7FA")
        color = QColorDialog.getColor(QColor(current), self, t("ui.custom_color"))
        if color.isValid():
            hex_color = color.name()  # #RRGGBB
            self._on_seed_selected(hex_color)

    def _on_dynamic_color_toggled(self, enabled: bool):
        """动态取色开关"""
        self.pipeline.config.ui["dynamic_color"] = enabled
        save_config(self.pipeline.config)
        mgr = get_theme_manager()
        mgr.set_dynamic_color(enabled)
        if enabled:
            # 动态取色启用后，色块选中状态清除
            current_seed = mgr.current_seed()
            for sw in self._swatches:
                sw.set_selected(sw._hex.lower() == current_seed.lower())
        logger.info(f"Dynamic color {'enabled' if enabled else 'disabled'}")

    # ── 主题/语言 ──

    def apply_theme(self, scheme, shape, motion):
        running = self.pipeline.is_running
        self._service_btn.set_variant(
            M3Button.Variant.ERROR if running else M3Button.Variant.FILLED
        )
        # 色块选中圈需要重绘
        for sw in self._swatches:
            sw.update()

    def retranslate_ui(self):
        running = self.pipeline.is_running
        self._service_btn.setText(t("service.stop") if running else t("service.start"))
        self._lang_label.setText(t("general.language"))
        self._fs_label.setText(t("ui.font_size"))
        self._br_label.setText(t("ui.border_radius"))
        self._theme_label.setText(t("ui.theme"))
        self._theme_combo.setItemText(0, t("ui.theme_system"))
        self._theme_combo.setItemText(1, t("ui.theme_light"))
        self._theme_combo.setItemText(2, t("ui.theme_dark"))
        self._seed_label.setText(t("ui.seed_color"))
        self._dyn_label.setText(t("ui.dynamic_color"))
        self._custom_color_btn.setText(t("ui.custom_color"))
