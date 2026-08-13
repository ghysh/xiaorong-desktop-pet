"""Tray unavailability fallback and in-memory icon construction tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QSystemTrayIcon

from desktop_pet.app import create_application
from desktop_pet.settings.repository import SettingsRepository
from desktop_pet.settings.service import SettingsService
from desktop_pet.ui import tray_controller as tray_module
from desktop_pet.ui.action_registry import ActionRegistry
from desktop_pet.ui.pet_window import PetWindow
from desktop_pet.ui.tray_controller import TrayController, _create_cached_character_icon


def _registry(service: SettingsService) -> ActionRegistry:
    return ActionRegistry(
        service,
        show_hide_callback=lambda: None,
        show_settings_callback=lambda: None,
        reset_position_callback=lambda: None,
        drowsy_sleep_enabled_callback=service.set_drowsy_sleep_enabled,
        drowsy_sleep_demo_callback=lambda: None,
        quit_callback=lambda: None,
    )


def test_unavailable_tray_warns_and_keeps_window_logic_alive(tmp_path: Path, monkeypatch) -> None:
    create_application(["pytest-tray-unavailable"])
    window = PetWindow()
    service = SettingsService(SettingsRepository(tmp_path))
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    monkeypatch.setattr(tray_module, "_TRAY_WARNING_EMITTED", False)
    with pytest.warns(RuntimeWarning, match="unavailable"):
        tray = TrayController(window, _registry(service), restore_callback=lambda: None)
    assert not tray.available
    assert tray.tray_icon is None
    tray.show()
    tray.shutdown()
    window.close()


def test_tray_icon_is_built_from_cached_character_pixmap(tmp_path: Path) -> None:
    del tmp_path
    create_application(["pytest-tray-icon"])
    window = PetWindow()
    icon = _create_cached_character_icon(window)
    assert not icon.isNull()
    assert not icon.pixmap(64, 64).isNull()
    window.close()
