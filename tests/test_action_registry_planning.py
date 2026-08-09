"""Planning registry must never silently activate placeholder actions."""

from __future__ import annotations

from dataclasses import replace

import pytest

from desktop_pet.actions.manifest import load_action_manifest
from desktop_pet.actions.model import ActionFrame
from desktop_pet.actions.registry import ActionPlanRegistry
from desktop_pet.actions.validation import load_planned_registry
from desktop_pet.paths import PROJECT_ROOT

ACTIONS_ROOT = PROJECT_ROOT / "assets" / "actions"


def test_planning_registry_has_unique_stable_ids_and_lookup() -> None:
    registry = load_planned_registry(ACTIONS_ROOT)
    assert registry.action_ids == tuple(sorted(registry.action_ids))
    assert registry.get("walk_left_loop").display_name == "向左行走循环"
    with pytest.raises(KeyError, match="Unknown"):
        registry.get("not_planned")


def test_planning_registry_rejects_duplicates_and_ready_actions() -> None:
    planned = load_action_manifest(ACTIONS_ROOT / "walk_left/manifest.json")
    registry = ActionPlanRegistry([planned])
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register(planned)
    future_frame = ActionFrame("frames/blink_0001.png", 35, 0.5, 0.9733)
    ready = replace(
        planned,
        status="ready",
        runtime_enabled=True,
        assets_complete=True,
        frames=(future_frame,),
    )
    assert ready.to_clip().action_id == "walk_left_loop"
    with pytest.raises(ValueError, match="only disabled"):
        registry.register(ready)


def test_current_runtime_imports_only_the_stage10b_action_runtime() -> None:
    app_source = (PROJECT_ROOT / "src/desktop_pet/app.py").read_text(encoding="utf-8")
    window_source = (PROJECT_ROOT / "src/desktop_pet/ui/pet_window.py").read_text(encoding="utf-8")
    assert "desktop_pet.actions" not in app_source
    assert "desktop_pet.actions.validation" in window_source
    assert "ActionPlayer" not in app_source
    assert "ActionPlayer" not in window_source
