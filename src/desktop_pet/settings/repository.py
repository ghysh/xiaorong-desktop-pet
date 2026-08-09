"""INI-backed settings persistence using an explicit user configuration path."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from desktop_pet.settings.model import PetSize, UserSettings

SETTINGS_FILE_NAME = "settings.ini"
SETTINGS_DIRECTORY_NAME = "DesktopPet"
CONFIG_ORGANIZATION_NAME = "DesktopPetProject"


def default_config_directory() -> Path:
    """Keep the historical config path independent from the user-visible application name."""
    raw_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation)
    if not raw_location:
        raise RuntimeError("Qt could not resolve the user application configuration directory.")
    return Path(raw_location) / CONFIG_ORGANIZATION_NAME / SETTINGS_DIRECTORY_NAME


class SettingsRepository:
    """Load and save validated settings without accessing any QWidget."""

    def __init__(self, config_directory: Path | str | None = None) -> None:
        self.config_directory = (
            Path(config_directory).resolve() if config_directory is not None else default_config_directory()
        )
        self.file_path = self.config_directory / SETTINGS_FILE_NAME
        self.save_count = 0

    def load(self) -> UserSettings:
        """Recover invalid fields independently while ignoring unknown keys."""
        if not self.file_path.exists():
            return UserSettings()
        store = self._store()
        defaults = UserSettings()
        size = _parse_size(store.value("appearance/size"), defaults.size)
        always_on_top = _parse_bool(
            store.value("appearance/always_on_top"),
            defaults.always_on_top,
        )
        animation_enabled = _parse_bool(
            store.value("animation/enabled"),
            defaults.animation_enabled,
        )
        behavior_enabled = _parse_bool(
            store.value("behavior/enabled"),
            defaults.behavior_enabled,
        )
        click_reaction_enabled = _parse_bool(
            store.value("interaction/click_reaction_enabled"),
            defaults.click_reaction_enabled,
        )
        remember_position = _parse_bool(
            store.value("window/remember_position"),
            defaults.remember_position,
        )
        window_x = _parse_optional_int(store.value("window/x"))
        window_y = _parse_optional_int(store.value("window/y"))
        if window_x is None or window_y is None:
            window_x = None
            window_y = None
            screen_name = None
        else:
            screen_name = _parse_optional_text(store.value("window/screen_name"))
        return UserSettings(
            schema_version=1,
            size=size,
            always_on_top=always_on_top,
            animation_enabled=animation_enabled,
            behavior_enabled=behavior_enabled,
            click_reaction_enabled=click_reaction_enabled,
            remember_position=remember_position,
            window_x=window_x,
            window_y=window_y,
            screen_name=screen_name,
        )

    def save(self, settings: UserSettings) -> None:
        """Synchronize an explicit INI file and fail clearly on write errors."""
        if not isinstance(settings, UserSettings):
            raise ValueError("SettingsRepository can only save UserSettings.")
        self.config_directory.mkdir(parents=True, exist_ok=True)
        store = self._store()
        store.setValue("meta/schema_version", settings.schema_version)
        store.setValue("appearance/size", settings.size.name)
        store.setValue("appearance/always_on_top", settings.always_on_top)
        store.setValue("animation/enabled", settings.animation_enabled)
        store.setValue("behavior/enabled", settings.behavior_enabled)
        store.setValue("interaction/click_reaction_enabled", settings.click_reaction_enabled)
        store.setValue("window/remember_position", settings.remember_position)
        if settings.remember_position and settings.window_x is not None and settings.window_y is not None:
            store.setValue("window/x", settings.window_x)
            store.setValue("window/y", settings.window_y)
            if settings.screen_name is None:
                store.remove("window/screen_name")
            else:
                store.setValue("window/screen_name", settings.screen_name)
        else:
            store.remove("window/x")
            store.remove("window/y")
            store.remove("window/screen_name")
        store.sync()
        if store.status() is not QSettings.Status.NoError:
            raise OSError(f"Failed to save desktop-pet settings: {self.file_path}; status={store.status().name}")
        self.save_count += 1

    def _store(self) -> QSettings:
        store = QSettings(str(self.file_path), QSettings.Format.IniFormat)
        store.setFallbacksEnabled(False)
        return store


def _parse_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def _parse_optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _parse_size(value: object, default: PetSize) -> PetSize:
    if isinstance(value, PetSize):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in PetSize.__members__:
            return PetSize[normalized]
        compact = normalized.lower().replace(" ", "")
        for size in PetSize:
            if compact in {f"{size.width}x{size.height}", f"{size.width},{size.height}"}:
                return size
    return default
