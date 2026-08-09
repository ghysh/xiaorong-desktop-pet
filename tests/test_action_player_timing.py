"""Absolute-time progression, delayed ticks, boundaries, pause, and large inputs."""

from __future__ import annotations

import pytest

from desktop_pet.actions.player import ActionPlayer
from tests.action_test_helpers import make_clip


def test_delayed_tick_skips_expired_intermediate_frames() -> None:
    clip = make_clip(durations=(20, 30, 40, 50))
    player = ActionPlayer()
    changed: list[object] = []
    player.frame_changed.connect(changed.append)
    player.start(clip, 1.0)
    player.update(1.095)
    assert player.current_playback_frame is not None
    assert player.current_playback_frame.frame_index == 3
    assert len(changed) == 2


def test_equal_times_are_deterministic_and_do_not_repeat_signals() -> None:
    player = ActionPlayer()
    changed: list[object] = []
    player.frame_changed.connect(changed.append)
    player.start(make_clip(), 0.0)
    for _ in range(10):
        player.update(0.020)
    assert len(changed) == 1


def test_pause_resume_freezes_action_elapsed_time() -> None:
    player = ActionPlayer()
    clip = make_clip(durations=(100, 100))
    player.start(clip, 0.0)
    player.update(0.050)
    player.pause(0.050)
    player.update(10.0)
    assert player.current_frame is clip.frames[0]
    player.resume(10.0)
    player.update(10.049)
    assert player.current_frame is clip.frames[0]
    player.update(10.050)
    assert player.current_frame is clip.frames[1]


@pytest.mark.parametrize("value", (-1.0, float("nan"), float("inf")))
def test_invalid_elapsed_time_is_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        ActionPlayer().start(make_clip(), value)


def test_time_cannot_move_backwards_but_large_values_are_safe() -> None:
    player = ActionPlayer()
    player.start(make_clip(), 5.0)
    player.update(5.01)
    with pytest.raises(ValueError, match="monotonic"):
        player.update(5.0)
    player.update(1e12)
    assert player.current_clip is None
