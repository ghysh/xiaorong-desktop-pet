"""Pure screen-safe bubble placement tests, including negative-coordinate displays."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize

from desktop_pet.ui.dialogue_bubble import TailDirection, calculate_bubble_placement


def _assert_inside(position, size: QSize, screen: QRect, margin: int = 12) -> None:
    safe = screen.adjusted(margin, margin, -margin, -margin)
    assert position.x() >= safe.left()
    assert position.y() >= safe.top()
    assert position.x() + size.width() <= safe.left() + safe.width()
    assert position.y() + size.height() <= safe.top() + safe.height()


def test_default_position_is_above_alpha_bounds() -> None:
    size = QSize(240, 100)
    pet = QRect(500, 400, 180, 380)
    placement = calculate_bubble_placement(size, pet, QRect(0, 0, 1440, 900), screen_margin=12, pet_gap=8)

    assert placement.tail_direction is TailDirection.BOTTOM
    assert placement.position.y() + size.height() < pet.top()
    _assert_inside(placement.position, size, QRect(0, 0, 1440, 900))


def test_left_right_top_and_taskbar_boundaries_remain_inside_available_geometry() -> None:
    screen = QRect(0, 0, 1280, 680)
    size = QSize(300, 130)
    pets = (
        QRect(0, 250, 150, 360),
        QRect(1130, 250, 150, 360),
        QRect(530, 0, 180, 360),
        QRect(530, 500, 180, 360),
    )
    for pet in pets:
        placement = calculate_bubble_placement(size, pet, screen, screen_margin=12, pet_gap=8)
        _assert_inside(placement.position, size, screen)


def test_negative_coordinate_screen_and_three_pet_sizes() -> None:
    screen = QRect(-1920, -180, 1920, 1080)
    bubble = QSize(260, 120)
    for width, height in ((240, 360), (280, 420), (320, 480)):
        pet = QRect(-400, 820 - height, width, height)
        placement = calculate_bubble_placement(bubble, pet, screen, screen_margin=12, pet_gap=8)
        _assert_inside(placement.position, bubble, screen)
