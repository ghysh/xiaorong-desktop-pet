"""Qt signal wrapper around a timer-free, injected-time behavior state machine."""

from __future__ import annotations

from collections import deque
from math import isfinite

from PySide6.QtCore import QObject, Signal

from desktop_pet.behavior.profiles import BehaviorAnimationProfile, ProfileBlend, profile_for_state
from desktop_pet.behavior.scheduler import BehaviorScheduler
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.behavior.transition import StateTransition, TransitionReason, validate_transition
from desktop_pet.config import BehaviorConfig


class BehaviorController(QObject):
    """Own state and scheduling only; callers inject elapsed monotonic seconds."""

    state_changed = Signal(object)
    profile_changed = Signal(object)

    def __init__(self, config: BehaviorConfig, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._scheduler = BehaviorScheduler(config)
        self._current_state = PetState.STARTING
        self._state_entered_seconds = 0.0
        self._scheduled_duration_seconds: float | None = config.starting_duration_seconds
        self._current_profile = profile_for_state(PetState.STARTING, config)
        self._profile_blend = ProfileBlend(
            self._current_profile,
            profile_for_state(PetState.IDLE_CALM, config),
            0.0,
            config.starting_duration_seconds,
        )
        self._started = False
        self._last_update_seconds = 0.0
        self._resume_state: PetState | None = None
        self._resume_elapsed_seconds = 0.0
        self._resume_duration_seconds: float | None = None
        self._click_resume_state: PetState | None = None
        self._click_resume_elapsed_seconds = 0.0
        self._click_resume_duration_seconds: float | None = None
        self._paused_state: PetState | None = None
        self._paused_elapsed_seconds = 0.0
        self._paused_duration_seconds: float | None = None
        self._history: deque[StateTransition] = deque(maxlen=config.state_history_limit)
        self._behavior_enabled = True
        self._total_transition_count = 0

    @property
    def current_state(self) -> PetState:
        return self._current_state

    @property
    def scheduled_duration_seconds(self) -> float | None:
        return self._scheduled_duration_seconds

    @property
    def actual_seed(self) -> int:
        return self._scheduler.actual_seed

    @property
    def history(self) -> tuple[StateTransition, ...]:
        return tuple(self._history)

    @property
    def scheduler(self) -> BehaviorScheduler:
        return self._scheduler

    @property
    def behavior_enabled(self) -> bool:
        return self._behavior_enabled

    @property
    def total_transition_count(self) -> int:
        return self._total_transition_count

    def start(self, elapsed_seconds: float = 0.0) -> None:
        """Start once in STARTING; a paused controller instead resumes its saved base state."""
        self._validate_time(elapsed_seconds)
        if self._current_state is PetState.STOPPED:
            return
        if self._current_state is PetState.PAUSED:
            self.resume(elapsed_seconds)
            return
        if self._started:
            return
        self._started = True
        self._state_entered_seconds = elapsed_seconds
        self._last_update_seconds = elapsed_seconds
        self._profile_blend = ProfileBlend(
            profile_for_state(PetState.STARTING, self._config),
            profile_for_state(PetState.IDLE_CALM, self._config),
            elapsed_seconds,
            self._config.starting_duration_seconds,
        )
        self.profile_changed.emit(self._current_profile)

    def update(self, elapsed_seconds: float) -> None:
        """Advance at most one transition using injected time; no random work occurs per frame otherwise."""
        self._validate_monotonic_time(elapsed_seconds)
        if not self._started:
            self.start(elapsed_seconds)
        self._last_update_seconds = elapsed_seconds
        if self._current_state in {
            PetState.DRAGGING,
            PetState.SETTLING,
            PetState.CLICK_REACTION,
            PetState.PAUSED,
            PetState.STOPPED,
        }:
            return
        if not self._behavior_enabled:
            return
        if self._scheduled_duration_seconds is None:
            return
        state_elapsed = elapsed_seconds - self._state_entered_seconds
        if state_elapsed < self._scheduled_duration_seconds:
            return
        if self._current_state is PetState.STARTING:
            duration = self._scheduler.choose_duration(PetState.IDLE_CALM)
            self._transition(
                PetState.IDLE_CALM,
                TransitionReason.STARTUP_COMPLETE,
                elapsed_seconds,
                scheduled_duration_seconds=duration,
            )
            return
        if self._current_state in AUTOMATIC_STATES:
            next_state = self._scheduler.choose_next_state(self._current_state)
            duration = self._scheduler.choose_duration(next_state)
            self._transition(
                next_state,
                TransitionReason.SCHEDULED_TRANSITION,
                elapsed_seconds,
                scheduled_duration_seconds=duration,
            )

    def profile_at(self, elapsed_seconds: float) -> BehaviorAnimationProfile:
        """Return the current smoothly interpolated profile for the animation controller."""
        self._validate_time(elapsed_seconds)
        if self._profile_blend is None:
            return self._current_profile
        return self._profile_blend.profile_at(elapsed_seconds)

    def motion_profile_at(
        self,
        elapsed_seconds: float,
    ) -> BehaviorAnimationProfile | ProfileBlend:
        """Return a phase-stable endpoint blend for final transform calculation."""
        self._validate_time(elapsed_seconds)
        blend = self._profile_blend
        if blend is None or elapsed_seconds >= blend.started_at_seconds + blend.duration_seconds:
            return self._current_profile
        return blend

    def begin_drag(self, elapsed_seconds: float) -> None:
        """Immediately override any active state while freezing its elapsed scheduling time."""
        self._validate_monotonic_time(elapsed_seconds)
        if self._current_state in {PetState.PAUSED, PetState.STOPPED, PetState.DRAGGING}:
            return
        if self._current_state is PetState.CLICK_REACTION:
            self._resume_state = self._click_resume_state
            self._resume_elapsed_seconds = self._click_resume_elapsed_seconds
            self._resume_duration_seconds = self._click_resume_duration_seconds
            self._clear_click_resume()
        elif self._current_state is not PetState.SETTLING:
            self._resume_state = self._current_state
            self._resume_elapsed_seconds = max(0.0, elapsed_seconds - self._state_entered_seconds)
            self._resume_duration_seconds = self._scheduled_duration_seconds
        self._transition(PetState.DRAGGING, TransitionReason.DRAG_STARTED, elapsed_seconds, immediate_profile=True)

    def begin_click_reaction(self, elapsed_seconds: float) -> bool:
        """Freeze a starting/automatic state and enter the short user-click override."""
        self._validate_monotonic_time(elapsed_seconds)
        if self._current_state is not PetState.STARTING and self._current_state not in AUTOMATIC_STATES:
            return False
        self._click_resume_state = self._current_state
        self._click_resume_elapsed_seconds = max(0.0, elapsed_seconds - self._state_entered_seconds)
        self._click_resume_duration_seconds = self._scheduled_duration_seconds
        self._transition(
            PetState.CLICK_REACTION,
            TransitionReason.CLICK_STARTED,
            elapsed_seconds,
            preserve_profile=True,
        )
        return True

    def finish_click_reaction(self, elapsed_seconds: float) -> None:
        """Restore the pre-click state without consuming its remaining scheduled time."""
        self._validate_monotonic_time(elapsed_seconds)
        if self._current_state is not PetState.CLICK_REACTION:
            return
        target = self._click_resume_state
        if not self._behavior_enabled:
            target = PetState.IDLE_CALM
            self._click_resume_elapsed_seconds = 0.0
            self._click_resume_duration_seconds = None
        if target is not PetState.STARTING and target not in AUTOMATIC_STATES:
            target = PetState.IDLE_CALM
            self._click_resume_elapsed_seconds = 0.0
            self._click_resume_duration_seconds = self._scheduler.choose_duration(target)
        duration = self._click_resume_duration_seconds
        if duration is None and self._behavior_enabled:
            duration = (
                self._config.starting_duration_seconds
                if target is PetState.STARTING
                else self._scheduler.choose_duration(target)
            )
        self._transition(
            target,
            TransitionReason.CLICK_FINISHED,
            elapsed_seconds,
            scheduled_duration_seconds=duration,
        )
        self._state_entered_seconds = elapsed_seconds - self._click_resume_elapsed_seconds
        self._clear_click_resume()

    def set_behavior_enabled(self, enabled: bool, elapsed_seconds: float) -> None:
        """Toggle automatic scheduling while preserving drag and click overrides."""
        if not isinstance(enabled, bool):
            raise ValueError("Behavior enabled state must be boolean.")
        self._validate_monotonic_time(elapsed_seconds)
        if enabled is self._behavior_enabled:
            return
        self._behavior_enabled = enabled
        if not enabled:
            self._scheduled_duration_seconds = None
            if self._current_state in AUTOMATIC_STATES or self._current_state is PetState.STARTING:
                if self._current_state is PetState.IDLE_CALM:
                    source = self.profile_at(elapsed_seconds)
                    target = profile_for_state(PetState.IDLE_CALM, self._config)
                    self._current_profile = target
                    self._profile_blend = ProfileBlend(
                        source,
                        target,
                        elapsed_seconds,
                        self._config.profile_transition_duration_seconds,
                    )
                    self._state_entered_seconds = elapsed_seconds
                else:
                    self._transition(
                        PetState.IDLE_CALM,
                        TransitionReason.BEHAVIOR_DISABLED,
                        elapsed_seconds,
                    )
            elif self._current_state in {PetState.DRAGGING, PetState.SETTLING}:
                self._resume_state = PetState.IDLE_CALM
                self._resume_elapsed_seconds = 0.0
                self._resume_duration_seconds = None
            elif self._current_state is PetState.CLICK_REACTION:
                self._click_resume_state = PetState.IDLE_CALM
                self._click_resume_elapsed_seconds = 0.0
                self._click_resume_duration_seconds = None
            elif self._current_state is PetState.PAUSED:
                self._paused_state = PetState.IDLE_CALM
                self._paused_elapsed_seconds = 0.0
                self._paused_duration_seconds = None
            return

        duration = self._scheduler.choose_duration(PetState.IDLE_CALM)
        if self._current_state is PetState.IDLE_CALM:
            self._scheduled_duration_seconds = duration
            self._state_entered_seconds = elapsed_seconds
        elif self._current_state in {PetState.DRAGGING, PetState.SETTLING}:
            self._resume_duration_seconds = duration
        elif self._current_state is PetState.CLICK_REACTION:
            self._click_resume_duration_seconds = duration
        elif self._current_state is PetState.PAUSED:
            self._paused_duration_seconds = duration

    def release_drag(self, elapsed_seconds: float) -> None:
        """Enter SETTLING; automatic scheduling remains frozen until the animation reports completion."""
        self._validate_monotonic_time(elapsed_seconds)
        if self._current_state is not PetState.DRAGGING:
            return
        self._transition(PetState.SETTLING, TransitionReason.DRAG_RELEASED, elapsed_seconds, immediate_profile=True)

    def settling_complete(self, elapsed_seconds: float) -> None:
        """Restore the pre-drag base state and its remaining scheduled time."""
        self._validate_monotonic_time(elapsed_seconds)
        if self._current_state is not PetState.SETTLING:
            return
        target = self._resume_state
        if target not in AUTOMATIC_STATES and target is not PetState.STARTING:
            target = PetState.IDLE_CALM
            self._resume_elapsed_seconds = 0.0
            self._resume_duration_seconds = self._scheduler.choose_duration(target)
        duration = self._resume_duration_seconds
        if duration is None and self._behavior_enabled:
            duration = (
                self._config.starting_duration_seconds
                if target is PetState.STARTING
                else self._scheduler.choose_duration(target)
            )
        self._transition(
            target,
            TransitionReason.SETTLING_COMPLETE,
            elapsed_seconds,
            scheduled_duration_seconds=duration,
        )
        self._state_entered_seconds = elapsed_seconds - self._resume_elapsed_seconds
        self._resume_state = None

    def pause(self, elapsed_seconds: float) -> None:
        """Freeze state time and select a safe resumable base state without creating a timer."""
        self._validate_monotonic_time(elapsed_seconds)
        if self._current_state in {PetState.PAUSED, PetState.STOPPED}:
            return
        if self._current_state in {PetState.DRAGGING, PetState.SETTLING}:
            target = self._resume_state if self._resume_state in AUTOMATIC_STATES else PetState.IDLE_CALM
            state_elapsed = self._resume_elapsed_seconds
            duration = self._resume_duration_seconds
        elif self._current_state is PetState.CLICK_REACTION:
            target = self._click_resume_state
            state_elapsed = self._click_resume_elapsed_seconds
            duration = self._click_resume_duration_seconds
            self._clear_click_resume()
        else:
            target = self._current_state
            state_elapsed = max(0.0, elapsed_seconds - self._state_entered_seconds)
            duration = self._scheduled_duration_seconds
        self._paused_state = target
        self._paused_elapsed_seconds = state_elapsed
        self._paused_duration_seconds = duration
        self._transition(PetState.PAUSED, TransitionReason.WINDOW_HIDDEN, elapsed_seconds, immediate_profile=True)

    def resume(self, elapsed_seconds: float) -> None:
        """Resume the saved base state without counting time spent hidden."""
        self._validate_time(elapsed_seconds)
        if self._current_state is not PetState.PAUSED:
            return
        target = self._paused_state
        if target not in AUTOMATIC_STATES and target is not PetState.STARTING:
            target = PetState.IDLE_CALM
        duration = self._paused_duration_seconds
        if duration is None and self._behavior_enabled:
            duration = (
                self._config.starting_duration_seconds
                if target is PetState.STARTING
                else self._scheduler.choose_duration(target)
            )
        self._last_update_seconds = elapsed_seconds
        self._transition(
            target,
            TransitionReason.WINDOW_SHOWN,
            elapsed_seconds,
            scheduled_duration_seconds=duration,
        )
        self._state_entered_seconds = elapsed_seconds - self._paused_elapsed_seconds

    def stop(self, elapsed_seconds: float) -> None:
        """Enter the terminal state exactly once and reject all future changes."""
        self._validate_time(elapsed_seconds)
        if self._current_state is PetState.STOPPED:
            return
        self._transition(
            PetState.STOPPED,
            TransitionReason.APPLICATION_STOPPING,
            elapsed_seconds,
            immediate_profile=True,
        )
        self._started = False

    def state_elapsed_seconds(self, elapsed_seconds: float) -> float:
        """Return active elapsed state time, or the frozen value while paused."""
        self._validate_time(elapsed_seconds)
        if self._current_state is PetState.PAUSED:
            return self._paused_elapsed_seconds
        return max(0.0, elapsed_seconds - self._state_entered_seconds)

    def _transition(
        self,
        next_state: PetState,
        reason: TransitionReason,
        elapsed_seconds: float,
        *,
        scheduled_duration_seconds: float | None = None,
        immediate_profile: bool = False,
        preserve_profile: bool = False,
    ) -> None:
        previous = self._current_state
        validate_transition(previous, next_state)
        previous_elapsed = max(0.0, elapsed_seconds - self._state_entered_seconds)
        source_profile = self.profile_at(elapsed_seconds)
        target_profile = source_profile if preserve_profile else profile_for_state(next_state, self._config)
        self._current_state = next_state
        self._state_entered_seconds = elapsed_seconds
        self._scheduled_duration_seconds = scheduled_duration_seconds
        self._current_profile = target_profile
        if preserve_profile or immediate_profile or next_state in {PetState.PAUSED, PetState.STOPPED}:
            self._profile_blend = None
        else:
            self._profile_blend = ProfileBlend(
                source_profile,
                target_profile,
                elapsed_seconds,
                self._config.profile_transition_duration_seconds,
            )
        transition = StateTransition(
            previous_state=previous,
            next_state=next_state,
            reason=reason,
            elapsed_seconds=previous_elapsed,
            scheduled_duration_seconds=scheduled_duration_seconds,
        )
        self._history.append(transition)
        self._total_transition_count += 1
        self.state_changed.emit(transition)
        self.profile_changed.emit(target_profile)

    def _clear_click_resume(self) -> None:
        self._click_resume_state = None
        self._click_resume_elapsed_seconds = 0.0
        self._click_resume_duration_seconds = None

    @staticmethod
    def _validate_time(elapsed_seconds: float) -> None:
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Behavior elapsed time must be finite and nonnegative.")

    def _validate_monotonic_time(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds)
        if elapsed_seconds < self._last_update_seconds:
            raise ValueError("Behavior elapsed time must be monotonic between lifecycle resets.")
