"""Timer-free arbitration between requests and the current action clip."""

from __future__ import annotations

from enum import Enum, auto

from desktop_pet.actions.model import ActionClip, ActionInterruptPolicy, ActionPriority
from desktop_pet.actions.request import ActionRequest, ActionRequestSource
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState


class ArbitrationDecision(Enum):
    START_IMMEDIATELY = auto()
    QUEUE_AFTER_FRAME = auto()
    QUEUE_AFTER_CYCLE = auto()
    REJECT = auto()


class ActionArbiter:
    """Apply the centralized priority scale without playing frames or changing PetState."""

    def decide(
        self,
        request: ActionRequest,
        *,
        state: PetState,
        current_clip: ActionClip | None,
        pending_action_id: str | None = None,
    ) -> ArbitrationDecision:
        if not isinstance(request, ActionRequest) or not isinstance(state, PetState):
            raise ValueError("Action arbitration requires a valid request and PetState.")
        if request.action_id == pending_action_id:
            return ArbitrationDecision.REJECT
        if state is PetState.STOPPED:
            return ArbitrationDecision.REJECT
        if request.source is ActionRequestSource.AUTONOMOUS and state not in AUTOMATIC_STATES:
            return ArbitrationDecision.REJECT
        if current_clip is None:
            return ArbitrationDecision.START_IMMEDIATELY
        if request.action_id == current_clip.action_id:
            return ArbitrationDecision.REJECT
        current_priority = ActionPriority(current_clip.priority)
        if request.priority <= current_priority:
            return ArbitrationDecision.REJECT
        if current_clip.interrupt_policy is ActionInterruptPolicy.IMMEDIATE:
            return ArbitrationDecision.START_IMMEDIATELY
        if current_clip.interrupt_policy is ActionInterruptPolicy.FINISH_FRAME:
            return ArbitrationDecision.QUEUE_AFTER_FRAME
        if current_clip.interrupt_policy is ActionInterruptPolicy.FINISH_CYCLE:
            return ArbitrationDecision.QUEUE_AFTER_CYCLE
        if request.priority in {ActionPriority.STOPPED, ActionPriority.DRAGGING}:
            return ArbitrationDecision.START_IMMEDIATELY
        return ArbitrationDecision.REJECT
