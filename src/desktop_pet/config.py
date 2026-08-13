"""Validated configuration for the transparent pet, animation, and behavior layers."""

from dataclasses import dataclass, field
from math import isfinite

DEFAULT_WINDOW_WIDTH = 280
DEFAULT_WINDOW_HEIGHT = 420
SMALL_WINDOW_WIDTH = 240
SMALL_WINDOW_HEIGHT = 360
LARGE_WINDOW_WIDTH = 320
LARGE_WINDOW_HEIGHT = 480
STARTUP_MARGIN = 24
MIN_VISIBLE_WIDTH = 40
MIN_VISIBLE_HEIGHT = 40
WINDOW_TITLE = "小融"
APPLICATION_TITLE = WINDOW_TITLE
ALPHA_HIT_TEST_THRESHOLD = 16
CLICK_MAX_HOLD_DURATION_MS = 500
CLICK_REACTION_DURATION_MS = 260


@dataclass(frozen=True, slots=True)
class DialogueBubbleConfig:
    """Internal logical-pixel limits for the click dialogue bubble."""

    display_duration_ms: int = 4500
    minimum_width: int = 180
    maximum_width: int = 400
    screen_margin: int = 12
    pet_gap: int = 8
    corner_radius: int = 18
    tail_size: int = 14
    horizontal_padding: int = 24
    vertical_padding: int = 18
    line_gap: int = 4
    font_point_size: float = 13.0
    maximum_height: int = 360
    maximum_display_characters: int = 600

    def __post_init__(self) -> None:
        integer_fields = (
            "display_duration_ms",
            "minimum_width",
            "maximum_width",
            "screen_margin",
            "pet_gap",
            "corner_radius",
            "tail_size",
            "horizontal_padding",
            "vertical_padding",
            "line_gap",
            "maximum_height",
            "maximum_display_characters",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if not 2000 <= self.display_duration_ms <= 10_000:
            raise ValueError("Dialogue display duration must be between 2000 and 10000 ms.")
        if self.minimum_width > self.maximum_width:
            raise ValueError("Dialogue minimum width cannot exceed its maximum width.")
        if (
            isinstance(self.font_point_size, bool)
            or not isinstance(self.font_point_size, (int, float))
            or not isfinite(self.font_point_size)
            or not 11.0 <= self.font_point_size <= 16.0
        ):
            raise ValueError("Dialogue font point size must be between 11 and 16 points.")
        minimum_content_width = 2 * (self.tail_size + self.horizontal_padding) + 1
        if self.maximum_width < minimum_content_width:
            raise ValueError("Dialogue maximum width is too small for its padding and tail.")


@dataclass(frozen=True, slots=True)
class BlinkConfig:
    """Internal blink scheduling parameters; intentionally not user settings."""

    enabled: bool = True
    minimum_interval_seconds: float = 3.0
    maximum_interval_seconds: float = 8.0
    double_blink_probability: float = 0.12
    double_blink_gap_minimum_seconds: float = 0.08
    double_blink_gap_maximum_seconds: float = 0.16
    startup_minimum_delay_seconds: float = 2.0
    resume_minimum_delay_seconds: float = 1.5
    seed: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("Blink enabled state must be boolean.")
        if not 0 < self.minimum_interval_seconds < self.maximum_interval_seconds:
            raise ValueError("Blink minimum interval must be positive and below the maximum.")
        if not 0.0 <= self.double_blink_probability <= 1.0:
            raise ValueError("Double-blink probability must be between zero and one.")
        if not 0 < self.double_blink_gap_minimum_seconds <= self.double_blink_gap_maximum_seconds:
            raise ValueError("Double-blink gap bounds must be positive and ordered.")
        if self.startup_minimum_delay_seconds < 2.0:
            raise ValueError("Blink startup delay must be at least two seconds.")
        if self.resume_minimum_delay_seconds < 1.5:
            raise ValueError("Blink resume delay must be at least 1.5 seconds.")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise ValueError("Blink seed must be an integer or None.")


@dataclass(frozen=True, slots=True)
class DrowsySleepConfig:
    """Internal timing and gentle nasal-bubble motion for autonomous sleep."""

    enabled: bool = True
    startup_minimum_seconds: float = 30.0
    startup_maximum_seconds: float = 55.0
    minimum_interval_seconds: float = 75.0
    maximum_interval_seconds: float = 140.0
    interrupted_retry_seconds: float = 30.0
    bubble_anchor_x: float = 0.485
    bubble_anchor_y: float = 0.418
    bubble_rotation_degrees: float = 8.0
    bubble_rotation_period_seconds: float = 5.8
    bubble_scale_amplitude: float = 0.065
    bubble_scale_period_seconds: float = 3.4
    seed: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("Drowsy sleep enabled state must be boolean.")
        ranges = (
            ("startup", self.startup_minimum_seconds, self.startup_maximum_seconds),
            ("interval", self.minimum_interval_seconds, self.maximum_interval_seconds),
        )
        for name, minimum, maximum in ranges:
            if not isfinite(minimum) or not isfinite(maximum) or minimum <= 0 or maximum < minimum:
                raise ValueError(f"Drowsy sleep {name} bounds must be positive and ordered.")
        if not isfinite(self.interrupted_retry_seconds) or self.interrupted_retry_seconds <= 0:
            raise ValueError("Drowsy sleep interrupted retry must be positive.")
        for name in ("bubble_anchor_x", "bubble_anchor_y"):
            value = getattr(self, name)
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one.")
        if not 0.0 < self.bubble_rotation_degrees <= 10.0:
            raise ValueError("Bubble rotation must be greater than zero and at most ten degrees.")
        if not 4.0 <= self.bubble_rotation_period_seconds <= 8.0:
            raise ValueError("Bubble rotation period must be between four and eight seconds.")
        if not 0.0 < self.bubble_scale_amplitude <= 0.10:
            raise ValueError("Bubble scale amplitude must be greater than zero and at most 0.10.")
        if not 2.5 <= self.bubble_scale_period_seconds <= 5.0:
            raise ValueError("Bubble scale period must be between 2.5 and 5 seconds.")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise ValueError("Drowsy sleep seed must be an integer or None.")


@dataclass(frozen=True, slots=True)
class AnimationConfig:
    """Validated, intentionally subtle parameters for internal paint transforms."""

    target_fps: int = 30
    breathing_period_seconds: float = 3.6
    breathing_scale_x: float = 0.002
    breathing_scale_y: float = 0.006
    floating_period_seconds: float = 4.8
    floating_amplitude_pixels: float = 1.5
    sway_period_seconds: float = 6.4
    sway_amplitude_degrees: float = 0.7
    drag_tilt_max_degrees: float = 4.0
    drag_tilt_smoothing: float = 0.28
    drag_return_duration_ms: int = 220
    drag_velocity_degrees_per_pixel_per_second: float = 0.015

    def __post_init__(self) -> None:
        if isinstance(self.target_fps, bool) or not isinstance(self.target_fps, int):
            raise ValueError("Animation target FPS must be an integer.")
        if not 15 <= self.target_fps <= 60:
            raise ValueError("Animation target FPS must be between 15 and 60.")
        for name in (
            "breathing_period_seconds",
            "floating_period_seconds",
            "sway_period_seconds",
            "drag_velocity_degrees_per_pixel_per_second",
        ):
            if not isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and greater than zero.")
        if not 0 <= self.breathing_scale_x <= 0.002:
            raise ValueError("Breathing horizontal scale amplitude must be between 0 and 0.002.")
        if not 0 <= self.breathing_scale_y <= 0.006:
            raise ValueError("Breathing vertical scale amplitude must be between 0 and 0.006.")
        if not 0 <= self.floating_amplitude_pixels <= 3.0:
            raise ValueError("Floating amplitude must be between 0 and 3 logical pixels.")
        if not 0 <= self.sway_amplitude_degrees <= 1.2:
            raise ValueError("Sway amplitude must be between 0 and 1.2 degrees.")
        if not 0 <= self.drag_tilt_max_degrees <= 5.0:
            raise ValueError("Drag tilt must be between 0 and 5 degrees.")
        if not 0.20 <= self.drag_tilt_smoothing <= 0.35:
            raise ValueError("Drag tilt smoothing must be between 0.20 and 0.35.")
        if not 180 <= self.drag_return_duration_ms <= 280:
            raise ValueError("Drag return duration must be between 180 and 280 milliseconds.")


@dataclass(frozen=True, slots=True)
class StateDurationRange:
    """Inclusive duration range used only when scheduling automatic behavior states."""

    minimum_seconds: float
    maximum_seconds: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_seconds, bool)
            or not isfinite(self.minimum_seconds)
            or self.minimum_seconds <= 0
        ):
            raise ValueError("State minimum duration must be finite and greater than zero.")
        if (
            isinstance(self.maximum_seconds, bool)
            or not isfinite(self.maximum_seconds)
            or self.maximum_seconds < self.minimum_seconds
        ):
            raise ValueError("State maximum duration must be finite and no smaller than the minimum.")


