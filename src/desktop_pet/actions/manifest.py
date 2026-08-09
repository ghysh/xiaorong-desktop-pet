"""Strict JSON manifest parsing without making planned actions runnable."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from desktop_pet.actions.model import (
    ActionCategory,
    ActionClip,
    ActionFrame,
    ActionInterruptPolicy,
    ActionLoopMode,
    validate_action_priority,
    validate_canvas,
    validate_normalized_coordinate,
    validate_positive_integer,
    validate_source_hash,
    validate_stable_identifier,
)

SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_STATUSES = frozenset({"planned", "draft", "ready", "disabled"})


@dataclass(frozen=True, slots=True)
class PlanningEstimate:
    """Non-runtime production estimate stored beside a planned action."""

    frame_count_min: int
    frame_count_max: int
    fps_min: int
    fps_max: int
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("frame_count_min", "frame_count_max", "fps_min", "fps_max"):
            validate_positive_integer(getattr(self, name), name)
        if self.frame_count_min > self.frame_count_max or self.fps_min > self.fps_max:
            raise ValueError("Planning estimate minimum values cannot exceed maximum values.")
        if not isinstance(self.notes, tuple) or any(
            not isinstance(note, str) or not note.strip() for note in self.notes
        ):
            raise ValueError("Planning notes must be nonempty strings in a tuple.")


@dataclass(frozen=True, slots=True)
class ActionManifest:
    """Serializable action metadata that may remain intentionally non-runnable."""

    schema_version: int
    action_id: str
    display_name: str
    status: str
    runtime_enabled: bool
    assets_complete: bool
    category: ActionCategory
    loop_mode: ActionLoopMode
    interrupt_policy: ActionInterruptPolicy
    priority: int
    default_loop_count: int
    mirror_allowed: bool
    source_asset_sha256: str
    canvas_width: int
    canvas_height: int
    feet_anchor_x: float
    feet_anchor_y: float
    tags: tuple[str, ...]
    frames: tuple[ActionFrame, ...]
    planning: PlanningEstimate

    def __post_init__(self) -> None:
        if self.schema_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(f"Unsupported action manifest schema version: {self.schema_version}")
        validate_stable_identifier(self.action_id, "action_id")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("Action manifest display_name must be nonempty.")
        if self.status not in SUPPORTED_STATUSES:
            raise ValueError(f"Unsupported action manifest status: {self.status}")
        if not isinstance(self.runtime_enabled, bool) or not isinstance(self.assets_complete, bool):
            raise ValueError("Action manifest runtime flags must be boolean.")
        if self.status == "planned" and (self.runtime_enabled or self.assets_complete):
            raise ValueError("Planned actions cannot be runtime-enabled or asset-complete.")
        if self.status in {"draft", "disabled"} and self.runtime_enabled:
            raise ValueError(f"{self.status.title()} actions cannot be runtime-enabled.")
        if not isinstance(self.category, ActionCategory):
            raise ValueError("Action manifest category must be an ActionCategory.")
        if not isinstance(self.loop_mode, ActionLoopMode):
            raise ValueError("Action manifest loop_mode must be an ActionLoopMode.")
        if not isinstance(self.interrupt_policy, ActionInterruptPolicy):
            raise ValueError("Action manifest interrupt_policy must be an ActionInterruptPolicy.")
        if not isinstance(self.mirror_allowed, bool):
            raise ValueError("Action manifest mirror_allowed must be boolean.")
        validate_action_priority(self.priority)
        validate_positive_integer(self.default_loop_count, "default_loop_count")
        validate_source_hash(self.source_asset_sha256)
        validate_canvas(self.canvas_width, self.canvas_height)
        validate_normalized_coordinate(self.feet_anchor_x, "feet_anchor_x")
        validate_normalized_coordinate(self.feet_anchor_y, "feet_anchor_y")
        if not isinstance(self.tags, tuple) or len(set(self.tags)) != len(self.tags):
            raise ValueError("Action manifest tags must be a unique tuple.")
        for tag in self.tags:
            validate_stable_identifier(tag, "tag")
        if not isinstance(self.frames, tuple) or any(not isinstance(frame, ActionFrame) for frame in self.frames):
            raise ValueError("Action manifest frames must be a tuple of ActionFrame values.")
        if not isinstance(self.planning, PlanningEstimate):
            raise ValueError("Action manifest planning must be a PlanningEstimate.")

    def to_clip(self) -> ActionClip:
        """Create a runtime-ready clip only after a later stage completes and enables assets."""
        if self.status != "ready" or not self.runtime_enabled or not self.assets_complete:
            raise ValueError("A planned or incomplete action manifest cannot become a runtime ActionClip.")
        return ActionClip(
            action_id=self.action_id,
            display_name=self.display_name,
            category=self.category,
            frames=self.frames,
            loop_mode=self.loop_mode,
            interrupt_policy=self.interrupt_policy,
            priority=self.priority,
            default_loop_count=self.default_loop_count,
            mirror_allowed=self.mirror_allowed,
            source_asset_sha256=self.source_asset_sha256,
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            feet_anchor_x=self.feet_anchor_x,
            feet_anchor_y=self.feet_anchor_y,
            tags=self.tags,
        )


def load_action_manifest(path: Path | str) -> ActionManifest:
    """Load one UTF-8 JSON manifest with clear field errors."""
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid action manifest JSON: {manifest_path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Action manifest root must be an object: {manifest_path}")
    try:
        canvas = payload["canvas"]
        feet_anchor = payload["feet_anchor"]
        planning = payload["planning"]
        frames = tuple(_frame_from_dict(frame) for frame in payload["frames"])
        return ActionManifest(
            schema_version=payload["schema_version"],
            action_id=payload["action_id"],
            display_name=payload["display_name"],
            status=payload["status"],
            runtime_enabled=payload["runtime_enabled"],
            assets_complete=payload["assets_complete"],
            category=ActionCategory[payload["category"]],
            loop_mode=ActionLoopMode[payload["loop_mode"]],
            interrupt_policy=ActionInterruptPolicy[payload["interrupt_policy"]],
            priority=payload["priority"],
            default_loop_count=payload["default_loop_count"],
            mirror_allowed=payload.get("mirror_allowed", False),
            source_asset_sha256=payload["source_asset_sha256"],
            canvas_width=canvas["width"],
            canvas_height=canvas["height"],
            feet_anchor_x=feet_anchor["x"],
            feet_anchor_y=feet_anchor["y"],
            tags=tuple(payload["tags"]),
            frames=frames,
            planning=PlanningEstimate(
                frame_count_min=planning["frame_count_min"],
                frame_count_max=planning["frame_count_max"],
                fps_min=planning["fps_min"],
                fps_max=planning["fps_max"],
                notes=tuple(planning.get("notes", [])),
            ),
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"Invalid or missing action manifest field in {manifest_path}: {error}") from error


def _frame_from_dict(payload: object) -> ActionFrame:
    if not isinstance(payload, dict):
        raise ValueError("Each action manifest frame must be an object.")
    try:
        return ActionFrame(
            asset_path=payload["asset_path"],
            duration_ms=payload["duration_ms"],
            anchor_x=payload["anchor_x"],
            anchor_y=payload["anchor_y"],
            event=payload.get("event"),
        )
    except KeyError as error:
        raise ValueError(f"Missing action frame field: {error}") from error
