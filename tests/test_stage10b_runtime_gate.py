"""Only blink_normal is ready; no Stage 10C+ feature leaks into runtime."""

from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest
from PySide6.QtCore import QTimer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.actions.cache import ActionAssetCache
from desktop_pet.actions.manifest import load_action_manifest
from desktop_pet.actions.registry import ActionRuntimeRegistry
from desktop_pet.app import create_application
from desktop_pet.paths import ACTIONS_DIR, ANIMATIONS_DIR, BLINK_MANIFEST, PROJECT_ROOT
from desktop_pet.settings.model import UserSettings
from desktop_pet.ui.pet_window import PetWindow


def test_only_blink_is_ready_and_other_eight_actions_remain_planned() -> None:
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in ACTIONS_DIR.rglob("manifest.json")]
    ready = [item for item in manifests if item["status"] == "ready"]
    planned = [item for item in manifests if item["status"] == "planned"]
    assert [item["action_id"] for item in ready] == ["blink_normal"]
    assert len(planned) == 8
    assert all(not item["runtime_enabled"] and not item["assets_complete"] and not item["frames"] for item in planned)


def test_runtime_registers_only_blink_and_still_has_one_high_frequency_timer() -> None:
    create_application(["pytest-stage10b-gate"])
    window = PetWindow()
    assert window.runtime_action_registry.action_ids == ("blink_normal",)
    assert len(window.findChildren(QTimer)) == 1
    action_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "src/desktop_pet/actions").glob("*.py")
    )
    assert "from PySide6.QtCore import QTimer" not in action_sources
    assert "QTimer(" not in action_sources
    assert "Thread" not in action_sources
    window.close()


@pytest.mark.parametrize(
    "manifest",
    (
        lambda ready: replace(ready, status="planned", runtime_enabled=False, assets_complete=False, frames=()),
        lambda ready: replace(ready, status="draft", runtime_enabled=False, assets_complete=False),
        lambda ready: replace(ready, status="ready", runtime_enabled=True, assets_complete=False),
    ),
)
def test_runtime_registry_rejects_every_incomplete_gate_combination(manifest: object) -> None:
    create_application(["pytest-stage10b-incomplete-gate"])
    ready = load_action_manifest(BLINK_MANIFEST)
    incomplete = manifest(ready)  # type: ignore[operator]
    with pytest.raises(ValueError, match="ready, enabled, and asset-complete"):
        ActionRuntimeRegistry().register_manifest(incomplete, BLINK_MANIFEST, ActionAssetCache(ACTIONS_DIR))


def test_manifest_rejects_unapproved_source_hash() -> None:
    ready = load_action_manifest(BLINK_MANIFEST)
    with pytest.raises(ValueError, match="Plan B"):
        replace(ready, source_asset_sha256="0" * 64)


def test_stage10b_does_not_add_settings_motion_reminders_dance_or_packaging() -> None:
    assert set(UserSettings.__dataclass_fields__) == {
        "schema_version", "size", "always_on_top", "animation_enabled", "behavior_enabled",
        "click_reaction_enabled", "remember_position", "window_x", "window_y", "screen_name",
    }
    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "src/desktop_pet").rglob("*.py")
    )
    assert "WindowMotionController" not in runtime
    assert "ReminderController" not in runtime
    ui_actions = (PROJECT_ROOT / "src/desktop_pet/ui/action_registry.py").read_text(encoding="utf-8")
    assert "dance_wave_step" not in ui_actions
