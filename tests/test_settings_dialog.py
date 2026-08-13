"""Offscreen settings-dialog Apply, OK-style values, Cancel, and defaults tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.app import create_application
from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.settings.repository import SettingsRepository
from desktop_pet.settings.service import SettingsService
from desktop_pet.ui.settings_dialog import SettingsDialog


def test_apply_updates_service_while_cancel_discards_unapplied_controls(tmp_path: Path) -> None:
    create_application(["pytest-settings-dialog"])
    service = SettingsService(SettingsRepository(tmp_path))
    dialog = SettingsDialog(service)
    dialog.size_combo.setCurrentIndex(dialog.size_combo.findData(PetSize.SMALL.name))
    dialog.always_on_top_checkbox.setChecked(False)
    applied = dialog.apply_changes()
    assert applied.size is PetSize.SMALL
    assert not service.current.always_on_top

    dialog.animation_enabled_checkbox.setChecked(False)
    dialog.reject()
    assert service.current.animation_enabled
    dialog.close()


def test_restore_defaults_only_changes_controls_until_apply(tmp_path: Path) -> None:
    create_application(["pytest-settings-defaults"])
    service = SettingsService(SettingsRepository(tmp_path))
    service.apply(UserSettings(size=PetSize.LARGE, always_on_top=False))
    dialog = SettingsDialog(service)
    dialog._show_defaults()
    assert service.current.size is PetSize.LARGE
    assert dialog.size_combo.currentData() == PetSize.DEFAULT.name
    assert dialog.apply_changes() == UserSettings()
    dialog.close()


def test_unexposed_drowsy_sleep_setting_is_preserved_until_restore_defaults(
    tmp_path: Path,
) -> None:
    create_application(["pytest-settings-drowsy"])
    service = SettingsService(SettingsRepository(tmp_path))
    service.set_drowsy_sleep_enabled(False)
    dialog = SettingsDialog(service)
    assert dialog.apply_changes().drowsy_sleep_enabled is False
    dialog._show_defaults()
    assert dialog.apply_changes().drowsy_sleep_enabled is True
    dialog.close()
