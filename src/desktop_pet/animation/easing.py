"""Small deterministic easing functions with no Qt dependency."""

from __future__ import annotations

from math import cos, pi


def clamp01(value: float) -> float:
    """Clamp a numeric progress value to the inclusive interval from zero to one."""
    return max(0.0, min(1.0, value))


def linear(progress: float) -> float:
    """Return clamped linear progress."""
    return clamp01(progress)


def ease_in_out_sine(progress: float) -> float:
    """Return a smooth sine ease-in/ease-out progress value."""
    value = clamp01(progress)
    return -(cos(pi * value) - 1.0) / 2.0


def ease_out_cubic(progress: float) -> float:
    """Return a cubic deceleration progress value."""
    value = clamp01(progress)
    return 1.0 - (1.0 - value) ** 3
