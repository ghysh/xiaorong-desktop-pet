"""Immutable, Qt-free models for future action clips."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from pathlib import PurePosixPath

APPROVED_SOURCE_ASSET_SHA256 = "6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64"
APPROVED_CANVAS_SIZE = (1024, 1536)
_STABLE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class ActionCategory(Enum):
    """Rendering or orchestration responsibility of an action."""

    OVERLAY = auto()
    FRAME_SEQUENCE = auto()
    TRANSFORM = auto()
    WINDOW_MOVEMENT = auto()
    REMINDER = auto()
    USER_SELECTED = auto()


class ActionLoopMode(Enum):
    """How a future player advances after the final frame."""

    ONCE = auto()
    LOOP = auto()
    PING_PONG = auto()
    HOLD_LAST_FRAME = auto()


class ActionInterruptPolicy(Enum):
    """Clip-local interruption boundary below global drag/stop overrides."""

    IMMEDIATE = auto()
    FINISH_FRAME = auto()
    FINISH_CYCLE = auto()
    NOT_INTERRUPTIBLE = auto()


class ActionPriority(IntEnum):
    """One centralized priority scale; larger values win."""

    IDLE = 100
    BLINK = 200
    CLICK_REACTION = 300
    AUTONOMOUS_SLEEP = 400
    AUTONOMOUS_WALK = 500
    SLEEP_TRANSITION = 600
    REMINDER = 700
    USER_SELECTED_DANCE = 800
    DRAGGING = 900
    PAUSED = 1000
    STOPPED = 1100


@dataclass(frozen=True, slots=True)
class ActionFrame:
    """One future image frame with normalized anchoring metadata."""

    asset_path: str
    duration_ms: int
    anchor_x: float
    anchor_y: float
    event: str | None = None

    def __post_init__(self) -> None:
        validate_relative_asset_path(self.asset_path)
        if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int) or self.duration_ms <= 0:
            raise ValueError("Action frame duration_ms must be a positive integer.")
        validate_normalized_coordinate(self.anchor_x, "anchor_x")
        validate_normalized_coordinate(self.anchor_y, "anchor_y")
        if self.event is not None:
            validate_stable_identifier(self.event, "event")


@dataclass(frozen=True, slots=True)
class ActionClip:
    """Validated runtime-ready metadata; Stage 10A creates no instances in the app."""

    action_id: str
    display_name: str
    category: ActionCategory
    frames: tuple[ActionFrame, ...]
    loop_mode: ActionLoopMode
    interrupt_policy: ActionInterruptPolicy
    priority: int
    default_loop_count: int
    source_asset_sha256: str
    canvas_width: int
    canvas_height: int
    feet_anchor_x: float
    feet_anchor_y: float
    tags: tuple[str, ...] = ()
    mirror_allowed: bool = False

    def __post_init__(self) -> None:
        validate_stable_identifier(self.action_id, "action_id")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("Action display_name must be nonempty.")
        if not isinstance(self.category, ActionCategory):
            raise ValueError("Action category must be an ActionCategory.")
        if not isinstance(self.frames, tuple) or any(not isinstance(frame, ActionFrame) for frame in self.frames):
            raise ValueError("Action frames must be a tuple of ActionFrame values.")
        visual_categories = {
            ActionCategory.OVERLAY,
            ActionCategory.FRAME_SEQUENCE,
            ActionCategory.USER_SELECTED,
        }
        if self.category in visual_categories and not self.frames:
            raise ValueError("Visual actions require at least one frame.")
        if not isinstance(self.loop_mode, ActionLoopMode):
            raise ValueError("Action loop_mode must be an ActionLoopMode.")
        if not isinstance(self.interrupt_policy, ActionInterruptPolicy):
            raise ValueError("Action interrupt_policy must be an ActionInterruptPolicy.")
        validate_action_priority(self.priority)
        validate_positive_integer(self.default_loop_count, "default_loop_count")
        validate_source_hash(self.source_asset_sha256)
        validate_canvas(self.canvas_width, self.canvas_height)
        validate_normalized_coordinate(self.feet_anchor_x, "feet_anchor_x")
        validate_normalized_coordinate(self.feet_anchor_y, "feet_anchor_y")
        if not isinstance(self.mirror_allowed, bool):
            raise ValueError("Action mirror_allowed must be boolean.")
        if not isinstance(self.tags, tuple):
            raise ValueError("Action tags must be a tuple.")
        for tag in self.tags:
            validate_stable_identifier(tag, "tag")
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("Action tags must be unique.")


def validate_stable_identifier(value: object, field_name: str) -> None:
    if not isinstance(value, str) or _STABLE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a stable lowercase English identifier.")


def validate_relative_asset_path(value: object) -> None:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise ValueError("Action frame asset_path must be a nonempty POSIX relative path.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.casefold() != ".png":
        raise ValueError("Action frame asset_path must be a safe relative PNG path.")


def validate_positive_integer(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"Action {field_name} must be a positive integer.")


def validate_action_priority(value: object) -> None:
    """Require every runtime priority to come from the centralized scale."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Action priority must use a defined ActionPriority value.")
    try:
        ActionPriority(value)
    except ValueError as error:
        raise ValueError("Action priority must use a defined ActionPriority value.") from error


def validate_normalized_coordinate(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"Action {field_name} must be between 0.0 and 1.0.")


def validate_source_hash(value: object) -> None:
    if value != APPROVED_SOURCE_ASSET_SHA256:
        raise ValueError("Action source_asset_sha256 must reference the approved Plan B runtime master.")


def validate_canvas(width: object, height: object) -> None:
    if (width, height) != APPROVED_CANVAS_SIZE:
        raise ValueError("Action canvas must use the approved shared 1024 x 1536 coordinate space.")
