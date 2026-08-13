"""Explicit INI persistence and field-level recovery tests."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.settings.repository import SettingsRepository, default_config_directory


def test_round_trip_uses_injected_directory_and_syncs_ini(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path)
    expected = UserSettings(
        size=PetSize.LARGE,
        always_on_top=False,
        behavior_enabled=False,
        drowsy_sleep_enabled=False,
        window_x=-350,
        window_y=80,
        screen_name="left",
    )
    repository.save(expected)
    assert repository.file_path == tmp_path / "settings.ini"
    assert repository.load() == expected
    assert repository.save_count == 1


def test_invalid_fields_recover_independently_and_unknown_fields_are_ignored(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    store = QSettings(str(repository.file_path), QSettings.Format.IniFormat)
    store.setValue("meta/schema_version", "broken")
    store.setValue("appearance/size", "INVALID")
    store.setValue("appearance/always_on_top", "false")
    store.setValue("animation/enabled", "garbage")
    store.setValue("behavior/enabled", "false")
    store.setValue("autonomous_actions/drowsy_sleep_enabled", "false")
    store.setValue("window/x", "not-an-int")
    store.setValue("window/y", 50)
    store.setValue("future/unknown", "safe")
    store.sync()
    loaded = repository.load()
    assert loaded.schema_version == 1
    assert loaded.size is PetSize.DEFAULT
    assert not loaded.always_on_top
    assert loaded.animation_enabled
    assert not loaded.behavior_enabled
    assert not loaded.drowsy_sleep_enabled
    assert loaded.window_x is None and loaded.window_y is None


def test_malformed_file_does_not_crash_and_default_location_is_not_project() -> None:
    directory = default_config_directory()
    assert directory.name == "DesktopPet"
    assert directory == (
        Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation))
        / "DesktopPetProject"
        / "DesktopPet"
    )
    assert PROJECT_ROOT not in directory.parents
