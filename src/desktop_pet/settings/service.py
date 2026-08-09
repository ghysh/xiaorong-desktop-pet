"""Application-facing settings updates and pure position restoration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Signal

from desktop_pet.config import MIN_VISIBLE_HEIGHT, MIN_VISIBLE_WIDTH
from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.settings.repository import SettingsRepository


def position_has_minimum_visibility(
    position: QPoint,
    window_size: QSize,
    screen_geometries: Mapping[str, QRect],
) -> bool:
    """Return whether at least 40 by 40 logical pixels remain on any usable screen."""
    proposed = QRect(position, window_size)
    required_width = min(MIN_VISIBLE_WIDTH, window_size.width())
    required_height = min(MIN_VISIBLE_HEIGHT, window_size.height())
    return any(
        proposed.intersected(geometry).width() >= required_width
        and proposed.intersected(geometry).height() >= required_height
        for geometry in screen_geometries.values()
    )


def resolve_window_position(
    settings: UserSettings,
    window_size: QSize,
    screen_geometries: Mapping[str, QRect],
    default_position: QPoint,
) -> tuple[QPoint, bool]:
    """Restore a valid saved point or return the pointer-screen default with correction flag."""
    if not screen_geometries:
        raise ValueError("At least one screen geometry is required to restore a position.")
    if not settings.remember_position or settings.window_x is None or settings.window_y is None:
        return QPoint(default_position), False
    if settings.screen_name is not None and settings.screen_name not in screen_geometries:
        return QPoint(default_position), True
    saved = QPoint(settings.window_x, settings.window_y)
    if position_has_minimum_visibility(saved, window_size, screen_geometries):
        return saved, False
    return QPoint(default_position), True


class SettingsService(QObject):
    """Own current immutable settings, persistence, and change notifications."""

    settings_changed = Signal(object)

    def __init__(self, repository: SettingsRepository, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._settings = repository.load()

    @property
    def repository(self) -> SettingsRepository:
        return self._repository

    @property
    def current(self) -> UserSettings:
        return self._settings

    def apply(self, settings: UserSettings, *, persist: bool = True) -> UserSettings:
        if not isinstance(settings, UserSettings):
            raise ValueError("SettingsService can only apply UserSettings.")
        if not settings.remember_position and (
            settings.window_x is not None or settings.window_y is not None or settings.screen_name is not None
        ):
            settings = replace(settings, window_x=None, window_y=None, screen_name=None)
        self._settings = settings
        if persist:
            self._repository.save(settings)
        self.settings_changed.emit(settings)
        return settings

    def set_size(self, size: PetSize) -> UserSettings:
        return self.apply(replace(self._settings, size=size))

    def set_always_on_top(self, enabled: bool) -> UserSettings:
        return self.apply(replace(self._settings, always_on_top=enabled))

    def set_animation_enabled(self, enabled: bool) -> UserSettings:
        return self.apply(replace(self._settings, animation_enabled=enabled))

    def set_behavior_enabled(self, enabled: bool) -> UserSettings:
        return self.apply(replace(self._settings, behavior_enabled=enabled))

    def set_click_reaction_enabled(self, enabled: bool) -> UserSettings:
        return self.apply(replace(self._settings, click_reaction_enabled=enabled))

    def set_remember_position(self, enabled: bool) -> UserSettings:
        updates: dict[str, object] = {"remember_position": enabled}
        if not enabled:
            updates.update(window_x=None, window_y=None, screen_name=None)
        return self.apply(replace(self._settings, **updates))

    def save_position(self, position: QPoint, screen_name: str | None) -> UserSettings:
        if not self._settings.remember_position:
            return self._settings
        return self.apply(
            replace(
                self._settings,
                window_x=position.x(),
                window_y=position.y(),
                screen_name=screen_name,
            )
        )

    def reset_position(self) -> UserSettings:
        return self.apply(replace(self._settings, window_x=None, window_y=None, screen_name=None))

    def save_current(self) -> None:
        self._repository.save(self._settings)
