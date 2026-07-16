from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QGraphicsOpacityEffect, QStackedWidget, QVBoxLayout

from voirol.core.config import save_config
from voirol.core.pipeline import VoicePipeline
from voirol.gui.m3 import M3NavigationBar, M3Snackbar
from voirol.gui.settings.base_tab import SettingsTab
from voirol.gui.settings.tabs import (
    AboutTab,
    AgentTab,
    AITab,
    GeneralTab,
    LogTab,
    ModelTab,
    TTSTab,
    VoiceTab,
)
from voirol.gui.settings.widgets.enroll_dialog import show_enroll_dialog
from voirol.gui.theme import get_theme_manager
from voirol.utils.i18n import language_changed_signal, t
from voirol.utils.resources import resource_path


class _AnimatedStackedWidget(QStackedWidget):
    """带淡入淡出过渡动画的 QStackedWidget。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_duration = 200
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._is_animating = False

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or self._is_animating:
            return
        self._is_animating = True
        # 淡出
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(self._anim_duration // 2)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(lambda: self._on_faded_out(index))
        self._fade_out.start()

    def _on_faded_out(self, index: int):
        super().setCurrentIndex(index)
        # 淡入
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(self._anim_duration // 2)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.finished.connect(self._on_faded_in)
        self._fade_in.start()

    def _on_faded_in(self):
        self._is_animating = False


class SettingsDialog(QDialog):
    def __init__(self, pipeline: VoicePipeline):
        super().__init__()
        self.pipeline = pipeline
        self.setWindowTitle(t("settings.title"))
        self.setWindowIcon(QIcon(resource_path("assets/img/icon.png")))
        self.setMinimumWidth(680)
        self.setMinimumHeight(560)

        self._theme = get_theme_manager()
        self._theme.theme_changed.connect(self._on_theme_changed)
        language_changed_signal().connect(self._on_language_changed)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._nav = M3NavigationBar(M3NavigationBar.Style.BAR)
        self._stack = _AnimatedStackedWidget()

        layout.addWidget(self._nav)
        layout.addWidget(self._stack, 1)

        self._tabs: list[SettingsTab] = [
            VoiceTab(pipeline, self._debounce_save),
            GeneralTab(pipeline, self._debounce_save),
            AITab(pipeline, self._debounce_save),
            AgentTab(pipeline, self._debounce_save),
            TTSTab(pipeline, self._debounce_save),
            ModelTab(pipeline, self._debounce_save),
            LogTab(pipeline, self._debounce_save),
            AboutTab(pipeline, self._debounce_save),
        ]

        for tab in self._tabs:
            self._stack.addWidget(tab)
            self._nav.add_item(tab.title())

        self._nav.current_changed.connect(self._stack.setCurrentIndex)
        self._nav.set_current(0)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._do_save_config)

        self._on_theme_changed(
            self._theme.current_scheme(),
            self._theme.current_shape(),
            self._theme.current_motion(),
        )

    def _on_language_changed(self, _lang: str):
        """语言切换时刷新所有 Tab 文本、导航栏标签、窗口标题。"""
        self.setWindowTitle(t("settings.title"))
        for i, tab in enumerate(self._tabs):
            tab.retranslate_ui()
            self._nav.set_item_label(i, tab.title())

    def _debounce_save(self):
        if not self._save_timer.isActive():
            self._save_timer.start()

    def _do_save_config(self):
        save_config(self.pipeline.config)
        # Snackbar 通知（非阻塞）
        try:
            M3Snackbar.show(self, t("settings.saved"))
        except Exception:
            pass

    def _on_theme_changed(self, scheme, shape, motion):
        self.setStyleSheet(self._theme.generate_qss())
        for tab in self._tabs:
            tab.apply_theme(scheme, shape, motion)

    def closeEvent(self, event):
        self._save_timer.stop()
        save_config(self.pipeline.config)
        for tab in self._tabs:
            tab.cleanup()
        super().closeEvent(event)

    def done(self, result):
        self._save_timer.stop()
        save_config(self.pipeline.config)
        for tab in self._tabs:
            tab.cleanup()
        super().done(result)


def _show_settings_dialog(pipeline: VoicePipeline):
    dialog = SettingsDialog(pipeline)
    dialog.exec()
