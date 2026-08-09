"""Unit checks for the immutable local drawing-transform value object."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, QRectF

from desktop_pet.animation.transform import AnimationTransform, transformed_bounds


def test_identity_and_defaults_are_no_op_values() -> None:
    assert AnimationTransform.identity() == AnimationTransform()
    assert AnimationTransform().as_tuple() == (0.0, 0.0, 1.0, 1.0, 0.0)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"offset_x": math.inf},
        {"offset_y": 21.0},
        {"scale_x": 0.94},
        {"scale_y": 1.06},
        {"rotation_degrees": 10.1},
    ),
)
def test_transform_rejects_invalid_ranges(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        AnimationTransform(**kwargs)


def test_approximate_equality_and_composition_are_local_only() -> None:
    base = AnimationTransform(offset_y=1.0, scale_x=1.001, rotation_degrees=0.5)
    drag = AnimationTransform(rotation_degrees=-0.75)

    assert base.is_close(AnimationTransform(offset_y=1.0000001, scale_x=1.001, rotation_degrees=0.5))
    assert not base.is_close(drag)
    assert base.combined_with(drag) == AnimationTransform(offset_y=1.0, scale_x=1.001, rotation_degrees=-0.25)
    assert "desktop" not in AnimationTransform.__dataclass_fields__


def test_qtransform_keeps_anchor_fixed_except_for_overall_offset() -> None:
    anchor = QPointF(140.0, 409.0)
    transform = AnimationTransform(offset_x=1.25, offset_y=-1.5, scale_x=1.002, scale_y=1.008, rotation_degrees=4.0)

    mapped_anchor = transform.to_qtransform(anchor).map(anchor)

    assert mapped_anchor.x() == pytest.approx(anchor.x() + transform.offset_x)
    assert mapped_anchor.y() == pytest.approx(anchor.y() + transform.offset_y)


def test_transformed_bounds_expands_and_moves_using_the_local_transform() -> None:
    bounds = QRectF(65.625, 11.484375, 148.203125, 397.3046875)
    anchor = QPointF(139.7265625, 408.7890625)

    transformed = transformed_bounds(
        bounds,
        anchor,
        AnimationTransform(offset_y=-1.5, scale_y=1.008, rotation_degrees=0.7),
    )

    assert transformed.top() < bounds.top()
    assert transformed.bottom() < bounds.bottom()
    assert transformed.width() > bounds.width()
