"""Immutable internal drawing transforms and alpha-bound geometry helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QTransform


@dataclass(frozen=True, slots=True)
class AnimationTransform:
    """A bounded local paint transform that never stores desktop window coordinates."""

    offset_x: float = 0.0
    offset_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation_degrees: float = 0.0

    def __post_init__(self) -> None:
        for name in ("offset_x", "offset_y", "scale_x", "scale_y", "rotation_degrees"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite.")
        if abs(self.offset_x) > 20 or abs(self.offset_y) > 20:
            raise ValueError("Animation offsets must remain within 20 logical pixels.")
        if not 0.95 <= self.scale_x <= 1.05 or not 0.95 <= self.scale_y <= 1.05:
            raise ValueError("Animation scales must remain between 0.95 and 1.05.")
        if abs(self.rotation_degrees) > 10:
            raise ValueError("Animation rotation must remain within 10 degrees.")

    @classmethod
    def identity(cls) -> AnimationTransform:
        """Return the no-op local drawing transform."""
        return cls()

    def is_close(self, other: AnimationTransform, *, tolerance: float = 1e-6) -> bool:
        """Compare transforms component by component with a small absolute tolerance."""
        if tolerance < 0:
            raise ValueError("Transform comparison tolerance cannot be negative.")
        return all(
            abs(left - right) <= tolerance
            for left, right in zip(self.as_tuple(), other.as_tuple(), strict=True)
        )

    def combined_with(self, other: AnimationTransform) -> AnimationTransform:
        """Compose another local transform without introducing desktop coordinates."""
        return AnimationTransform(
            offset_x=self.offset_x + other.offset_x,
            offset_y=self.offset_y + other.offset_y,
            scale_x=self.scale_x * other.scale_x,
            scale_y=self.scale_y * other.scale_y,
            rotation_degrees=self.rotation_degrees + other.rotation_degrees,
        )

    def as_tuple(self) -> tuple[float, float, float, float, float]:
        """Return values in the stable order used by diagnostics and tests."""
        return (self.offset_x, self.offset_y, self.scale_x, self.scale_y, self.rotation_degrees)

    def to_qtransform(self, anchor: QPointF) -> QTransform:
        """Build the documented overall-translation, anchor, rotation, scale transform."""
        transform = QTransform()
        transform.translate(self.offset_x, self.offset_y)
        transform.translate(anchor.x(), anchor.y())
        transform.rotate(self.rotation_degrees)
        transform.scale(self.scale_x, self.scale_y)
        transform.translate(-anchor.x(), -anchor.y())
        return transform

    def apply_to_painter(self, painter: QPainter, anchor: QPointF) -> None:
        """Apply this transform to a painter in the prescribed order."""
        painter.translate(self.offset_x, self.offset_y)
        painter.translate(anchor.x(), anchor.y())
        painter.rotate(self.rotation_degrees)
        painter.scale(self.scale_x, self.scale_y)
        painter.translate(-anchor.x(), -anchor.y())


def transformed_bounds(bounds: QRectF, anchor: QPointF, transform: AnimationTransform) -> QRectF:
    """Return the axis-aligned bounds after the documented local draw transform."""
    angle = radians(transform.rotation_degrees)
    cosine = cos(angle)
    sine = sin(angle)
    points: list[QPointF] = []
    for point in (bounds.topLeft(), bounds.topRight(), bounds.bottomLeft(), bounds.bottomRight()):
        relative_x = (point.x() - anchor.x()) * transform.scale_x
        relative_y = (point.y() - anchor.y()) * transform.scale_y
        rotated_x = relative_x * cosine - relative_y * sine
        rotated_y = relative_x * sine + relative_y * cosine
        points.append(
            QPointF(
                anchor.x() + rotated_x + transform.offset_x,
                anchor.y() + rotated_y + transform.offset_y,
            )
        )
    left = min(point.x() for point in points)
    right = max(point.x() for point in points)
    top = min(point.y() for point in points)
    bottom = max(point.y() for point in points)
    return QRectF(left, top, right - left, bottom - top)
