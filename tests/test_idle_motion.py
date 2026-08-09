"""Tests for deterministic elapsed-time idle motion."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from desktop_pet.animation.idle_motion import IdleMotionProfile, calculate_idle_transform
from desktop_pet.paths import PROJECT_ROOT


def test_same_elapsed_input_produces_same_transform() -> None:
    profile = IdleMotionProfile()
    assert calculate_idle_transform(12.345, profile) == calculate_idle_transform(12.345, profile)


def test_idle_ranges_remain_within_the_approved_limits() -> None:
    profile = IdleMotionProfile()
    transforms = [calculate_idle_transform(index / 50.0, profile) for index in range(5000)]

    assert all(0.998 <= transform.scale_x <= 1.002 for transform in transforms)
    assert all(0.996 <= transform.scale_y <= 1.008 for transform in transforms)
    assert all(abs(transform.offset_y) <= 1.5 for transform in transforms)
    assert all(abs(transform.rotation_degrees) <= 0.7 for transform in transforms)


def test_combined_idle_cycle_is_continuous_and_stable_for_large_values() -> None:
    profile = IdleMotionProfile()
    beginning = calculate_idle_transform(0.0, profile)
    combined_cycle = calculate_idle_transform(57.6, profile)
    large_value = calculate_idle_transform(10_000_000_000.0, profile)

    assert beginning.is_close(combined_cycle, tolerance=1e-10)
    assert all(math.isfinite(value) for value in large_value.as_tuple())


def test_idle_motion_rejects_nonfinite_elapsed_time() -> None:
    with pytest.raises(ValueError, match="finite"):
        calculate_idle_transform(math.inf, IdleMotionProfile())


def test_idle_runtime_does_not_import_random() -> None:
    source = (PROJECT_ROOT / "src" / "desktop_pet" / "animation" / "idle_motion.py").read_text(encoding="utf-8")
    assert "import random" not in source
    assert Path(__file__).is_file()
