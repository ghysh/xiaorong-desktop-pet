"""State enumeration and priority invariants for Stage 8."""

from __future__ import annotations

from desktop_pet.behavior.state import AUTOMATIC_STATES, STATE_PRIORITY, PetState, state_priority
from desktop_pet.behavior.transition import is_transition_allowed


def test_pet_state_contains_all_unique_required_states() -> None:
    assert {state.name for state in PetState} == {
        "STARTING",
        "IDLE_CALM",
        "IDLE_QUIET",
        "IDLE_SWAY",
        "RESTING",
        "DRAGGING",
        "SETTLING",
        "CLICK_REACTION",
        "PAUSED",
        "STOPPED",
    }
    assert len({state.value for state in PetState}) == len(PetState)


def test_automatic_state_set_and_priority_order_are_explicit() -> None:
    assert AUTOMATIC_STATES == {
        PetState.IDLE_CALM,
        PetState.IDLE_QUIET,
        PetState.IDLE_SWAY,
        PetState.RESTING,
    }
    assert state_priority(PetState.STOPPED) > state_priority(PetState.PAUSED)
    assert state_priority(PetState.PAUSED) > state_priority(PetState.DRAGGING)
    assert state_priority(PetState.DRAGGING) > state_priority(PetState.SETTLING)
    assert state_priority(PetState.SETTLING) > state_priority(PetState.CLICK_REACTION)
    assert state_priority(PetState.CLICK_REACTION) > state_priority(PetState.STARTING)
    assert all(STATE_PRIORITY[state] == 1 for state in AUTOMATIC_STATES)


def test_stopped_cannot_leave_and_logic_does_not_depend_on_display_strings() -> None:
    assert all(not is_transition_allowed(PetState.STOPPED, state) for state in PetState)
    assert all(not isinstance(state.value, str) for state in PetState)
