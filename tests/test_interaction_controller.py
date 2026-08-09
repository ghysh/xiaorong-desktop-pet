"""Click validation, state restoration, and drag priority tests."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt

from desktop_pet.behavior.controller import BehaviorController
from desktop_pet.behavior.state import PetState
from desktop_pet.config import BehaviorConfig
from desktop_pet.interaction.controller import InteractionController


def _controller() -> tuple[BehaviorController, InteractionController]:
    behavior = BehaviorController(BehaviorConfig(behavior_seed=9))
    behavior.start(0.0)
    return behavior, InteractionController(behavior)


def _valid_click(interaction: InteractionController, elapsed: float = 0.10) -> bool:
    return interaction.try_start_click(
        elapsed_seconds=elapsed,
        button=Qt.MouseButton.LeftButton,
        press_hit=True,
        release_hit=True,
        movement_distance=0.0,
        drag_threshold=10,
        held_ms=80,
    )


def test_valid_click_enters_and_finishes_at_260ms_without_losing_starting_time() -> None:
    behavior, interaction = _controller()
    assert _valid_click(interaction)
    assert behavior.current_state is PetState.CLICK_REACTION
    interaction.update(0.359)
    assert behavior.current_state is PetState.CLICK_REACTION
    interaction.update(0.360)
    assert behavior.current_state is PetState.STARTING
    assert behavior.state_elapsed_seconds(0.360) == pytest.approx(0.10)


def test_transparent_drag_right_long_and_paused_gestures_are_rejected() -> None:
    cases = [
        {"press_hit": False},
        {"release_hit": False},
        {"movement_distance": 10.0},
        {"button": Qt.MouseButton.RightButton},
        {"held_ms": 501},
        {"context_menu_open": True},
    ]
    for override in cases:
        behavior, interaction = _controller()
        arguments = {
            "elapsed_seconds": 0.1,
            "button": Qt.MouseButton.LeftButton,
            "press_hit": True,
            "release_hit": True,
            "movement_distance": 0.0,
            "drag_threshold": 10,
            "held_ms": 50,
            "context_menu_open": False,
        }
        arguments.update(override)
        assert not interaction.try_start_click(**arguments)
        assert behavior.current_state is PetState.STARTING

    behavior, interaction = _controller()
    behavior.pause(0.1)
    assert not _valid_click(interaction, 0.1)


def test_drag_immediately_overrides_active_click_and_does_not_move_a_widget() -> None:
    behavior, interaction = _controller()
    assert _valid_click(interaction)
    interaction.cancel_for_drag()
    behavior.begin_drag(0.15)
    assert behavior.current_state is PetState.DRAGGING
    assert not interaction.is_active
    assert interaction.current_transform.offset_x == 0.0
    assert QPoint(1, 2) == QPoint(1, 2)
