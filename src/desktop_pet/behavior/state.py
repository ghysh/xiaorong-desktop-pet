"""Behavior states and their explicit priority groups."""

from __future__ import annotations

from enum import Enum, auto


class PetState(Enum):
    """All runtime states; values are never used as display or persistence strings."""

    STARTING = auto()
    IDLE_CALM = auto()
    IDLE_QUIET = auto()
    IDLE_SWAY = auto()
    RESTING = auto()
    DRAGGING = auto()
    SETTLING = auto()
    CLICK_REACTION = auto()
    PAUSED = auto()
    STOPPED = auto()


AUTOMATIC_STATES = frozenset(
    {
        PetState.IDLE_CALM,
        PetState.IDLE_QUIET,
        PetState.IDLE_SWAY,
        PetState.RESTING,
    }
)

STATE_PRIORITY = {
    PetState.STOPPED: 7,
    PetState.PAUSED: 6,
    PetState.DRAGGING: 5,
    PetState.SETTLING: 4,
    PetState.CLICK_REACTION: 3,
    PetState.STARTING: 2,
    PetState.IDLE_CALM: 1,
    PetState.IDLE_QUIET: 1,
    PetState.IDLE_SWAY: 1,
    PetState.RESTING: 1,
}


def state_priority(state: PetState) -> int:
    """Return the explicit behavior priority without relying on enum numeric values."""
    return STATE_PRIORITY[state]
