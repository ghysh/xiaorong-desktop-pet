"""BlinkController state gate, request deduplication, and completion behavior."""

from __future__ import annotations

from desktop_pet.behavior.state import PetState
from desktop_pet.blink.controller import BlinkController
from desktop_pet.config import BlinkConfig


def test_startup_waits_then_idle_submits_one_deduplicated_request() -> None:
    controller = BlinkController(BlinkConfig(seed=5))
    assert controller.update(0.0, PetState.STARTING) is None
    assert controller.update(0.45, PetState.IDLE_CALM) is None
    due = controller.scheduler.next_due_seconds
    assert due is not None and due >= 2.45
    request = controller.update(due, PetState.IDLE_CALM)
    assert request is not None and request.action_id == "blink_normal"
    assert controller.update(due + 0.01, PetState.IDLE_CALM) is None


def test_accept_finish_and_interrupt_do_not_change_pet_state() -> None:
    controller = BlinkController(BlinkConfig(seed=8))
    state = PetState.IDLE_QUIET
    controller.update(0.0, state)
    due = controller.scheduler.next_due_seconds
    assert due is not None
    assert controller.update(due, state) is not None
    controller.resolve_request(True, due)
    assert controller.is_active
    controller.on_clip_finished(due + 0.195)
    assert not controller.is_active
    assert state is PetState.IDLE_QUIET


def test_every_nonidle_state_blocks_autonomous_blink() -> None:
    forbidden = (
        PetState.STARTING,
        PetState.CLICK_REACTION,
        PetState.DRAGGING,
        PetState.SETTLING,
        PetState.PAUSED,
        PetState.STOPPED,
    )
    for state in forbidden:
        assert BlinkController(BlinkConfig(seed=1)).update(100.0, state) is None
