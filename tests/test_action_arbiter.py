"""Action priority and interrupt-boundary arbitration."""

from __future__ import annotations

import pytest

from desktop_pet.actions.arbiter import ActionArbiter, ArbitrationDecision
from desktop_pet.actions.model import ActionInterruptPolicy, ActionPriority
from desktop_pet.actions.request import ActionRequest, ActionRequestSource
from desktop_pet.behavior.state import PetState
from tests.action_test_helpers import make_clip


def request(priority: ActionPriority = ActionPriority.BLINK, action_id: str = "blink_normal") -> ActionRequest:
    return ActionRequest(action_id, priority, ActionRequestSource.AUTONOMOUS, 5.0, "test")


def test_idle_starts_blink_but_all_override_states_reject_it() -> None:
    arbiter = ActionArbiter()
    assert (
        arbiter.decide(request(), state=PetState.IDLE_CALM, current_clip=None)
        is ArbitrationDecision.START_IMMEDIATELY
    )
    for state in (
        PetState.STARTING,
        PetState.CLICK_REACTION,
        PetState.DRAGGING,
        PetState.SETTLING,
        PetState.PAUSED,
        PetState.STOPPED,
    ):
        assert arbiter.decide(request(), state=state, current_clip=None) is ArbitrationDecision.REJECT


@pytest.mark.parametrize(
    ("policy", "expected"),
    (
        (ActionInterruptPolicy.IMMEDIATE, ArbitrationDecision.START_IMMEDIATELY),
        (ActionInterruptPolicy.FINISH_FRAME, ArbitrationDecision.QUEUE_AFTER_FRAME),
        (ActionInterruptPolicy.FINISH_CYCLE, ArbitrationDecision.QUEUE_AFTER_CYCLE),
        (ActionInterruptPolicy.NOT_INTERRUPTIBLE, ArbitrationDecision.REJECT),
    ),
)
def test_higher_priority_request_respects_clip_policy(
    policy: ActionInterruptPolicy,
    expected: ArbitrationDecision,
) -> None:
    current = make_clip(interrupt_policy=policy, priority=ActionPriority.BLINK)
    higher = ActionRequest(
        "user_action",
        ActionPriority.USER_SELECTED_DANCE,
        ActionRequestSource.USER,
        5.0,
        "user selected",
    )
    assert ActionArbiter().decide(higher, state=PetState.IDLE_CALM, current_clip=current) is expected


def test_duplicate_pending_and_lower_priority_requests_are_rejected() -> None:
    current = make_clip(priority=ActionPriority.CLICK_REACTION)
    arbiter = ActionArbiter()
    assert arbiter.decide(request(), state=PetState.IDLE_CALM, current_clip=current) is ArbitrationDecision.REJECT
    assert (
        arbiter.decide(request(), state=PetState.IDLE_CALM, current_clip=None, pending_action_id="blink_normal")
        is ArbitrationDecision.REJECT
    )
