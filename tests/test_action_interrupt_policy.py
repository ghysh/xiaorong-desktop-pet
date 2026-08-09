"""Queued frame/cycle boundaries and forced global interruption."""

from __future__ import annotations

from desktop_pet.actions.arbiter import ArbitrationDecision
from desktop_pet.actions.model import ActionLoopMode
from desktop_pet.actions.player import ActionPlayer
from tests.action_test_helpers import make_clip


def test_queue_after_frame_switches_at_absolute_frame_boundary() -> None:
    first = make_clip(action_id="first_action", durations=(100, 100))
    second = make_clip(action_id="second_action", durations=(40,))
    player = ActionPlayer()
    player.start(first, 0.0)
    player.update(0.030)
    player.queue(second, ArbitrationDecision.QUEUE_AFTER_FRAME, 0.030)
    player.update(0.099)
    assert player.current_clip is first
    player.update(0.100)
    assert player.current_clip is second


def test_queue_after_cycle_waits_for_loop_cycle_boundary() -> None:
    first = make_clip(action_id="first_loop", loop_mode=ActionLoopMode.LOOP, durations=(50, 50), loop_count=3)
    second = make_clip(action_id="second_action", durations=(40,))
    player = ActionPlayer()
    player.start(first, 0.0)
    player.update(0.060)
    player.queue(second, ArbitrationDecision.QUEUE_AFTER_CYCLE, 0.060)
    player.update(0.099)
    assert player.current_clip is first
    player.update(0.100)
    assert player.current_clip is second


def test_forced_interrupt_clears_frame_pending_and_emits_reason() -> None:
    player = ActionPlayer()
    interruptions: list[object] = []
    changed: list[object] = []
    player.clip_interrupted.connect(interruptions.append)
    player.frame_changed.connect(changed.append)
    first = make_clip(action_id="first_action")
    player.start(first, 0.0)
    player.queue(make_clip(action_id="second_action"), ArbitrationDecision.QUEUE_AFTER_FRAME, 0.01)
    assert player.interrupt(0.02, reason="dragging")
    assert player.pending_action_id is None
    assert player.current_frame is None
    assert interruptions[-1].reason == "dragging"
    assert changed[-1] is None
