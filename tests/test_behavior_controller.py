"""Injected-time state-machine tests without real-duration waits."""

from __future__ import annotations

import pytest

from desktop_pet.behavior.controller import BehaviorController
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.behavior.transition import TransitionReason
from desktop_pet.config import BehaviorConfig, StateDurationRange


def _fast_config(seed: int = 3) -> BehaviorConfig:
    return BehaviorConfig(
        behavior_seed=seed,
        starting_duration_seconds=0.15,
        calm_duration=StateDurationRange(0.5, 0.5),
        quiet_duration=StateDurationRange(0.5, 0.5),
        sway_duration=StateDurationRange(0.5, 0.5),
        resting_duration=StateDurationRange(0.5, 0.5),
        profile_transition_duration_seconds=0.10,
    )


def test_initial_startup_and_scheduled_transition_use_injected_time() -> None:
    controller = BehaviorController(_fast_config())
    transitions = []
    controller.state_changed.connect(transitions.append)
    controller.start(0.0)
    controller.update(0.149)
    assert controller.current_state is PetState.STARTING
    controller.update(0.15)
    assert controller.current_state is PetState.IDLE_CALM
    controller.update(0.65)
    assert controller.current_state in AUTOMATIC_STATES - {PetState.IDLE_CALM}
    assert [transition.reason for transition in transitions[:2]] == [
        TransitionReason.STARTUP_COMPLETE,
        TransitionReason.SCHEDULED_TRANSITION,
    ]


def test_drag_override_freezes_auto_elapsed_and_settling_restores_base_state() -> None:
    controller = BehaviorController(_fast_config())
    controller.start(0.0)
    controller.update(0.15)
    controller.begin_drag(0.35)
    assert controller.current_state is PetState.DRAGGING
    controller.update(10.0)
    assert controller.current_state is PetState.DRAGGING
    controller.release_drag(10.0)
    assert controller.current_state is PetState.SETTLING
    controller.settling_complete(10.22)
    assert controller.current_state is PetState.IDLE_CALM
    assert controller.state_elapsed_seconds(10.22) == pytest.approx(0.20)


def test_pause_resume_freezes_time_and_stop_is_terminal() -> None:
    controller = BehaviorController(_fast_config())
    controller.start(0.0)
    controller.update(0.15)
    controller.pause(0.30)
    frozen = controller.state_elapsed_seconds(100.0)
    assert controller.current_state is PetState.PAUSED
    assert frozen == 0.15
    controller.resume(0.0)
    assert controller.current_state is PetState.IDLE_CALM
    assert controller.state_elapsed_seconds(0.0) == 0.15
    controller.stop(0.1)
    assert controller.current_state is PetState.STOPPED
    controller.update(100.0)
    controller.begin_drag(100.0)
    assert controller.current_state is PetState.STOPPED
    assert len(controller.history) <= 100