@dataclass(frozen=True, slots=True)
class BehaviorConfig:
    """Production defaults for reproducible low-risk behavior scheduling."""

    behavior_seed: int | None = None
    starting_duration_seconds: float = 0.45
    calm_duration: StateDurationRange = field(default_factory=lambda: StateDurationRange(8.0, 14.0))
    quiet_duration: StateDurationRange = field(default_factory=lambda: StateDurationRange(4.0, 8.0))
    sway_duration: StateDurationRange = field(default_factory=lambda: StateDurationRange(5.0, 9.0))
    resting_duration: StateDurationRange = field(default_factory=lambda: StateDurationRange(8.0, 16.0))
    quiet_floating_multiplier: float = 0.30
    quiet_sway_multiplier: float = 0.15
    sway_rotation_multiplier: float = 1.30
    sway_floating_multiplier: float = 0.80
    resting_breathing_period_multiplier: float = 1.40
    resting_breathing_amplitude_multiplier: float = 0.55
    resting_tilt_degrees: float = 0.20
    profile_transition_duration_seconds: float = 0.35
    state_history_limit: int = 100

    def __post_init__(self) -> None:
        if self.behavior_seed is not None and (
            isinstance(self.behavior_seed, bool) or not isinstance(self.behavior_seed, int)
        ):
            raise ValueError("Behavior seed must be an integer or None.")
        if not isfinite(self.starting_duration_seconds) or self.starting_duration_seconds <= 0:
            raise ValueError("Starting duration must be finite and greater than zero.")
        multiplier_names = (
            "quiet_floating_multiplier",
            "quiet_sway_multiplier",
            "sway_rotation_multiplier",
            "sway_floating_multiplier",
            "resting_breathing_period_multiplier",
            "resting_breathing_amplitude_multiplier",
        )
        for name in multiplier_names:
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative.")
        if not 0.20 <= self.quiet_floating_multiplier <= 0.40:
            raise ValueError("Quiet floating multiplier must be between 0.20 and 0.40.")
        if not 0.10 <= self.quiet_sway_multiplier <= 0.20:
            raise ValueError("Quiet sway multiplier must be between 0.10 and 0.20.")
        if 0.7 * self.sway_rotation_multiplier > 1.0:
            raise ValueError("The default behavior sway angle cannot exceed 1.0 degree.")
        if not isfinite(self.resting_tilt_degrees) or abs(self.resting_tilt_degrees) > 0.4:
            raise ValueError("Resting fixed tilt must remain within 0.4 degrees.")
        if (
            not isfinite(self.profile_transition_duration_seconds)
            or self.profile_transition_duration_seconds <= 0
            or self.profile_transition_duration_seconds > 0.45
        ):
            raise ValueError("Profile transition duration must be greater than zero and at most 0.45 seconds.")
        if (
            isinstance(self.state_history_limit, bool)
            or not isinstance(self.state_history_limit, int)
            or self.state_history_limit <= 0
        ):
            raise ValueError("State history limit must be a positive integer.")


