"""Material You 组件库。

提供符合 M3 设计规范的 PyQt6 组件，所有组件订阅 M3ThemeManager 的 theme_changed
信号，实现主题实时切换。

组件清单：
    button.py     — M3Button (Filled / Tonal / Outlined / Text / Elevated)
    card.py       — M3Card / M3ElevatedCard / M3OutlinedCard / M3FilledCard
    switch.py     — M3Switch (替代 QCheckBox 的开关变体)
    slider.py     — M3Slider
    text_field.py — M3TextField (Filled / Outlined)
    chip.py       — M3Chip / M3FilterChip / M3InputChip
    list.py       — M3ListTile
    dialog.py     — M3Dialog / M3AlertDialog
    navigation.py — M3NavigationBar / M3NavigationRail
    snackbar.py   — M3Snackbar
    progress.py   — M3CircularProgress / M3LinearProgress
    ripple.py     — RippleOverlay (内部用)
    state_layer.py — StateLayerOverlay (内部用)
    base.py       — M3Widget 基类

所有组件均继承自 M3Widget，自动订阅主题变化。
"""
from voirol.gui.m3.base import M3Widget
from voirol.gui.m3.button import M3Button
from voirol.gui.m3.card import M3Card, M3ElevatedCard, M3OutlinedCard, M3FilledCard
from voirol.gui.m3.switch import M3Switch
from voirol.gui.m3.text_field import M3TextField
from voirol.gui.m3.chip import M3Chip
from voirol.gui.m3.dialog import M3Dialog
from voirol.gui.m3.navigation import M3NavigationBar
from voirol.gui.m3.snackbar import M3Snackbar
from voirol.gui.m3.progress import M3CircularProgress, M3LinearProgress

__all__ = [
    "M3Widget",
    "M3Button",
    "M3Card", "M3ElevatedCard", "M3OutlinedCard", "M3FilledCard",
    "M3Switch",
    "M3TextField",
    "M3Chip",
    "M3Dialog",
    "M3NavigationBar",
    "M3Snackbar",
    "M3CircularProgress", "M3LinearProgress",
]
