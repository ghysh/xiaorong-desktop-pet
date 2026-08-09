"""Unit tests for screen-safe desktop-pet geometry without a real display."""

import pytest
from PySide6.QtCore import QPoint, QRect, QSize

from desktop_pet.ui.geometry import calculate_bottom_right_position, ensure_window_visible


def test_bottom_right_position_uses_available_geometry_and_margin() -> None:
    position = calculate_bottom_right_position(QRect(0, 0, 1920, 1040), QSize(280, 420), 24)

    assert position == QPoint(1616, 596)


def test_bottom_right_position_supports_negative_coordinate_secondary_screen() -> None:
    position = calculate_bottom_right_position(QRect(-1600, 0, 1600, 900), QSize(280, 420), 24)

    assert position == QPoint(-304, 456)


def test_bottom_right_position_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="positive"):
        calculate_bottom_right_position(QRect(0, 0, 800, 600), QSize(0, 420), 24)
    with pytest.raises(ValueError, match="negative"):
        calculate_bottom_right_position(QRect(0, 0, 800, 600), QSize(280, 420), -1)


def test_visible_window_position_is_unchanged_when_already_visible_on_any_screen() -> None:
    screens = (QRect(-1600, 0, 1600, 900), QRect(0, 0, 1920, 1040))
    proposed = QRect(-100, 100, 280, 420)

    assert ensure_window_visible(proposed, screens, QSize(40, 40)) == proposed.topLeft()


def test_visible_window_position_clamps_an_offscreen_window_to_minimum_visible_area() -> None:
    proposed = QRect(-2000, -1000, 280, 420)
    corrected = ensure_window_visible(proposed, (QRect(0, 0, 1920, 1040),), QSize(40, 40))
    corrected_rect = QRect(corrected, proposed.size())
    visible_area = corrected_rect.intersected(QRect(0, 0, 1920, 1040))

    assert corrected == QPoint(-240, -380)
    assert visible_area.width() >= 40
    assert visible_area.height() >= 40


def test_visible_window_position_rejects_missing_screen_geometry() -> None:
    with pytest.raises(ValueError, match="No available"):
        ensure_window_visible(QRect(0, 0, 280, 420), (), QSize(40, 40))
