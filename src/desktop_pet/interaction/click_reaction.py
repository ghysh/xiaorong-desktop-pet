"""Deterministic 260 ms paint-only click feedback curve."""

from __future__ import annotations

from math import isfinite

from desktop_pet.animation.easing import ease_in_out_sine
from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.config import CLICK_REACTION_DURATION_MS


def _interpolate(left: float, right: float, weight: float) -> float:
    return left + (right - left) * weight


def click_reaction_transform(elapsed_ms: float) -> AnimationTransform:
    """Return the feet-anchored local transform for a deterministic elapsed time."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("Click-reaction elapsed milliseconds must be finite and nonnegative.")
    if elapsed_ms >= CLICK_REACTION_DURATION_MS:
        return AnimationTransform.identity()

    if elapsed_ms <= 90.0:
        weight = ease_in_out_sine(elapsed_ms / 90.0)
        return AnimationTransform(
            offset_y=_interpolate(0.0, 1.0, weight),
            scale_x=_interpolate(1.0, 1.010, weight),
            scale_y=_interpolate(1.0, 0.992, weight),
        )
    if elapsed_ms <= 180.0:
        weight = ease_in_out_sine((elapsed_ms - 90.0) / 90.0)
        return AnimationTransform(
            offset_y=_interpolate(1.0, -0.5, weight),
            scale_x=_interpolate(1.010, 0.997, weight),
            scale_y=_interpolate(0.992, 1.003, weight),
        )

    weight = ease_in_out_sine((elapsed_ms - 180.0) / 80.0)
    return AnimationTransform(
        offset_y=_interpolate(-0.5, 0.0, weight),
        scale_x=_interpolate(0.997, 1.0, weight),
        scale_y=_interpolate(1.003, 1.0, weight),
    )
