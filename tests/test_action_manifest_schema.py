"""Machine-readable schema and all disabled planned-manifest tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desktop_pet.actions.model import APPROVED_SOURCE_ASSET_SHA256
from desktop_pet.actions.validation import (
    PLANNED_MANIFEST_RELATIVE_PATHS,
    find_action_images,
    load_planned_registry,
    validate_planned_manifest,
)
from desktop_pet.paths import PROJECT_ROOT

ACTIONS_ROOT = PROJECT_ROOT / "assets" / "actions"


def test_action_json_schema_locks_stage_10a_safety_fields() -> None:
    schema = json.loads((ACTIONS_ROOT / "schema/action_clip.schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]
    assert schema["$schema"].endswith("2020-12/schema")
    assert properties["status"]["enum"] == ["planned", "draft", "ready", "disabled"]
    assert properties["runtime_enabled"] == {"type": "boolean"}
    assert properties["assets_complete"] == {"type": "boolean"}
    assert properties["mirror_allowed"] == {"const": False}
    assert properties["frames"]["items"]["properties"]["duration_ms"]["minimum"] == 1
    assert any(rule["if"]["properties"]["status"] == {"const": "ready"} for rule in schema["allOf"])
    assert properties["source_asset_sha256"]["const"] == APPROVED_SOURCE_ASSET_SHA256


def test_every_planned_manifest_parses_and_remains_non_runnable() -> None:
    registry = load_planned_registry(ACTIONS_ROOT)
    assert len(registry) == len(PLANNED_MANIFEST_RELATIVE_PATHS) == 8
    for manifest in registry:
        assert validate_planned_manifest(manifest) == ()
        assert manifest.status == "planned"
        assert manifest.runtime_enabled is False
        assert manifest.assets_complete is False
        assert manifest.mirror_allowed is False
        assert manifest.frames == ()
        assert manifest.source_asset_sha256 == APPROVED_SOURCE_ASSET_SHA256
        with pytest.raises(ValueError, match="cannot become"):
            manifest.to_clip()


def test_action_asset_tree_contains_only_ready_runtime_images() -> None:
    expected_images = {"dialogue_bubble_frame.png"}
    for relative_manifest in ("blink/manifest.json", "drowsy_sleep/manifest.json"):
        payload = json.loads((ACTIONS_ROOT / relative_manifest).read_text(encoding="utf-8"))
        expected_images.update(Path(frame["asset_path"]).name for frame in payload["frames"])
    expected_images.add("sleep_nod.png")  # Retained legacy endpoint; no longer packaged or played.
    assert {path.name for path in find_action_images(ACTIONS_ROOT)} == expected_images
    for relative_path in PLANNED_MANIFEST_RELATIVE_PATHS:
        payload = json.loads((ACTIONS_ROOT / relative_path).read_text(encoding="utf-8"))
        assert payload["frames"] == []
        assert not payload["runtime_enabled"]
