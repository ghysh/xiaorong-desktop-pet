"""Pure coordinate mapping and cached-QImage alpha hit testing."""

from __future__ import annotations

from math import floor

from PySide6.QtCore import QPoint, QPointF, QSize
from PySide6.QtGui import QImage

from desktop_pet.config import ALPHA_HIT_TEST_THRESHOLD


def map_window_point_to_source(
    point: QPointF,
    window_size: QSize,
    source_size: QSize,
) -> QPoint | None:
    """Map a point through a centred keep-aspect-ratio fit into source pixels."""
    if window_size.width() <= 0 or window_size.height() <= 0:
        raise ValueError("Window size must be positive for alpha hit testing.")
    if source_size.width() <= 0 or source_size.height() <= 0:
        raise ValueError("Source size must be positive for alpha hit testing.")
    if point.x() < 0 or point.y() < 0 or point.x() >= window_size.width() or point.y() >= window_size.height():
        return None

    scale = min(
        window_size.width() / source_size.width(),
        window_size.height() / source_size.height(),
    )
    rendered_width = source_size.width() * scale
    rendered_height = source_size.height() * scale
    offset_x = (window_size.width() - rendered_width) / 2.0
    offset_y = (window_size.height() - rendered_height) / 2.0
    rendered_x = point.x() - offset_x
    rendered_y = point.y() - offset_y
    if rendered_x < 0 or rendered_y < 0 or rendered_x >= rendered_width or rendered_y >= rendered_height:
        return None

    source_x = min(source_size.width() - 1, floor(rendered_x / scale))
    source_y = min(source_size.height() - 1, floor(rendered_y / scale))
    return QPoint(source_x, source_y)


def is_character_pixel(
    point: QPointF,
    window_size: QSize,
    alpha_image: QImage,
    threshold: int = ALPHA_HIT_TEST_THRESHOLD,
) -> bool:
    """Return whether a cached source image has enough alpha at a window point."""
    if alpha_image.isNull():
        raise ValueError("Alpha image cannot be null.")
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
        raise ValueError("Alpha threshold must be an integer between 0 and 255.")
    source_point = map_window_point_to_source(point, window_size, alpha_image.size())
    if source_point is None:
        return False
    return alpha_image.pixelColor(source_point).alpha() >= threshold
