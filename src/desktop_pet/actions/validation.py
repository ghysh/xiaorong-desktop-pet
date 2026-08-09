"""Filesystem-independent and planning-tree validation helpers."""

from __future__ import annotations

from pathlib import Path

from desktop_pet.actions.manifest import ActionManifest, load_action_manifest
from desktop_pet.actions.model import APPROVED_SOURCE_ASSET_SHA256
from desktop_pet.actions.registry import ActionPlanRegistry, ActionRuntimeRegistry

PLANNED_MANIFEST_RELATIVE_PATHS = (
    "walk_left/manifest.json",
    "walk_right/manifest.json",
    "sit_cross_legged/manifest.json",
    "sleep_cross_legged/manifest.json",
    "wake_up/manifest.json",
    "dances/dance_wave_step/manifest.json",
    "dances/dance_side_sway/manifest.json",
    "dances/dance_spin/manifest.json",
)
BLINK_MANIFEST_RELATIVE_PATH = "blink/manifest.json"
ALL_ACTION_MANIFEST_RELATIVE_PATHS = (BLINK_MANIFEST_RELATIVE_PATH, *PLANNED_MANIFEST_RELATIVE_PATHS)
FORBIDDEN_ACTION_IMAGE_SUFFIXES = frozenset({".apng", ".gif", ".jpeg", ".jpg", ".png", ".webp"})


def load_planned_registry(actions_root: Path | str) -> ActionPlanRegistry:
    root = Path(actions_root)
    manifests = [load_action_manifest(root / relative_path) for relative_path in PLANNED_MANIFEST_RELATIVE_PATHS]
    registry = ActionPlanRegistry(manifests)
    if len(registry) != len(PLANNED_MANIFEST_RELATIVE_PATHS):
        raise ValueError("Not all required Stage 10A manifests were registered.")
    return registry


def validate_planned_manifest(manifest: ActionManifest) -> tuple[str, ...]:
    errors: list[str] = []
    if manifest.status != "planned":
        errors.append("status must be planned")
    if manifest.runtime_enabled:
        errors.append("runtime_enabled must be false")
    if manifest.assets_complete:
        errors.append("assets_complete must be false")
    if manifest.frames:
        errors.append("Stage 10A planned manifests must not reference frames")
    if manifest.mirror_allowed:
        errors.append("mirror_allowed must remain false until explicit user approval")
    if manifest.source_asset_sha256 != APPROVED_SOURCE_ASSET_SHA256:
        errors.append("source hash must reference the approved Plan B master")
    return tuple(errors)


def find_action_images(actions_root: Path | str) -> tuple[Path, ...]:
    root = Path(actions_root)
    return tuple(
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.casefold() in FORBIDDEN_ACTION_IMAGE_SUFFIXES
    )


def load_runtime_registry(actions_root: Path | str, cache: object) -> ActionRuntimeRegistry:
    """Load only explicitly shipped runtime manifests; planning files are development-only."""
    root = Path(actions_root)
    registry = ActionRuntimeRegistry()
    for relative_path in (BLINK_MANIFEST_RELATIVE_PATH,):
        manifest_path = root / relative_path
        manifest = load_action_manifest(manifest_path)
        registry.register_manifest(manifest, manifest_path, cache)  # type: ignore[arg-type]
    return registry
