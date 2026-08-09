"""Behavior-to-animation profiles and smooth deterministic profile blending."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from desktop_pet.animation.easing import clamp01, ease_in_out_sine
from desktop_pet.animation.idle_motion import IdleMotionProfile, calculate_idle_transform
from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.behavior.state import PetState
from desktop_pet.config import BehaviorConfig


@dataclass(frozen=True, slots=True)
class BehaviorAnimationProfile:
    """Validated multipliers applied to a base immutable idle-motion profile."""

    breathing_period_multiplier: float = 1.0
    breathing_scale_x_multiplier: float = 1.0
    breathing_scale_y_multiplier: float = 1.0
    floating_amplitude_multiplier: float = 1.0
    sway_amplitude_multiplier: float = 1.0
    fixed_rotation_degrees: float = 0.0
    motion_strength: float = 1.0

    def __post_init__(self) -> None:
        multiplier_names = (
            "breathing_period_multiplier",
            "breathing_scale_x_multiplier",
            "breathing_scale_y_multiplier",
            "floating_amplitude_multiplier",
            "sway_amplitude_multiplier",
        )
        for name in multiplier_names:
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative.")
        if not isfinite(self.fixed_rotation_degrees) or abs(self.fixed_rotation_degrees) > 0.4:
            raise ValueError("Behavior profile fixed rotation must remain within 0.4 degrees.")
        if not isfinite(self.motion_strength) or not 0 <= self.motion_strength <= 1:
            raise ValueError("Behavior profile motion strength must be between zero and one.")


@dataclass(frozen=True, slots=True)
class ProfileBlend:
    """A time-addressable smooth transition between immutable profiles."""

    source: BehaviorAnimationProfile
    target: BehaviorAnimationProfile
    started_at_seconds: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if not isfinite(self.started_at_seconds):
            raise ValueError("Profile blend start time must be finite.")
        if not isfinite(self.duration_seconds) or self.duration_seconds <= 0:
            raise ValueError("Profile blend duration must be finite and greater than zero.")

    def weight_at(self, elapsed_seconds: float) -> float:
        """Return a bounded sine-eased weight without coupling phase to uptime."""
        epsilon = 1e-12
        if elapsed_seconds <= self.started_at_seconds + epsilon:
            return 0.0
        if elapsed_seconds >= self.started_at_seconds + self.duration_seconds - epsilon:
            return 1.0
        progress = clamp01((elapsed_seconds - self.started_at_seconds) / self.duration_seconds)
        return ease_in_out_sine(progress)

    def profile_at(self, elapsed_seconds: float) -> BehaviorAnimationProfile:
        """Return the interpolated parameter view used by state diagnostics."""
        weight = self.weight_at(elapsed_seconds)
        if weight <= 0.0:
            return self.source
        if weight >= 1.0:
            return self.target
        return _interpolate_profile(self.source, self.target, weight)


def _interpolate_profile(
    source: BehaviorAnimationProfile,
    target: BehaviorAnimationProfile,
    weight: float,
) -> BehaviorAnimationProfile:
    def interpolate(left: float, right: float) -> float:
        return left + (right - left) * weight

    return BehaviorAnimationProfile(
        breathing_period_multiplier=interpolate(
            source.breathing_period_multiplier,
            target.breathing_period_multiplier,
        ),
        breathing_scale_x_multiplier=interpolate(
            source.breathing_scale_x_multiplier,
            target.breathing_scale_x_multiplier,
        ),
        breathing_scale_y_multiplier=interpolate(
            source.breathing_scale_y_multiplier,
            target.breathing_scale_y_multiplier,
        ),
        floating_amplitude_multiplier=interpolate(
            source.floating_amplitude_multiplier,
            target.floating_amplitude_multiplier,
        ),
        sway_amplitude_multiplier=interpolate(
            source.sway_amplitude_multiplier,
            target.sway_amplitude_multiplier,
        ),
        fixed_rotation_degrees=interpolate(
            source.fixed_rotation_degrees,
            target.fixed_rotation_degrees,
        ),
        motion_strength=interpolate(source.motion_strength, target.motion_strength),
    )


def profile_for_state(state: PetState, config: BehaviorConfig) -> BehaviorAnimationProfile:
    """Map every behavior state to a safe immutable animation profile."""
    profiles = {
        PetState.STARTING: BehaviorAnimationProfile(
            breathing_scale_x_multiplier=0.0,
            breathing_scale_y_multiplier=0.0,
            floating_amplitude_multiplier=0.0,
            sway_amplitude_multiplier=0.0,
            motion_strength=0.0,
        ),
        PetState.IDLE_CALM: BehaviorAnimationProfile(),
        PetState.IDLE_QUIET: BehaviorAnimationProfile(
            floating_amplitude_multiplier=config.quiet_floating_multiplier,
            sway_amplitude_multiplier=config.quiet_sway_multiplier,
        ),
        PetState.IDLE_SWAY: BehaviorAnimationProfile(
            floating_amplitude_multiplier=config.sway_floating_multiplier,
            sway_amplitude_multiplier=config.sway_rotation_multiplier,
        ),
        PetState.RESTING: BehaviorAnimationProfile(
            breathing_period_multiplier=config.resting_breathing_period_multiplier,
            breathing_scale_x_multiplier=config.resting_breathing_amplitude_multiplier,
            breathing_scale_y_multiplier=config.resting_breathing_amplitude_multiplier,
            floating_amplitude_multiplier=0.0,
            sway_amplitude_multiplier=0.0,
            fixed_rotation_degrees=config.resting_tilt_degrees,
        ),
        PetState.DRAGGING: BehaviorAnimationProfile(
            breathing_scale_x_multiplier=0.30,
            breathing_scale_y_multiplier=0.30,
            floating_amplitude_multiplier=0.0,
            sway_amplitude_multiplier=0.0,
        ),
        PetState.SETTLING: BehaviorAnimationProfile(
            breathing_scale_x_multiplier=0.30,
            breathing_scale_y_multiplier=0.30,
            floating_amplitude_multiplier=0.0,
            sway_amplitude_multiplier=0.0,
        ),
        PetState.CLICK_REACTION: BehaviorAnimationProfile(),
        PetState.PAUSED: BehaviorAnimationProfile(
            breathing_scale_x_multiplier=0.0,
            breathing_scale_y_multiplier=0.0,
            floating_amplitude_multiplier=0.0,
            sway_amplitude_multiplier=0.0,
            motion_strength=0.0,
        ),
        PetState.STOPPED: BehaviorAnimationProfile(
            breathing_scale_x_multiplier=0.0,
            breathing_scale_y_multiplier=0.0,
            floating_amplitude_multiplier=0.0,
            sway_amplitude_multiplier=0.0,
            motion_strength=0.0,
        ),
    }
    return profiles[state]


def apply_behavior_profile(
    base: IdleMotionProfile,
    profile: BehaviorAnimationProfile,
) -> IdleMotionProfile:
    """Create effective idle parameters without mutating the Stage 7 base profile."""
    return base.scaled(
        breathing_period_multiplier=profile.breathing_period_multiplier,
        breathing_scale_x_multiplier=profile.breathing_scale_x_multiplier,
        breathing_scale_y_multiplier=profile.breathing_scale_y_multiplier,
        floating_amplitude_multiplier=profile.floating_amplitude_multiplier,
        sway_amplitude_multiplier=profile.sway_amplitude_multiplier,
    )


def calculate_behavior_transform(
    elapsed_seconds: float,
    base: IdleMotionProfile,
    profile: BehaviorAnimationProfile | ProfileBlend,
) -> AnimationTransform:
    """Calculate a phase-stable transform, including transitions after long uptime."""
    if isinstance(profile, ProfileBlend):
        source = calculate_behavior_transform(elapsed_seconds, base, profile.source)
        target = calculate_behavior_transform(elapsed_seconds, base, profile.target)
        return _interpolate_transform(source, target, profile.weight_at(elapsed_seconds))
    transform = calculate_idle_transform(elapsed_seconds, apply_behavior_profile(base, profile))
    strength = profile.motion_strength
    return AnimationTransform(
        offset_x=transform.offset_x * strength,
        offset_y=transform.offset_y * strength,
        scale_x=1.0 + (transform.scale_x - 1.0) * strength,
        scale_y=1.0 + (transform.scale_y - 1.0) * strength,
        rotation_degrees=transform.rotation_degrees * strength + profile.fixed_rotation_degrees,
    )


def _interpolate_transform(
    source: AnimationTransform,
    target: AnimationTransform,
    weight: float,
) -> AnimationTransform:
    def interpolate(left: float, right: float) -> float:
        return left + (right - left) * weight

    return AnimationTransform(
        offset_x=interpolate(source.offset_x, target.offset_x),
        offset_y=interpolate(source.offset_y, target.offset_y),
        scale_x=interpolate(source.scale_x, target.scale_x),
        scale_y=interpolate(source.scale_y, target.scale_y),
        rotation_degrees=interpolate(source.rotation_degrees, target.rotation_degrees),
    )
