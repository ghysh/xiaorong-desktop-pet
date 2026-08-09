"""Blink remains below click/drag/lifecycle and cannot disturb higher-priority behavior."""

from __future__ import annotations

from desktop_pet.actions.model import ActionPriority
from desktop_pet.behavior.state import PetState
from desktop_pet.blink.controller import BlinkController
from desktop_pet.config import BlinkConfig


def test_blink_priority_is_below_every_interactive_override() -> None:
    assert ActionPriority.STOPPED > ActionPriority.PAUSED > ActionPriority.DRAGGING
    assert ActionPriority.DRAGGING > ActionPriority.CLICK_REACTION > ActionPriority.BLINK > ActionPriority.IDLE


def test_state_gate_rejects_blink_during_click_drag_pause_and_stop() -> None:
    for state in (PetState.CLICK_REACTION, PetState.DRAGGING, PetState.PAUSED, PetState.STOPPED):
        controller = BlinkController(BlinkConfig(seed=3))
        assert controller.update(100.0, state) is None
        assert not controller.is_active
