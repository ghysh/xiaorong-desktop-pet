"""Reproducibility and isolation tests for the local behavior scheduler."""

from __future__ import annotations

import random

import pytest

from desktop_pet.behavior.scheduler import BehaviorScheduler
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.config import BehaviorConfig


def _state_sequence(seed: int, count: int = 30) -> list[PetState]:
    scheduler = BehaviorScheduler(BehaviorConfig(behavior_seed=seed))
    state = PetState.IDLE_CALM
    sequence = []
    for _ in range(count):
        state = scheduler.choose_next_state(state)
        scheduler.choose_duration(state)
        sequence.append(state)
    return sequence


def test_fixed_seed_reproduces_state_sequence_without_touching_global_random() -> None:
    global_state = random.getstate()
    first = _state_sequence(20260805)
    second = _state_sequence(20260805)

    assert first == second
    assert random.getstate() == global_state


def test_scheduler_only_returns_nonself_automatic_states_and_never_repeats_resting() -> None:
    scheduler = BehaviorScheduler(BehaviorConfig(behavior_seed=17))
    state = PetState.IDLE_CALM
    for _ in range(500):
        next_state = scheduler.choose_next_state(state)
        assert next_state in AUTOMATIC_STATES
        assert next_state is not state
        assert next_state not in {PetState.DRAGGING, PetState.PAUSED, PetState.SETTLING, PetState.STOPPED}
        assert not (state is PetState.RESTING and next_state is PetState.RESTING)
        state = next_state


def test_durations_remain_in_ranges_and_invalid_states_are_rejected() -> None:
    scheduler = BehaviorScheduler(BehaviorConfig(behavior_seed=9))
    for state in AUTOMATIC_STATES:
        duration_range = scheduler.duration_range(state)
        values = [scheduler.choose_duration(state) for _ in range(100)]
        assert all(duration_range.minimum_seconds <= value <= duration_range.maximum_seconds for value in values)
    with pytest.raises(ValueError, match="not schedulable"):
        scheduler.choose_next_state(PetState.DRAGGING)
    with pytest.raises(ValueError, match="no automatic duration"):
        scheduler.choose_duration(PetState.PAUSED)


def test_none_seed_creates_and_records_one_process_seed() -> None:
    scheduler = BehaviorScheduler(BehaviorConfig())
    assert isinstance(scheduler.actual_seed, int)
    assert 0 <= scheduler.actual_seed < 2**64
