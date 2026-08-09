"""Immutable action requests shared by autonomous and lifecycle producers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from math import isfinite

from desktop_pet.actions.model import ActionPriority, validate_stable_identifier


class ActionRequestSource(Enum):
    SYSTEM = auto()
    AUTONOMOUS = auto()
    USER = auto()
    REMINDER = auto()
    LIFECYCLE = auto()


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    priority: ActionPriority
    source: ActionRequestSource
    requested_at_seconds: float
    reason: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.action_id, "action_id")
        if not isinstance(self.priority, ActionPriority):
            raise ValueError("ActionRequest priority must be an ActionPriority value.")
        if not isinstance(self.source, ActionRequestSource):
            raise ValueError("ActionRequest source must be an ActionRequestSource value.")
        if not isfinite(self.requested_at_seconds) or self.requested_at_seconds < 0:
            raise ValueError("ActionRequest time must be finite and nonnegative.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("ActionRequest reason must be nonempty.")
