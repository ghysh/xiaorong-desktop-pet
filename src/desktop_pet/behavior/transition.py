"""Immutable transitions and the explicit runtime transition contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from desktop_pet.behavior.state import PetState


class TransitionReason(StrEnum):
    """Fixed reasons suitable for signals, diagnostics, and tests."""

    STARTUP_COMPLETE = "startup_complete"
    SCHEDULED_TRANSITION = "scheduled_transition"
    DRAG_STARTED = "drag_started"
    DRAG_RELEASED = "drag_released"
    SETTLING_COMPLETE = "settling_complete"
    CLICK_STARTED = "click_started"
    CLICK_FINISHED = "click_finished"
    BEHAVIOR_DISABLED = "behavior_disabled"
    WINDOW_HIDDEN = "window_hidden"
    WINDOW_SHOWN = "window_shown"
    APPLICATION_STOPPING = "application_stopping"


@dataclass(frozen=True, slots=True)
class StateTransition:
    """A state change record free of widgets, pixmaps, and mouse-event objects."""

    previous_state: PetState
    next_state: PetState
    reason: TransitionReason
    elapsed_seconds: float
    scheduled_duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.previous_state is self.next_state:
            raise ValueError("Behavior state transitions cannot be self-loops.")
        if not isinstance(self.reason, TransitionReason):
            raise ValueError("Behavior transition reason must be a fixed TransitionReason.")
        if not isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("Transition elapsed time must be finite and nonnegative.")
        if self.scheduled_duration_seconds is not None and (
            not isfinite(self.scheduled_duration_seconds) or self.scheduled_duration_seconds <= 0
        ):
            raise ValueError("Scheduled duration must be finite and greater than zero.")


_AUTOMATIC_TARGETS = {
    PetState.IDLE_CALM: frozenset({PetState.IDLE_QUIET, PetState.IDLE_SWAY, PetState.RESTING}),
    PetState.IDLE_QUIET: frozenset({PetState.IDLE_CALM, PetState.IDLE_SWAY}),
    PetState.IDLE_SWAY: frozenset({PetState.IDLE_CALM, PetState.IDLE_QUIET}),
    PetState.RESTING: frozenset({PetState.IDLE_CALM, PetState.IDLE_QUIET}),
}


def automatic_targets(state: PetState) -> frozenset[PetState]:
    """Return scheduled targets for an automatic state or reject invalid input."""
    try:
        return _AUTOMATIC_TARGETS[state]
    except KeyError as error:
        raise ValueError(f"State is not schedulable: {state.name}") from error


def is_transition_allowed(previous: PetState, next_state: PetState) -> bool:
    """Check static transition legality; restoration targets are documented explicitly."""
    if previous is next_state or previous is PetState.STOPPED:
        return False
    if next_state is PetState.STOPPED:
        return True
    if next_state is PetState.PAUSED:
        return previous is not PetState.STOPPED
    if next_state is PetState.DRAGGING:
        return previous not in {PetState.PAUSED, PetState.STOPPED, PetState.DRAGGING}
    if next_state is PetState.CLICK_REACTION:
        return previous is PetState.STARTING or previous in _AUTOMATIC_TARGETS
    if previous is PetState.CLICK_REACTION:
        return next_state is PetState.STARTING or next_state in _AUTOMATIC_TARGETS
    if previous is PetState.STARTING:
        return next_state is PetState.IDLE_CALM
    if previous in _AUTOMATIC_TARGETS:
        return next_state in _AUTOMATIC_TARGETS[previous]
    if previous is PetState.DRAGGING:
        return next_state is PetState.SETTLING
    if previous is PetState.SETTLING:
        return next_state in {
            PetState.STARTING,
            PetState.IDLE_CALM,
            PetState.IDLE_QUIET,
            PetState.IDLE_SWAY,
            PetState.RESTING,
        }
    if previous is PetState.PAUSED:
        return next_state in {
            PetState.STARTING,
            PetState.IDLE_CALM,
            PetState.IDLE_QUIET,
            PetState.IDLE_SWAY,
            PetState.RESTING,
        }
    return False


def validate_transition(previous: PetState, next_state: PetState) -> None:
    """Raise a clear error for a forbidden state change."""
    if not is_transition_allowed(previous, next_state):
        raise ValueError(f"Illegal behavior transition: {previous.name} -> {next_state.name}")
