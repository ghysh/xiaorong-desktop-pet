"""ActionRequest validation and immutability."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from desktop_pet.actions.model import ActionPriority
from desktop_pet.actions.request import ActionRequest, ActionRequestSource


def test_request_is_immutable_and_uses_central_priority() -> None:
    request = ActionRequest("blink_normal", ActionPriority.BLINK, ActionRequestSource.AUTONOMOUS, 2.5, "due")
    assert request.priority is ActionPriority.BLINK
    with pytest.raises(FrozenInstanceError):
        request.reason = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    (
        {"action_id": "Blink Normal"},
        {"priority": 200},
        {"source": object()},
        {"requested_at_seconds": -1.0},
        {"requested_at_seconds": float("nan")},
        {"reason": ""},
    ),
)
def test_invalid_request_fields_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "action_id": "blink_normal",
        "priority": ActionPriority.BLINK,
        "source": ActionRequestSource.AUTONOMOUS,
        "requested_at_seconds": 2.0,
        "reason": "scheduled",
    }
    values.update(changes)
    with pytest.raises(ValueError):
        ActionRequest(**values)  # type: ignore[arg-type]
