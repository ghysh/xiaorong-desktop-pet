"""Shared QAction identity, exclusivity, callbacks, and synchronized text tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.app import create_application
from desktop_pet.settings.model import PetSize
from desktop_pet.settings.repository import SettingsRepository
from desktop_pet.settings.service import SettingsService
from desktop_pet.ui.action_registry import ActionRegistry
from desktop_pet.ui.pet_window import PetWindow


def test_window_and_tray_menus_share_actions_and_size_group_is_exclusive(tmp_path: Path) -> None:
    create_application(["pytest-actions"])
    service = SettingsService(SettingsRepository(tmp_path))
    calls: list[str] = []
    registry = ActionRegistry(
        service,
        show_hide_callback=lambda: calls.append("visibility"),
        show_settings_callback=lambda: calls.append("settings"),
        reset_position_callback=lambda: calls.append("reset"),
        quit_callback=lambda: calls.append("quit"),
    )
    window = PetWindow()
    window_menu = registry.create_menu(window)
    tray_menu = registry.create_menu(window, tray_menu=True)
    assert registry.pause_resume_action in window_menu.actions()
    assert registry.pause_resume_action in tray_menu.actions()
    assert registry.size_action_group.isExclusive()

    registry.small_size_action.trigger()
    assert service.current.size is PetSize.SMALL
    assert registry.small_size_action.isChecked()
    assert not registry.default_size_action.isChecked()
    registry.sync(service.current, window_visible=True, tray_available=False)
    assert registry.show_hide_action.text() == "隐藏桌宠"
    assert not registry.show_hide_action.isEnabled()
    registry.settings_action.trigger()
    assert calls == ["settings"]
    window_menu.deleteLater()
    tray_menu.deleteLater()
    window.close()
