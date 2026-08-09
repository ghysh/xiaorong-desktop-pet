"""Pure cached-image alpha hit-test coverage for all approved sizes."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize
from PySide6.QtGui import QColor, QImage

from desktop_pet.interaction.hit_test import is_character_pixel, map_window_point_to_source


def _alpha_image() -> QImage:
    image = QImage(4, 6, QImage.Format.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(1, 2, QColor(20, 30, 40, 255))
    image.setPixelColor(2, 2, QColor(20, 30, 40, 15))
    image.setPixelColor(2, 3, QColor(20, 30, 40, 16))
    return image


def test_transparent_visible_and_threshold_pixels_are_distinguished() -> None:
    image = _alpha_image()
    window = QSize(280, 420)
    assert not is_character_pixel(QPointF(1, 1), window, image)
    assert is_character_pixel(QPointF(105, 175), window, image)
    assert not is_character_pixel(QPointF(175, 175), window, image)
    assert is_character_pixel(QPointF(175, 245), window, image)


def test_mapping_is_consistent_for_all_three_two_by_three_sizes() -> None:
    image = _alpha_image()
    for window in (QSize(240, 360), QSize(280, 420), QSize(320, 480)):
        point = QPointF(window.width() * 1.5 / 4, window.height() * 2.5 / 6)
        assert map_window_point_to_source(point, window, image.size()).toTuple() == (1, 2)
        assert is_character_pixel(point, window, image)


def test_outside_points_are_rejected_without_touching_image_storage() -> None:
    image = _alpha_image()
    before = image.cacheKey()
    for point in (QPointF(-1, 0), QPointF(0, -1), QPointF(280, 1), QPointF(1, 420)):
        assert map_window_point_to_source(point, QSize(280, 420), image.size()) is None
        assert not is_character_pixel(point, QSize(280, 420), image)
    assert image.cacheKey() == before
