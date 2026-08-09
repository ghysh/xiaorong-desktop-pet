"""Core ActionPlayer loop-mode and signal behavior."""

from __future__ import annotations

from desktop_pet.actions.model import ActionLoopMode
from desktop_pet.actions.player import ActionPlayer
from tests.action_test_helpers import make_clip


def test_once_emits_frames_once_and_finishes_at_exact_total() -> None:
    player = ActionPlayer()
    changed: list[object] = []
    finished: list[object] = []
    player.frame_changed.connect(changed.append)
    player.clip_finished.connect(finished.append)
    clip = make_clip()
    player.start(clip, 10.0)
    assert player.current_frame is clip.frames[0]
    player.update(10.039)
    assert len(changed) == 1
    player.update(10.040)
    assert player.current_frame is clip.frames[1]
    player.update(10.100)
    assert player.current_clip is None
    assert finished == [clip]
    assert changed[-1] is None


def test_loop_repeats_for_requested_count_then_finishes() -> None:
    clip = make_clip(loop_mode=ActionLoopMode.LOOP, durations=(40, 60), loop_count=2)
    player = ActionPlayer()
    player.start(clip, 0.0)
    player.update(0.100)
    assert player.current_playback_frame is not None
    assert player.current_playback_frame.cycle_index == 1
    assert player.current_playback_frame.frame_index == 0
    player.update(0.200)
    assert player.current_clip is None


def test_ping_pong_avoids_repeating_endpoint_frames() -> None:
    clip = make_clip(loop_mode=ActionLoopMode.PING_PONG, durations=(10, 10, 10), loop_count=1)
    player = ActionPlayer()
    player.start(clip, 0.0)
    observed = []
    for elapsed in (0.0, 0.010, 0.020, 0.030):
        player.update(elapsed)
        assert player.current_playback_frame is not None
        observed.append((player.current_playback_frame.frame_index, player.current_playback_frame.direction))
    assert observed == [(0, 1), (1, 1), (2, 1), (1, -1)]


def test_hold_last_frame_never_finishes_until_interrupted() -> None:
    clip = make_clip(loop_mode=ActionLoopMode.HOLD_LAST_FRAME)
    player = ActionPlayer()
    finished: list[object] = []
    player.clip_finished.connect(finished.append)
    player.start(clip, 0.0)
    player.update(10_000.0)
    assert player.current_frame is clip.frames[-1]
    assert finished == []
    assert player.interrupt(10_000.0, reason="test stop")
    assert player.current_clip is None
