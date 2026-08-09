"""Stage 10A immutable action-model tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from desktop_pet.actions.model import (
    APPROVED_SOURCE_ASSET_SHA256,
    ActionCategory,
    ActionClip,
    ActionFrame,
    ActionInterruptPolicy,
    ActionLoopMode,
)


def _valid_frame(**changes: object) -> ActionFrame:
    values = {
        "asset_path": "frames/frame_0001.png",
        "duration_ms": 100,
        "anchor_x": 0.5,
        "anchor_y": 0.9733,
    }
    values.update(changes)
    return ActionFrame(**values)


def _valid_clip(**changes: object) -> ActionClip:
    values = {
        "action_id": "walk_left_loop",
        "display_name": "向左行走循环",
        "category": ActionCategory.FRAME_SEQUENCE,
        "frames": (_valid_frame(),),
        "loop_mode": ActionLoopMode.LOOP,
        "interrupt_policy": ActionInterruptPolicy.FINISH_FRAME,
        "priority": 500,
        "default_loop_count": 1,
        "source_asset_sha256": APPROVED_SOURCE_ASSET_SHA256,
        "canvas_width": 1024,
        "canvas_height": 1536,
        "feet_anchor_x": 0.5,
        "feet_anchor_y": 0.9733,
        "tags": ("walk", "left"),
    }
    values.update(changes)
    return ActionClip(**values)


def test_action_enums_are_complete_and_models_are_immutable() -> None:
    assert {item.name for item in ActionCategory} == {
        "OVERLAY",
        "FRAME_SEQUENCE",
        "TRANSFORM",
        "WINDOW_MOVEMENT",
        "REMINDER",
        "USER_SELECTED",
    }
    assert {item.name for item in ActionLoopMode} == {"ONCE", "LOOP", "PING_PONG", "HOLD_LAST_FRAME"}
    assert {item.name for item in ActionInterruptPolicy} == {
        "IMMEDIATE",
        "FINISH_FRAME",
        "FINISH_CYCLE",
        "NOT_INTERRUPTIBLE",
    }
    clip = _valid_clip()
    assert clip.mirror_allowed is False
    with pytest.raises(FrozenInstanceError):
        clip.priority = 1  # type: ignore[misc]


@pytest.mark.parametrize("duration", [0, -1, 1.5, True])
def test_frame_duration_must_be_a_positive_integer(duration: object) -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        _valid_frame(duration_ms=duration)


@pytest.mark.parametrize(
    ("field", "value"),
    [("anchor_x", -0.01), ("anchor_x", 1.01), ("anchor_y", -1), ("anchor_y", 2)],
)
def test_frame_coordinates_and_asset_paths_are_validated(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _valid_frame(**{field: value})
    with pytest.raises(ValueError, match="relative PNG"):
        _valid_frame(asset_path="../outside.png")


def test_runtime_clip_requires_frames_canvas_and_approved_source() -> None:
    with pytest.raises(ValueError, match="at least one frame"):
        _valid_clip(frames=())
    with pytest.raises(ValueError, match="1024 x 1536"):
        _valid_clip(canvas_width=512)
    with pytest.raises(ValueError, match="Plan B"):
        _valid_clip(source_asset_sha256="0" * 64)
    with pytest.raises(ValueError, match="ActionPriority"):
        _valid_clip(priority=501)
