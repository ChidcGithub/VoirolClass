from enum import Enum

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget


class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class ThemeManager(QObject):
    changed = pyqtSignal(Theme, int)

    def broadcast(self, theme: Theme, br: int):
        self.changed.emit(theme, br)


_theme_manager: ThemeManager | None = None


def get_theme_manager() -> ThemeManager:
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def detect_system_theme() -> Theme:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return Theme.LIGHT if value == 1 else Theme.DARK
    except Exception:
        pass
    try:
        scheme = QApplication.styleHints().colorScheme()
        return Theme.LIGHT if scheme == Qt.ColorScheme.Light else Theme.DARK
    except Exception:
        return Theme.DARK


def resolve_theme(cfg_theme: str) -> Theme:
    if cfg_theme == "system":
        return detect_system_theme()
    return Theme(cfg_theme)


def theme_qss(theme: Theme, br: int = 5) -> str:
    if theme == Theme.LIGHT:
        return LIGHT_QSS.format(br=br)
    return DARK_QSS.format(br=br)


def apply_theme(widget: QWidget, theme: Theme, br: int = 5) -> None:
    widget.setStyleSheet(theme_qss(theme, br))


DARK_QSS = """
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
QLineEdit {{
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: {br}px;
    padding: 4px 8px;
    selection-background-color: #4a90d9;
}}
QComboBox {{
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: {br}px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: #777;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #999;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #555;
    selection-background-color: #4a4a4a;
}}
QSpinBox, QDoubleSpinBox {{
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: {br}px;
    padding: 4px 8px;
    min-height: 24px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    border: none;
    border-left: 1px solid #555;
    width: 20px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    border-left: 1px solid #555;
    width: 20px;
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
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+CiAgPHBhdGggZmlsbD0iI2ZmZmZmZiIgZD0iTTYgMTEuOUwyLjUgOC40IDMuOSA3IDYgOS4xIDEyLjEgM2wxLjQgMS40eiIvPgo8L3N2Zz4K);
}}
QLabel {{
    color: #e0e0e0;
}}
QTableWidget {{
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: {br}px;
    gridline-color: #3a3a3a;
}}
QTableWidget::item:selected {{
    background-color: #4a4a4a;
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: none;
    border-bottom: 1px solid #555;
    padding: 6px;
}}
QProgressBar {{
    background-color: #2d2d2d;
    border: 1px solid #555;
    border-radius: {br}px;
    text-align: center;
    color: #e0e0e0;
}}
QProgressBar::chunk {{
    background-color: #4a90d9;
    border-radius: {br}px;
}}
QFrame[frameShape=\"4\"] {{
    border: none;
    border-top: 1px solid #555;
}}
"""

LIGHT_QSS = """
QDialog {{
    background-color: #f5f5f5;
    color: #333333;
}}
QTabWidget::pane {{
    background-color: #f5f5f5;
    border: none;
}}
QTabBar::tab {{
    background-color: #e0e0e0;
    color: #666;
    padding: 8px 20px;
    border: none;
    min-width: 80px;
}}
QTabBar::tab:selected {{
    background-color: #ffffff;
    color: #333333;
    border-bottom: 2px solid #4a90d9;
}}
QTabBar::tab:hover:!selected {{
    background-color: #ebebeb;
    color: #444;
}}
QGroupBox {{
    background-color: #fafafa;
    border: 1px solid #ddd;
    border-radius: {br}px;
    margin-top: 12px;
    padding: 16px 12px 12px;
    font-weight: normal;
    color: #333333;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #333333;
}}
QPushButton {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: {br}px;
    padding: 6px 16px;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: #f0f0f0;
    border-color: #aaa;
}}
QPushButton:pressed {{
    background-color: #e0e0e0;
}}
QPushButton:disabled {{
    background-color: #f5f5f5;
    color: #aaa;
    border-color: #ddd;
}}
QLineEdit {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: {br}px;
    padding: 4px 8px;
    selection-background-color: #4a90d9;
    selection-color: #ffffff;
}}
QComboBox {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: {br}px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: #aaa;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #666;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    selection-background-color: #e0e0e0;
}}
QSpinBox, QDoubleSpinBox {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: {br}px;
    padding: 4px 8px;
    min-height: 24px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    border: none;
    border-left: 1px solid #ccc;
    width: 20px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    border-left: 1px solid #ccc;
    width: 20px;
}}
QListWidget {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: {br}px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 2px;
}}
QListWidget::item:selected {{
    background-color: #4a90d9;
    color: #ffffff;
}}
QListWidget::item:hover:!selected {{
    background-color: #e8f0fe;
}}
QCheckBox {{
    color: #333333;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #aaa;
    border-radius: 2px;
    background-color: #ffffff;
}}
QCheckBox::indicator:checked {{
    background-color: #4a90d9;
    border-color: #4a90d9;
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+CiAgPHBhdGggZmlsbD0iI2ZmZmZmZiIgZD0iTTYgMTEuOUwyLjUgOC40IDMuOSA3IDYgOS4xIDEyLjEgM2wxLjQgMS40eiIvPgo8L3N2Zz4K);
}}
QLabel {{
    color: #333333;
}}
QTableWidget {{
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: {br}px;
    gridline-color: #e0e0e0;
}}
QTableWidget::item:selected {{
    background-color: #4a90d9;
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: #f0f0f0;
    color: #333333;
    border: none;
    border-bottom: 1px solid #ccc;
    padding: 6px;
}}
QProgressBar {{
    background-color: #e0e0e0;
    border: 1px solid #ccc;
    border-radius: {br}px;
    text-align: center;
    color: #333333;
}}
QProgressBar::chunk {{
    background-color: #4a90d9;
    border-radius: {br}px;
}}
QFrame[frameShape=\"4\"] {{
    border: none;
    border-top: 1px solid #ccc;
}}
"""
