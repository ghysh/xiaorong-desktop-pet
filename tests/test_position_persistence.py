"""Pure visibility and restored-position behavior across desktop topology changes."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from desktop_pet.settings.model import UserSettings
from desktop_pet.settings.service import position_has_minimum_visibility, resolve_window_position


def test_primary_negative_secondary_and_exact_minimum_visibility_restore() -> None:
    screens = {"primary": QRect(0, 0, 1920, 1040), "left": QRect(-1280, 0, 1280, 984)}
    size = QSize(280, 420)
    for settings in (
        UserSettings(window_x=100, window_y=100, screen_name="primary"),
        UserSettings(window_x=-900, window_y=100, screen_name="left"),
        UserSettings(window_x=1880, window_y=1000, screen_name="primary"),
    ):
        position, corrected = resolve_window_position(settings, size, screens, QPoint(1500, 600))
        assert position == QPoint(settings.window_x, settings.window_y)
        assert not corrected
        assert position_has_minimum_visibility(position, size, screens)


def test_removed_screen_and_resolution_change_fall_back_to_pointer_default() -> None:
    screens = {"primary": QRect(0, 0, 1366, 728)}
    default = QPoint(1062, 284)
    for settings in (
        UserSettings(window_x=-900, window_y=100, screen_name="removed"),
        UserSettings(window_x=3000, window_y=2000, screen_name="primary"),
    ):
        position, corrected = resolve_window_position(settings, QSize(280, 420), screens, default)
        assert position == default
        assert corrected


def test_remember_position_false_ignores_saved_coordinates() -> None:
    settings = UserSettings(remember_position=False)
    default = QPoint(500, 300)
    position, corrected = resolve_window_position(
        settings,
        QSize(280, 420),
        {"primary": QRect(0, 0, 1920, 1080)},
        default,
    )
    assert position == default
    assert not corrected
