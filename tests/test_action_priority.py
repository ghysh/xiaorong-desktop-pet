"""Central future action priority and unchanged current state tests."""

from __future__ import annotations

import ast

from desktop_pet.actions.model import ActionPriority
from desktop_pet.behavior.state import PetState
from desktop_pet.paths import PROJECT_ROOT


def test_action_priority_has_the_approved_total_order() -> None:
    descending = tuple(item.name for item in sorted(ActionPriority, reverse=True))
    assert descending == (
        "STOPPED",
        "PAUSED",
        "DRAGGING",
        "USER_SELECTED_DANCE",
        "REMINDER",
        "SLEEP_TRANSITION",
        "AUTONOMOUS_WALK",
        "AUTONOMOUS_SLEEP",
        "CLICK_REACTION",
        "BLINK",
        "IDLE",
    )
    assert ActionPriority.DRAGGING > ActionPriority.USER_SELECTED_DANCE > ActionPriority.REMINDER
    assert ActionPriority.USER_SELECTED_DANCE > ActionPriority.AUTONOMOUS_WALK
    assert ActionPriority.CLICK_REACTION > ActionPriority.BLINK > ActionPriority.IDLE


def test_stage_10a_does_not_change_pet_states_or_add_a_runtime_timer() -> None:
    assert tuple(state.name for state in PetState) == (
        "STARTING",
        "IDLE_CALM",
        "IDLE_QUIET",
        "IDLE_SWAY",
        "RESTING",
        "DRAGGING",
        "SETTLING",
        "CLICK_REACTION",
        "PAUSED",
        "STOPPED",
    )
    animation_source = (PROJECT_ROOT / "src/desktop_pet/animation/controller.py").read_text(encoding="utf-8")
    assert animation_source.count("QTimer(self)") == 1
    action_timer_calls: list[ast.Call] = []
    for path in (PROJECT_ROOT / "src/desktop_pet/actions").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        action_timer_calls.extend(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "QTimer"
        )
    assert action_timer_calls == []
