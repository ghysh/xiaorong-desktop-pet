"""Small deterministic ActionClip factories shared by Stage 10B tests."""

from __future__ import annotations

from desktop_pet.actions.model import (
    APPROVED_SOURCE_ASSET_SHA256,
    ActionCategory,
    ActionClip,
    ActionFrame,
    ActionInterruptPolicy,
    ActionLoopMode,
    ActionPriority,
)


def make_frame(index: int, duration_ms: int = 50) -> ActionFrame:
    return ActionFrame(
        asset_path=f"frames/test_{index:02d}.png",
        duration_ms=duration_ms,
        anchor_x=0.5,
        anchor_y=0.9733,
        event=f"frame_{index}",
    )


def make_clip(
    *,
    action_id: str = "test_action",
    loop_mode: ActionLoopMode = ActionLoopMode.ONCE,
    interrupt_policy: ActionInterruptPolicy = ActionInterruptPolicy.IMMEDIATE,
    priority: ActionPriority = ActionPriority.BLINK,
    durations: tuple[int, ...] = (40, 60),
    loop_count: int = 1,
) -> ActionClip:
    return ActionClip(
        action_id=action_id,
        display_name="测试动作",
        category=ActionCategory.OVERLAY,
        frames=tuple(make_frame(index, duration) for index, duration in enumerate(durations)),
        loop_mode=loop_mode,
        interrupt_policy=interrupt_policy,
        priority=priority,
        default_loop_count=loop_count,
        source_asset_sha256=APPROVED_SOURCE_ASSET_SHA256,
        canvas_width=1024,
        canvas_height=1536,
        feet_anchor_x=0.5,
        feet_anchor_y=0.9733,
        tags=("test",),
    )
