"""Screen-safe geometry helpers for the static desktop-pet window."""

from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QSize


def calculate_bottom_right_position(
    available_geometry: QRect,
    window_size: QSize,
    margin: int,
) -> QPoint:
    """Return a bottom-right logical-pixel position inside one screen's usable area."""
    if window_size.width() <= 0 or window_size.height() <= 0:
        raise ValueError("Window size must be positive.")
    if margin < 0:
        raise ValueError("Startup margin cannot be negative.")

    return QPoint(
        available_geometry.x() + available_geometry.width() - window_size.width() - margin,
        available_geometry.y() + available_geometry.height() - window_size.height() - margin,
    )


def ensure_window_visible(
    proposed_rect: QRect,
    available_screens: Sequence[QRect],
    minimum_visible_size: QSize,
) -> QPoint:
    """Keep a minimum rectangle visible on one available screen without changing its size."""
    if minimum_visible_size.width() <= 0 or minimum_visible_size.height() <= 0:
        raise ValueError("Minimum visible size must be positive.")
    if proposed_rect.width() <= 0 or proposed_rect.height() <= 0:
        raise ValueError("Proposed window rectangle must have positive dimensions.")
    if not available_screens:
        raise ValueError("No available screen geometry was supplied.")

    required_width = min(minimum_visible_size.width(), proposed_rect.width())
    required_height = min(minimum_visible_size.height(), proposed_rect.height())
    for screen in available_screens:
        intersection = proposed_rect.intersected(screen)
        if intersection.width() >= required_width and intersection.height() >= required_height:
            return proposed_rect.topLeft()

    target_screen = min(
        available_screens,
        key=lambda screen: _squared_center_distance(proposed_rect, screen),
    )
    minimum_x = target_screen.x() - proposed_rect.width() + required_width
    maximum_x = target_screen.x() + target_screen.width() - required_width
    minimum_y = target_screen.y() - proposed_rect.height() + required_height
    maximum_y = target_screen.y() + target_screen.height() - required_height

    return QPoint(
        min(max(proposed_rect.x(), minimum_x), maximum_x),
        min(max(proposed_rect.y(), minimum_y), maximum_y),
    )


def _squared_center_distance(first: QRect, second: QRect) -> int:
    """Return a deterministic distance for choosing the nearest screen geometry."""
    first_center = first.center()
    second_center = second.center()
    horizontal = first_center.x() - second_center.x()
    vertical = first_center.y() - second_center.y()
    return horizontal * horizontal + vertical * vertical
