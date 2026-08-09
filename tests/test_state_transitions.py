"""Allowed and forbidden behavior transition table tests."""

from __future__ import annotations

import pytest

from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.behavior.transition import (
    StateTransition,
    TransitionReason,
    automatic_targets,
    is_transition_allowed,
    validate_transition,
)


def test_starting_and_automatic_transition_tables_are_exact() -> None:
    assert is_transition_allowed(PetState.STARTING, PetState.IDLE_CALM)
    assert not is_transition_allowed(PetState.STARTING, PetState.RESTING)
    assert automatic_targets(PetState.IDLE_CALM) == {
        PetState.IDLE_QUIET,
        PetState.IDLE_SWAY,
        PetState.RESTING,
    }
    assert automatic_targets(PetState.IDLE_QUIET) == {PetState.IDLE_CALM, PetState.IDLE_SWAY}
    assert automatic_targets(PetState.IDLE_SWAY) == {PetState.IDLE_CALM, PetState.IDLE_QUIET}
    assert automatic_targets(PetState.RESTING) == {PetState.IDLE_CALM, PetState.IDLE_QUIET}


def test_high_priority_drag_settling_pause_and_stop_rules() -> None:
    assert all(is_transition_allowed(state, PetState.DRAGGING) for state in AUTOMATIC_STATES)
    assert is_transition_allowed(PetState.DRAGGING, PetState.SETTLING)
    assert not is_transition_allowed(PetState.DRAGGING, PetState.RESTING)
    assert is_transition_allowed(PetState.SETTLING, PetState.IDLE_SWAY)
    assert not is_transition_allowed(PetState.PAUSED, PetState.DRAGGING)
    assert is_transition_allowed(PetState.PAUSED, PetState.IDLE_CALM)
    assert all(is_transition_allowed(state, PetState.STOPPED) for state in PetState if state is not PetState.STOPPED)


def test_self_loops_and_illegal_transitions_fail_clearly() -> None:
    for state in PetState:
        assert not is_transition_allowed(state, state)
    with pytest.raises(ValueError, match="Illegal behavior transition"):
        validate_transition(PetState.STARTING, PetState.RESTING)
    with pytest.raises(ValueError, match="self-loops"):
        StateTransition(
            PetState.IDLE_CALM,
            PetState.IDLE_CALM,
            TransitionReason.SCHEDULED_TRANSITION,
            1.0,
        )
