"""Reproducible local-random scheduling for single and double blinks."""

from __future__ import annotations

import random
import secrets
from math import isfinite

from desktop_pet.config import BlinkConfig


class BlinkScheduler:
    """Consume randomness only when a new blink event is scheduled."""

    def __init__(self, config: BlinkConfig) -> None:
        if not isinstance(config, BlinkConfig):
            raise ValueError("BlinkScheduler requires BlinkConfig.")
        self.config = config
        self.actual_seed = secrets.randbits(64) if config.seed is None else config.seed
        self._random = random.Random(self.actual_seed)
        self._next_due_seconds: float | None = None
        self._planned_double_gap_seconds: float | None = None
        self._follow_up_due = False
        self._active = False
        self._paused_remaining_seconds: float | None = None
        self._random_draw_count = 0

    @property
    def next_due_seconds(self) -> float | None:
        return self._next_due_seconds

    @property
    def random_draw_count(self) -> int:
        return self._random_draw_count

    @property
    def is_paused(self) -> bool:
        return self._paused_remaining_seconds is not None

    @property
    def follow_up_due(self) -> bool:
        return self._follow_up_due

    def start(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if self._next_due_seconds is None and not self._active:
            self._schedule_regular(elapsed_seconds, self.config.startup_minimum_delay_seconds)

    def is_due(self, elapsed_seconds: float) -> bool:
        self._validate_time(elapsed_seconds)
        return (
            self.config.enabled
            and not self.is_paused
            and not self._active
            and self._next_due_seconds is not None
            and elapsed_seconds >= self._next_due_seconds
        )

    def mark_started(self) -> None:
        if self._next_due_seconds is None or self._active:
            raise RuntimeError("BlinkScheduler has no due blink to start.")
        self._active = True
        self._next_due_seconds = None

    def mark_finished(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if not self._active:
            raise RuntimeError("BlinkScheduler has no active blink to finish.")
        self._active = False
        if self._follow_up_due:
            self._follow_up_due = False
            self._schedule_regular(elapsed_seconds, 0.0)
            return
        if self._planned_double_gap_seconds is not None:
            self._next_due_seconds = elapsed_seconds + self._planned_double_gap_seconds
            self._planned_double_gap_seconds = None
            self._follow_up_due = True
            return
        self._schedule_regular(elapsed_seconds, 0.0)

    def mark_interrupted(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        self._active = False
        self._follow_up_due = False
        self._planned_double_gap_seconds = None
        self._schedule_regular(elapsed_seconds, 0.0)

    def pause(self, elapsed_seconds: float, *, minimum_resume_delay_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if minimum_resume_delay_seconds < 0:
            raise ValueError("Blink resume delay cannot be negative.")
        remaining = (
            minimum_resume_delay_seconds
            if self._next_due_seconds is None
            else max(0.0, self._next_due_seconds - elapsed_seconds)
        )
        self._paused_remaining_seconds = max(remaining, minimum_resume_delay_seconds)
        self._next_due_seconds = None
        self._active = False
        self._follow_up_due = False
        self._planned_double_gap_seconds = None

    def resume(self, elapsed_seconds: float, *, minimum_delay_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if self._paused_remaining_seconds is None:
            return
        self._next_due_seconds = elapsed_seconds + max(self._paused_remaining_seconds, minimum_delay_seconds)
        self._paused_remaining_seconds = None

    def stop(self) -> None:
        self._next_due_seconds = None
        self._planned_double_gap_seconds = None
        self._follow_up_due = False
        self._active = False
        self._paused_remaining_seconds = None

    def _schedule_regular(self, elapsed_seconds: float, minimum_delay_seconds: float) -> None:
        interval = self._uniform(
            self.config.minimum_interval_seconds,
            self.config.maximum_interval_seconds,
        )
        self._next_due_seconds = elapsed_seconds + max(interval, minimum_delay_seconds)
        if self._random_value() < self.config.double_blink_probability:
            self._planned_double_gap_seconds = self._uniform(
                self.config.double_blink_gap_minimum_seconds,
                self.config.double_blink_gap_maximum_seconds,
            )
        else:
            self._planned_double_gap_seconds = None
        self._follow_up_due = False

    def _uniform(self, minimum: float, maximum: float) -> float:
        self._random_draw_count += 1
        return self._random.uniform(minimum, maximum)

    def _random_value(self) -> float:
        self._random_draw_count += 1
        return self._random.random()

    @staticmethod
    def _validate_time(elapsed_seconds: float) -> None:
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Blink elapsed time must be finite and nonnegative.")
