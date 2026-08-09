"""Regression tests for phase jumps during long-running behavior transitions."""

from __future__ import annotations

from desktop_pet.animation.idle_motion import IdleMotionProfile
from desktop_pet.behavior.profiles import ProfileBlend, calculate_behavior_transform, profile_for_state
from desktop_pet.behavior.state import PetState
from desktop_pet.config import BehaviorConfig

AUTOMATIC_STATES = (
    PetState.IDLE_CALM,
    PetState.IDLE_QUIET,
    PetState.IDLE_SWAY,
    PetState.RESTING,
)


def test_profile_blend_transform_has_exact_endpoints() -> None:
    config = BehaviorConfig()
    base = IdleMotionProfile()
    source = profile_for_state(PetState.IDLE_CALM, config)
    target = profile_for_state(PetState.RESTING, config)
    start = 3_600.0
    blend = ProfileBlend(source, target, start, config.profile_transition_duration_seconds)

    assert calculate_behavior_transform(start, base, blend) == calculate_behavior_transform(
        start,
        base,
        source,
    )
    end = start + config.profile_transition_duration_seconds
    assert calculate_behavior_transform(end, base, blend) == calculate_behavior_transform(
        end,
        base,
        target,
    )


def test_all_profile_transitions_remain_smooth_after_long_uptime() -> None:
    config = BehaviorConfig()
    base = IdleMotionProfile()
    frame_interval = 1.0 / 30.0
    sample_count = 12
    limits = {
        "offset_x": 0.001,
        "offset_y": 0.25,
        "scale_x": 0.0005,
        "scale_y": 0.0015,
        "rotation_degrees": 0.18,
    }

    for start in (60.0, 600.0, 3_600.0):
        for source_state in AUTOMATIC_STATES:
            for target_state in AUTOMATIC_STATES:
                if source_state is target_state:
                    continue
                blend = ProfileBlend(
                    profile_for_state(source_state, config),
                    profile_for_state(target_state, config),
                    start,
                    config.profile_transition_duration_seconds,
                )
                transforms = [
                    calculate_behavior_transform(start + index * frame_interval, base, blend)
                    for index in range(sample_count)
                ]
                for previous, current in zip(transforms, transforms[1:], strict=False):
                    for name, maximum_delta in limits.items():
                        assert abs(getattr(current, name) - getattr(previous, name)) <= maximum_delta


def test_interpolating_period_before_phase_calculation_would_reproduce_the_jitter() -> None:
    config = BehaviorConfig()
    base = IdleMotionProfile()
    start = 600.0
    blend = ProfileBlend(
        profile_for_state(PetState.IDLE_CALM, config),
        profile_for_state(PetState.RESTING, config),
        start,
        config.profile_transition_duration_seconds,
    )
    old_style = [
        calculate_behavior_transform(
            start + index / 30.0,
            base,
            blend.profile_at(start + index / 30.0),
        )
        for index in range(12)
    ]
    stable = [
        calculate_behavior_transform(start + index / 30.0, base, blend)
        for index in range(12)
    ]

    old_maximum_jump = max(
        abs(current.scale_y - previous.scale_y)
        for previous, current in zip(old_style, old_style[1:], strict=False)
    )
    stable_maximum_jump = max(
        abs(current.scale_y - previous.scale_y)
        for previous, current in zip(stable, stable[1:], strict=False)
    )
    assert old_maximum_jump > 0.01
    assert stable_maximum_jump < 0.0015
