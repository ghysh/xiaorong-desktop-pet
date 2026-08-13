"""One shared QAction registry for both pet-window and system-tray menus."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.settings.service import SettingsService


class ActionRegistry(QObject):
    """Create actions once, connect them once, and synchronize presentation state."""

    def __init__(
        self,
        settings_service: SettingsService,
        *,
        show_hide_callback: Callable[[], None],
        show_settings_callback: Callable[[], None],
        reset_position_callback: Callable[[], None],
        drowsy_sleep_enabled_callback: Callable[[bool], None],
        drowsy_sleep_demo_callback: Callable[[], None],
        quit_callback: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_service = settings_service
        self._show_hide_callback = show_hide_callback
        self._show_settings_callback = show_settings_callback
        self._reset_position_callback = reset_position_callback
        self._drowsy_sleep_enabled_callback = drowsy_sleep_enabled_callback
        self._drowsy_sleep_demo_callback = drowsy_sleep_demo_callback
        self._quit_callback = quit_callback

        self.show_hide_action = QAction("隐藏桌宠", self)
        self.pause_resume_action = QAction("暂停动画", self)
        self.small_size_action = QAction("小：240 × 360", self)
        self.default_size_action = QAction("默认：280 × 420", self)
        self.large_size_action = QAction("大：320 × 480", self)
        self.always_on_top_action = QAction("始终置顶", self)
        self.drowsy_sleep_on_action = QAction("开", self)
        self.drowsy_sleep_off_action = QAction("关", self)
        self.drowsy_sleep_demo_action = QAction("演示", self)
        self.settings_action = QAction("设置", self)
        self.reset_position_action = QAction("重置位置", self)
        self.quit_action = QAction("退出桌宠", self)

        self.size_action_group = QActionGroup(self)
        self.size_action_group.setExclusive(True)
        self._size_actions = {
            PetSize.SMALL: self.small_size_action,
            PetSize.DEFAULT: self.default_size_action,
            PetSize.LARGE: self.large_size_action,
        }
        for action in self._size_actions.values():
            action.setCheckable(True)
            self.size_action_group.addAction(action)
        self.always_on_top_action.setCheckable(True)
        self.drowsy_sleep_action_group = QActionGroup(self)
        self.drowsy_sleep_action_group.setExclusive(True)
        for action in (self.drowsy_sleep_on_action, self.drowsy_sleep_off_action):
            action.setCheckable(True)
            self.drowsy_sleep_action_group.addAction(action)

        self.show_hide_action.triggered.connect(self._show_hide_callback)
        self.pause_resume_action.triggered.connect(self._toggle_animation)
        for size, action in self._size_actions.items():
            action.triggered.connect(lambda checked=False, selected=size: self._select_size(selected, checked))
        self.always_on_top_action.triggered.connect(self._settings_service.set_always_on_top)
        self.drowsy_sleep_on_action.triggered.connect(
            lambda checked=False: self._select_drowsy_sleep(True, checked)
        )
        self.drowsy_sleep_off_action.triggered.connect(
            lambda checked=False: self._select_drowsy_sleep(False, checked)
        )
        self.drowsy_sleep_demo_action.triggered.connect(self._drowsy_sleep_demo_callback)
        self.settings_action.triggered.connect(self._show_settings_callback)
        self.reset_position_action.triggered.connect(self._reset_position_callback)
        self.quit_action.triggered.connect(self._quit_callback)

    @property
    def all_actions(self) -> tuple[QAction, ...]:
        return (
            self.show_hide_action,
            self.pause_resume_action,
            self.small_size_action,
            self.default_size_action,
            self.large_size_action,
            self.always_on_top_action,
            self.drowsy_sleep_on_action,
            self.drowsy_sleep_off_action,
            self.drowsy_sleep_demo_action,
            self.settings_action,
            self.reset_position_action,
            self.quit_action,
        )

    def create_menu(self, parent: QWidget, *, tray_menu: bool = False) -> QMenu:
        """Build a menu shell around the same persistent QAction objects."""
        menu = QMenu(parent)
        if tray_menu:
            menu.addAction(self.show_hide_action)
            menu.addSeparator()
        menu.addAction(self.pause_resume_action)
        autonomous_menu = QMenu("自主动作", menu)
        menu.addMenu(autonomous_menu)
        drowsy_sleep_menu = QMenu("打瞌睡", autonomous_menu)
        autonomous_menu.addMenu(drowsy_sleep_menu)
        drowsy_sleep_menu.addAction(self.drowsy_sleep_on_action)
        drowsy_sleep_menu.addAction(self.drowsy_sleep_off_action)
        drowsy_sleep_menu.addSeparator()
        drowsy_sleep_menu.addAction(self.drowsy_sleep_demo_action)
        size_menu = menu.addMenu("尺寸")
        for action in self._size_actions.values():
            size_menu.addAction(action)
        menu.addAction(self.always_on_top_action)
        menu.addAction(self.settings_action)
        menu.addAction(self.reset_position_action)
        if not tray_menu:
            menu.addAction(self.show_hide_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        return menu

    def sync(
        self,
        settings: UserSettings,
        *,
        window_visible: bool,
        tray_available: bool,
    ) -> None:
        """Synchronize labels, checks, and the no-tray hide safeguard."""
        self.show_hide_action.setText("隐藏桌宠" if window_visible else "显示桌宠")
        self.show_hide_action.setEnabled(tray_available or not window_visible)
        self.pause_resume_action.setText("暂停动画" if settings.animation_enabled else "恢复动画")
        self._size_actions[settings.size].setChecked(True)
        self.always_on_top_action.setChecked(settings.always_on_top)
        selected_sleep_action = (
            self.drowsy_sleep_on_action
            if settings.drowsy_sleep_enabled
            else self.drowsy_sleep_off_action
        )
        selected_sleep_action.setChecked(True)

    def _toggle_animation(self) -> None:
        self._settings_service.set_animation_enabled(not self._settings_service.current.animation_enabled)

    def _select_size(self, size: PetSize, checked: bool) -> None:
        if checked:
            self._settings_service.set_size(size)

    def _select_drowsy_sleep(self, enabled: bool, checked: bool) -> None:
        if checked:
            self._drowsy_sleep_enabled_callback(enabled)
