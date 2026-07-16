"""SettingsTab — 所有设置标签页的基类。

提供：
  - pipeline 访问（配置、运行状态）
  - 防抖保存回调
  - 主题感知（apply_theme / retranslate_ui）
  - 清理接口（cleanup）
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QWidget

from voirol.core.pipeline import VoicePipeline
from voirol.gui.tokens import M3ColorScheme, M3ShapeTokens, M3MotionTokens


class SettingsTab(QWidget):
    """设置标签页基类。

    子类必须实现：
      - ``_build_ui()``  构建 UI
      - ``title()``      返回导航栏标签文本
    可选实现：
      - ``icon_name()``      返回图标名称
      - ``retranslate_ui()`` 更新翻译文本
      - ``apply_theme()``    更新主题颜色
      - ``cleanup()``        清理线程/资源
    """

    def __init__(
        self,
        pipeline: VoicePipeline,
        on_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.pipeline = pipeline
        self._on_changed = on_changed
        self._build_ui()

    # ── 子类必须实现 ──

    def _build_ui(self):
        raise NotImplementedError

    def title(self) -> str:
        raise NotImplementedError

    # ── 可选覆盖 ──

    def icon_name(self) -> str:
        return ""

    def retranslate_ui(self):
        pass

    def apply_theme(self, scheme: M3ColorScheme, shape: M3ShapeTokens, motion: M3MotionTokens):
        pass

    def cleanup(self):
        pass

    # ── 便捷方法 ──

    def _mark_changed(self):
        """标记配置已变更，触发防抖保存"""
        if self._on_changed:
            self._on_changed()
