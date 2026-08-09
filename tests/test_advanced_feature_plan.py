"""Stage 10A planning remains intact while Stage 10B activates only blinking."""

from __future__ import annotations

import hashlib

from desktop_pet.paths import ANIMATIONS_DIR, FULLBODY_RUNTIME_MASTER, PROJECT_ROOT
from desktop_pet.settings.model import UserSettings
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256


def _sha256() -> str:
    return hashlib.sha256(FULLBODY_RUNTIME_MASTER.read_bytes()).hexdigest().upper()


def test_required_advanced_interaction_documents_exist() -> None:
    required = (
        "docs/advanced_interaction_architecture.md",
        "docs/action_manifest_schema.md",
        "docs/action_specs/blink_spec.md",
        "docs/action_specs/walking_spec.md",
        "docs/action_specs/cross_legged_sleep_spec.md",
        "docs/reminder_system_spec.md",
        "docs/dance_action_catalog.md",
        "docs/autonomous_behavior_spec.md",
        "docs/advanced_interaction_risk_register.md",
    )
    assert all((PROJECT_ROOT / path).is_file() for path in required)
    combined = "\n".join((PROJECT_ROOT / path).read_text(encoding="utf-8") for path in required)
    for concept in ("ActionClip", "ActionPlayer", "WindowMotionController", "ReminderController"):
        assert concept in combined


def test_stage_10a_keeps_assets_settings_and_runtime_features_unchanged() -> None:
    assert _sha256() == EXPECTED_RUNTIME_ASSET_SHA256
    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    assert set(UserSettings.__dataclass_fields__) == {
        "schema_version",
        "size",
        "always_on_top",
        "animation_enabled",
        "behavior_enabled",
        "click_reaction_enabled",
        "remember_position",
        "window_x",
        "window_y",
        "screen_name",
    }
    app_source = (PROJECT_ROOT / "src/desktop_pet/app.py").read_text(encoding="utf-8")
    action_registry_source = (PROJECT_ROOT / "src/desktop_pet/ui/action_registry.py").read_text(encoding="utf-8")
    assert "WindowMotionController" not in app_source
    assert "ReminderController" not in app_source
    assert "dance_wave_step" not in action_registry_source
    assert "WATER_REMINDER" not in app_source


def test_readme_and_plan_keep_the_full_10a_to_10g_roadmap() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    plan = (PROJECT_ROOT / "docs/development_plan.md").read_text(encoding="utf-8")
    assert "10A" in readme and "10B" in readme
    for stage in ("10A", "10B", "10C", "10D", "10E", "10F", "10G"):
        assert stage in plan
