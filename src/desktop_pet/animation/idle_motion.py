"""Deterministic elapsed-time calculations for subtle idle motion."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi, sin

from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.config import AnimationConfig


@dataclass(frozen=True, slots=True)
class IdleMotionProfile:
    """Pure idle-motion parameters, deliberately independent from Qt frame timing."""

    breathing_period_seconds: float = 3.6
    breathing_scale_y: float = 0.006
    breathing_scale_x: float = 0.002
    floating_period_seconds: float = 4.8
    floating_amplitude_pixels: float = 1.5
    sway_period_seconds: float = 6.4
    sway_amplitude_degrees: float = 0.7

    def __post_init__(self) -> None:
        AnimationConfig(
            breathing_period_seconds=self.breathing_period_seconds,
            breathing_scale_x=self.breathing_scale_x,
            breathing_scale_y=self.breathing_scale_y,
            floating_period_seconds=self.floating_period_seconds,
            floating_amplitude_pixels=self.floating_amplitude_pixels,
            sway_period_seconds=self.sway_period_seconds,
            sway_amplitude_degrees=self.sway_amplitude_degrees,
        )

    @classmethod
    def from_config(cls, config: AnimationConfig) -> IdleMotionProfile:
        """Copy idle-only values from the central animation configuration."""
        return cls(
            breathing_period_seconds=config.breathing_period_seconds,
            breathing_scale_x=config.breathing_scale_x,
            breathing_scale_y=config.breathing_scale_y,
            floating_period_seconds=config.floating_period_seconds,
            floating_amplitude_pixels=config.floating_amplitude_pixels,
            sway_period_seconds=config.sway_period_seconds,
            sway_amplitude_degrees=config.sway_amplitude_degrees,
        )

    def scaled(
        self,
        *,
        breathing_period_multiplier: float = 1.0,
        breathing_scale_x_multiplier: float = 1.0,
        breathing_scale_y_multiplier: float = 1.0,
        floating_amplitude_multiplier: float = 1.0,
        sway_amplitude_multiplier: float = 1.0,
    ) -> IdleMotionProfile:
        """Derive validated parameters without mutating the immutable Stage 7 base profile."""
        return IdleMotionProfile(
            breathing_period_seconds=self.breathing_period_seconds * breathing_period_multiplier,
            breathing_scale_y=self.breathing_scale_y * breathing_scale_y_multiplier,
            breathing_scale_x=self.breathing_scale_x * breathing_scale_x_multiplier,
            floating_period_seconds=self.floating_period_seconds,
            floating_amplitude_pixels=self.floating_amplitude_pixels * floating_amplitude_multiplier,
            sway_period_seconds=self.sway_period_seconds,
            sway_amplitude_degrees=min(1.0, self.sway_amplitude_degrees * sway_amplitude_multiplier),
        )


def _phase(elapsed_seconds: float, period_seconds: float, phase_offset: float) -> float:
    """Keep periodic calculation stable for very large elapsed-time inputs."""
    if not isfinite(elapsed_seconds):
        raise ValueError("Elapsed animation time must be finite.")
    cycle_fraction = (elapsed_seconds % period_seconds) / period_seconds
    return 2.0 * pi * cycle_fraction + phase_offset


def calculate_idle_transform(
    elapsed_seconds: float,
    profile: IdleMotionProfile,
) -> AnimationTransform:
    """Calculate one deterministic local transform directly from elapsed time."""
    breathing = sin(_phase(elapsed_seconds, profile.breathing_period_seconds, 0.31))
    floating = sin(_phase(elapsed_seconds, profile.floating_period_seconds, 1.17))
    sway = sin(_phase(elapsed_seconds, profile.sway_period_seconds, 2.43))
    horizontal_breathing = sin(_phase(elapsed_seconds, profile.breathing_period_seconds, 1.01))
    return AnimationTransform(
        offset_y=profile.floating_amplitude_pixels * floating,
        scale_x=1.0 + profile.breathing_scale_x * horizontal_breathing,
        scale_y=1.002 + profile.breathing_scale_y * breathing,
        rotation_degrees=profile.sway_amplitude_degrees * sway,
    )
