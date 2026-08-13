"""Pure screen-safe bubble placement tests, including negative-coordinate displays."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, QRect, QSize

from desktop_pet.ui.dialogue_bubble import TailDirection, calculate_bubble_placement


def _assert_inside(position, size: QSize, screen: QRect, margin: int = 12) -> None:
    safe = screen.adjusted(margin, margin, -margin, -margin)
    assert position.x() >= safe.left()
    assert position.y() >= safe.top()
    assert position.x() + size.width() <= safe.left() + safe.width()
    assert position.y() + size.height() <= safe.top() + safe.height()


def _expected_anchor(pet: QRect, direction: TailDirection) -> QPointF:
    if direction is TailDirection.BOTTOM:
        return QPointF(pet.left() + pet.width() / 2, pet.top())
    if direction is TailDirection.TOP:
        return QPointF(pet.left() + pet.width() / 2, pet.top() + pet.height())
    if direction is TailDirection.RIGHT:
        return QPointF(pet.left(), pet.top() + pet.height() / 2)
    return QPointF(pet.left() + pet.width(), pet.top() + pet.height() / 2)


def _assert_anchor_matches(placement, pet: QRect) -> None:
    expected = _expected_anchor(pet, placement.tail_direction)
    assert placement.anchor == expected
    assert placement.position.x() + placement.target.x() == pytest.approx(expected.x())
    assert placement.position.y() + placement.target.y() == pytest.approx(expected.y())


def test_default_position_is_above_alpha_bounds() -> None:
    size = QSize(240, 100)
    pet = QRect(500, 400, 180, 380)
    placement = calculate_bubble_placement(size, pet, QRect(0, 0, 1440, 900), screen_margin=12, pet_gap=8)

    assert placement.tail_direction is TailDirection.BOTTOM
    assert placement.position.y() + size.height() < pet.top()
    _assert_inside(placement.position, size, QRect(0, 0, 1440, 900))
    _assert_anchor_matches(placement, pet)


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
        _assert_anchor_matches(placement, pet)


def test_negative_coordinate_screen_and_three_pet_sizes() -> None:
    screen = QRect(-1920, -180, 1920, 1080)
    bubble = QSize(260, 120)
    for width, height in ((240, 360), (280, 420), (320, 480)):
        pet = QRect(-400, 820 - height, width, height)
        placement = calculate_bubble_placement(bubble, pet, screen, screen_margin=12, pet_gap=8)
        _assert_inside(placement.position, bubble, screen)
        _assert_anchor_matches(placement, pet)


@pytest.mark.parametrize(
    ("pet", "expected_direction"),
    (
        (QRect(550, 350, 180, 380), TailDirection.BOTTOM),
        (QRect(0, 0, 180, 380), TailDirection.TOP),
        (QRect(1100, 0, 180, 380), TailDirection.TOP),
        (QRect(0, 300, 180, 380), TailDirection.BOTTOM),
        (QRect(1100, 300, 180, 380), TailDirection.BOTTOM),
        (QRect(0, 180, 180, 380), TailDirection.BOTTOM),
        (QRect(1100, 180, 180, 380), TailDirection.BOTTOM),
    ),
)
def test_centre_corners_and_tight_horizontal_edges_keep_body_and_anchor_connected(
    pet: QRect,
    expected_direction: TailDirection,
) -> None:
    screen = QRect(0, 0, 1280, 900)
    size = QSize(380, 112)
    placement = calculate_bubble_placement(size, pet, screen, screen_margin=12, pet_gap=8)

    assert placement.tail_direction is expected_direction
    _assert_inside(placement.position, size, screen)
    _assert_anchor_matches(placement, pet)


def test_horizontal_edge_avoidance_is_continuous_instead_of_jumping() -> None:
    screen = QRect(0, 0, 1280, 900)
    size = QSize(380, 112)
    for horizontal_positions in (range(80, 141), range(960, 1021)):
        placements = [
            calculate_bubble_placement(size, QRect(x, 300, 180, 380), screen, screen_margin=12, pet_gap=8)
            for x in horizontal_positions
        ]

        assert all(item.tail_direction is TailDirection.BOTTOM for item in placements)
        assert max(
            abs(current.position.x() - previous.position.x())
            for previous, current in zip(placements[:-1], placements[1:], strict=True)
        ) <= 1
        assert max(
            abs(current.target.x() - previous.target.x())
            for previous, current in zip(placements[:-1], placements[1:], strict=True)
        ) <= 1


def test_side_position_is_used_when_neither_above_nor_below_fits() -> None:
    screen = QRect(0, 0, 1280, 400)
    size = QSize(300, 130)
    pet = QRect(550, 90, 180, 220)
    placement = calculate_bubble_placement(size, pet, screen, screen_margin=12, pet_gap=8)

    assert placement.tail_direction in {TailDirection.LEFT, TailDirection.RIGHT}
    _assert_inside(placement.position, size, screen)
    _assert_anchor_matches(placement, pet)
