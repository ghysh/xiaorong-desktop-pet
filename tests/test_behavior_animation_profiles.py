"""Animation profile mapping, interpolation, and Stage 7 safety-range tests."""

from __future__ import annotations

import pytest

from desktop_pet.animation.idle_motion import IdleMotionProfile
from desktop_pet.behavior.profiles import (
    ProfileBlend,
    apply_behavior_profile,
    calculate_behavior_transform,
    profile_for_state,
)
from desktop_pet.behavior.state import PetState
from desktop_pet.config import BehaviorConfig


def test_automatic_profiles_have_the_required_relative_strengths() -> None:
    config = BehaviorConfig(behavior_seed=1)
    calm = profile_for_state(PetState.IDLE_CALM, config)
    quiet = profile_for_state(PetState.IDLE_QUIET, config)
    sway = profile_for_state(PetState.IDLE_SWAY, config)
    resting = profile_for_state(PetState.RESTING, config)

    assert quiet.floating_amplitude_multiplier < calm.floating_amplitude_multiplier
    assert quiet.sway_amplitude_multiplier < calm.sway_amplitude_multiplier
    assert sway.sway_amplitude_multiplier > calm.sway_amplitude_multiplier
    assert 0.7 * sway.sway_amplitude_multiplier <= 1.0
    assert resting.floating_amplitude_multiplier == 0.0
    assert resting.sway_amplitude_multiplier == 0.0
    assert resting.breathing_period_multiplier > calm.breathing_period_multiplier


def test_dragging_settling_and_starting_profiles_are_low_risk() -> None:
    config = BehaviorConfig()
    dragging = profile_for_state(PetState.DRAGGING, config)
    settling = profile_for_state(PetState.SETTLING, config)
    starting = profile_for_state(PetState.STARTING, config)

    assert dragging.floating_amplitude_multiplier == 0.0
    assert dragging.sway_amplitude_multiplier == 0.0
    assert dragging.breathing_scale_y_multiplier == pytest.approx(0.30)
    assert settling == dragging
    assert starting.motion_strength == 0.0
    assert calculate_behavior_transform(0.0, IdleMotionProfile(), starting).is_close(
        calculate_behavior_transform(100.0, IdleMotionProfile(), starting)
    )


def test_profile_blend_is_smooth_and_has_exact_endpoints() -> None:
    config = BehaviorConfig()
    source = profile_for_state(PetState.IDLE_SWAY, config)
    target = profile_for_state(PetState.IDLE_QUIET, config)
    blend = ProfileBlend(source, target, 10.0, 0.35)

    assert blend.profile_at(10.0) == source
    midpoint = blend.profile_at(10.175)
    assert target.sway_amplitude_multiplier < midpoint.sway_amplitude_multiplier < source.sway_amplitude_multiplier
    assert blend.profile_at(10.35) == target


def test_all_automatic_profiles_keep_final_motion_within_stage_seven_limits() -> None:
    config = BehaviorConfig()
    base = IdleMotionProfile()
    for state in (
        PetState.IDLE_CALM,
        PetState.IDLE_QUIET,
        PetState.IDLE_SWAY,
        PetState.RESTING,
    ):
        profile = profile_for_state(state, config)
        effective = apply_behavior_profile(base, profile)
        assert effective.floating_amplitude_pixels <= 1.5
        assert effective.sway_amplitude_degrees <= 1.0
        for sample in range(100):
            transform = calculate_behavior_transform(sample / 10, base, profile)
            assert 0.998 <= transform.scale_x <= 1.002
            assert 0.996 <= transform.scale_y <= 1.008
            assert abs(transform.offset_y) <= 1.5
            assert abs(transform.rotation_degrees) <= 1.0
