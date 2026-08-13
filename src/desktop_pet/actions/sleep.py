"""Timer-free autonomous drowsy-sleep scheduling and nasal-bubble motion."""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass
from math import isfinite, pi, sin

from desktop_pet.actions.model import ActionPriority
from desktop_pet.actions.request import ActionRequest, ActionRequestSource
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.config import DrowsySleepConfig

DROWSY_SLEEP_ACTION_ID = "drowsy_sleep_cycle"
_SLEEP_BUBBLE_EVENT_RENDER = {
    # Per-frame normalized nose offsets keep the independent overlay attached
    # to the actual face pose instead of leaving it at one world coordinate.
    "sleep_bubble": (0.0, 0.0, 1.0, 0.88),
    "sleep_bubble_nod_local_micro": (-0.0003, 0.002, 1.0, 0.88),
    "sleep_bubble_nod_local_very_light": (-0.0007, 0.004, 1.0, 0.88),
    "sleep_bubble_nod_local_light": (-0.0010, 0.007, 1.0, 0.88),
    "sleep_bubble_nod_local_light_plus": (-0.0013, 0.010, 1.0, 0.88),
    "sleep_bubble_nod_local_light_mid": (-0.0016, 0.014, 1.0, 0.88),
    "sleep_bubble_nod_local_mid": (-0.0020, 0.019, 1.0, 0.88),
    "sleep_bubble_nod_local_mid_deep": (-0.0024, 0.024, 1.0, 0.88),
    "sleep_bubble_nod_local_deep": (-0.0028, 0.030, 1.0, 0.88),
    "sleep_bubble_nod_local_deep_peak": (-0.0032, 0.035, 1.0, 0.88),
    "sleep_bubble_nod_local_peak": (-0.0036, 0.040, 1.0, 0.88),
    "sleep_bubble_shrink_start": (-0.001, 0.005, 0.82, 0.72),
    "sleep_bubble_shrink_large": (-0.001, 0.007, 0.64, 0.56),
    "sleep_bubble_shrink_small": (0.0, 0.004, 0.30, 0.24),
}
SLEEP_BUBBLE_EVENTS = frozenset(_SLEEP_BUBBLE_EVENT_RENDER)


@dataclass(frozen=True, slots=True)
class SleepBubbleState:
    """Normalized render state; drawing remains owned by the pet window."""

    visible: bool
    anchor_x: float = 0.0
    anchor_y: float = 0.0
    rotation_degrees: float = 0.0
    scale: float = 1.0
    opacity: float = 0.0

    @classmethod
    def hidden(cls) -> SleepBubbleState:
        return cls(visible=False)


class DrowsySleepController:
    """Produce one autonomous request at a time without owning a timer."""

    def __init__(self, config: DrowsySleepConfig) -> None:
        self._config = config
        seed = config.seed if config.seed is not None else secrets.randbits(64)
        self._random = random.Random(seed)
        self._started = False
        self._enabled = config.enabled
        self._request_pending = False
        self._active = False
        self._next_due_seconds = float("inf")

    @property
    def active(self) -> bool:
        return self._active

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def next_due_seconds(self) -> float:
        return self._next_due_seconds

    def start(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if self._started:
            return
        self._started = True
        if self._enabled:
            self._schedule(
                elapsed_seconds,
                self._config.startup_minimum_seconds,
                self._config.startup_maximum_seconds,
            )

    def set_enabled(self, enabled: bool, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if not isinstance(enabled, bool):
            raise ValueError("Drowsy sleep enabled state must be boolean.")
        requested_enabled = enabled and self._config.enabled
        if requested_enabled is self._enabled:
            return
        self._enabled = requested_enabled
        self._request_pending = False
        self._active = False
        if enabled:
            self._schedule(
                elapsed_seconds,
                self._config.startup_minimum_seconds,
                self._config.startup_maximum_seconds,
            )
        else:
            self._next_due_seconds = float("inf")

    def update(
        self,
        elapsed_seconds: float,
        state: PetState,
        current_action_id: str | None,
    ) -> ActionRequest | None:
        self._validate_time(elapsed_seconds)
        if not self._started:
            self.start(elapsed_seconds)
        if (
            not self._enabled
            or self._request_pending
            or self._active
            or state not in AUTOMATIC_STATES
            or current_action_id is not None
            or elapsed_seconds < self._next_due_seconds
        ):
            return None
        self._request_pending = True
        return ActionRequest(
            action_id=DROWSY_SLEEP_ACTION_ID,
            priority=ActionPriority.AUTONOMOUS_SLEEP,
            source=ActionRequestSource.AUTONOMOUS,
            requested_at_seconds=elapsed_seconds,
            reason="scheduled drowsy sleep",
        )

    def resolve_request(self, accepted: bool, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if not self._request_pending:
            return
        self._request_pending = False
        if accepted:
            self._active = True
            self._next_due_seconds = float("inf")
        else:
            self._next_due_seconds = elapsed_seconds + 1.0

    def on_clip_started(self, action_id: str) -> None:
        if action_id == DROWSY_SLEEP_ACTION_ID:
            self._request_pending = False
            self._active = True

    def on_clip_finished(self, action_id: str, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if action_id != DROWSY_SLEEP_ACTION_ID:
            return
        self._active = False
        self._schedule(
            elapsed_seconds,
            self._config.minimum_interval_seconds,
            self._config.maximum_interval_seconds,
        )

    def on_clip_interrupted(self, action_id: str, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if action_id != DROWSY_SLEEP_ACTION_ID:
            return
        self._active = False
        self._request_pending = False
        self._next_due_seconds = (
            elapsed_seconds + self._config.interrupted_retry_seconds
            if self._enabled
            else float("inf")
        )

    def bubble_state(self, elapsed_seconds: float, frame_event: str | None) -> SleepBubbleState:
        self._validate_time(elapsed_seconds)
        if not self._active or frame_event not in SLEEP_BUBBLE_EVENTS:
            return SleepBubbleState.hidden()
        rotation_phase = 2.0 * pi * elapsed_seconds / self._config.bubble_rotation_period_seconds
        scale_phase = 2.0 * pi * elapsed_seconds / self._config.bubble_scale_period_seconds
        x_offset, y_offset, scale_multiplier, opacity = _SLEEP_BUBBLE_EVENT_RENDER[
            frame_event
        ]
        return SleepBubbleState(
            visible=True,
            anchor_x=self._config.bubble_anchor_x + x_offset,
            anchor_y=self._config.bubble_anchor_y + y_offset,
            rotation_degrees=self._config.bubble_rotation_degrees * sin(rotation_phase),
            scale=scale_multiplier
            * (1.0 + self._config.bubble_scale_amplitude * sin(scale_phase)),
            opacity=opacity,
        )

    def _schedule(self, elapsed_seconds: float, minimum: float, maximum: float) -> None:
        if self._enabled:
            self._next_due_seconds = elapsed_seconds + self._random.uniform(minimum, maximum)
        else:
            self._next_due_seconds = float("inf")

    @staticmethod
    def _validate_time(elapsed_seconds: float) -> None:
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Drowsy sleep elapsed time must be finite and nonnegative.")
