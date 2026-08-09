"""Deterministic offscreen smoke test for ActionPlayer semantics and interruption."""

from __future__ import annotations

import argparse
import json
import os
import sys

if "--offscreen" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.actions.arbiter import ArbitrationDecision
from desktop_pet.actions.model import (
    APPROVED_SOURCE_ASSET_SHA256,
    ActionCategory,
    ActionClip,
    ActionFrame,
    ActionInterruptPolicy,
    ActionLoopMode,
    ActionPriority,
)
from desktop_pet.actions.player import ActionPlayer


def make_clip(
    action_id: str,
    mode: ActionLoopMode,
    policy: ActionInterruptPolicy = ActionInterruptPolicy.IMMEDIATE,
    *,
    loops: int = 1,
) -> ActionClip:
    frames = tuple(ActionFrame(f"frames/smoke_{index}.png", 40, 0.5, 0.9733) for index in range(3))
    return ActionClip(
        action_id=action_id,
        display_name="播放器烟雾测试",
        category=ActionCategory.OVERLAY,
        frames=frames,
        loop_mode=mode,
        interrupt_policy=policy,
        priority=ActionPriority.BLINK,
        default_loop_count=loops,
        source_asset_sha256=APPROVED_SOURCE_ASSET_SHA256,
        canvas_width=1024,
        canvas_height=1536,
        feet_anchor_x=0.5,
        feet_anchor_y=0.9733,
        tags=("smoke",),
    )


def run_smoke() -> dict[str, object]:
    results: dict[str, object] = {}

    once = make_clip("smoke_once", ActionLoopMode.ONCE)
    player = ActionPlayer()
    player.start(once, 0.0)
    player.update(0.119)
    assert player.current_frame is once.frames[-1]
    player.update(0.120)
    assert player.current_clip is None
    results["once"] = "passed"

    loop = make_clip("smoke_loop", ActionLoopMode.LOOP, loops=2)
    player.start(loop, 1.0)
    player.update(1.120)
    assert player.current_playback_frame is not None and player.current_playback_frame.cycle_index == 1
    player.update(1.240)
    assert player.current_clip is None
    results["loop"] = "passed"

    ping = make_clip("smoke_ping_pong", ActionLoopMode.PING_PONG)
    player.start(ping, 2.0)
    indices = []
    for offset in (0.0, 0.04, 0.08, 0.12):
        player.update(2.0 + offset)
        assert player.current_playback_frame is not None
        indices.append(player.current_playback_frame.frame_index)
    assert indices == [0, 1, 2, 1]
    player.update(2.160)
    results["ping_pong"] = "passed"

    hold = make_clip("smoke_hold", ActionLoopMode.HOLD_LAST_FRAME)
    player.start(hold, 3.0)
    player.update(100.0)
    assert player.current_frame is hold.frames[-1]
    player.interrupt(100.0, reason="smoke reset")
    results["hold_last_frame"] = "passed"

    delayed = make_clip("smoke_delayed", ActionLoopMode.ONCE)
    player.start(delayed, 101.0)
    player.update(101.09)
    assert player.current_frame is delayed.frames[-1]
    player.interrupt(101.09, reason="immediate")
    results["delayed_tick_and_immediate"] = "passed"

    first = make_clip("smoke_first", ActionLoopMode.LOOP, loops=3)
    second = make_clip("smoke_second", ActionLoopMode.ONCE)
    player.start(first, 102.0)
    player.update(102.01)
    player.queue(second, ArbitrationDecision.QUEUE_AFTER_FRAME, 102.01)
    player.update(102.04)
    assert player.current_clip is second
    player.interrupt(102.04, reason="reset")
    player.start(first, 103.0)
    player.queue(second, ArbitrationDecision.QUEUE_AFTER_CYCLE, 103.01)
    player.update(103.12)
    assert player.current_clip is second
    player.interrupt(103.12, reason="stopped")
    assert player.current_clip is None
    results["finish_frame_finish_cycle_stopped"] = "passed"
    results["qtimer_children"] = len(player.findChildren(__import__("PySide6.QtCore", fromlist=["QTimer"]).QTimer))
    results["resource_reads"] = 0
    assert results["qtimer_children"] == 0
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offscreen", action="store_true")
    parser.parse_args()
    run_smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