@dataclass(frozen=True, slots=True)
class PetWindowConfig:
    """Validated logical-pixel dimensions and motion parameters for the pet window."""

    width: int = DEFAULT_WINDOW_WIDTH
    height: int = DEFAULT_WINDOW_HEIGHT
    startup_margin: int = STARTUP_MARGIN
    always_on_top: bool = True
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    blink: BlinkConfig = field(default_factory=BlinkConfig)
    drowsy_sleep: DrowsySleepConfig = field(default_factory=DrowsySleepConfig)

    def __post_init__(self) -> None:
        if isinstance(self.width, bool) or not isinstance(self.width, int) or self.width <= 0:
            raise ValueError("Pet window width must be a positive integer.")
        if isinstance(self.height, bool) or not isinstance(self.height, int) or self.height <= 0:
            raise ValueError("Pet window height must be a positive integer.")
        if self.width * 3 != self.height * 2:
            raise ValueError("Pet window dimensions must keep the approved 2:3 aspect ratio.")
        if isinstance(self.startup_margin, bool) or not isinstance(self.startup_margin, int):
            raise ValueError("Startup margin must be an integer.")
        if self.startup_margin < 0:
            raise ValueError("Startup margin cannot be negative.")
        if self.animation.sway_amplitude_degrees * self.behavior.sway_rotation_multiplier > 1.0:
            raise ValueError("Behavior-adjusted sway cannot exceed 1.0 degree.")
