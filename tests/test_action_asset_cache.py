"""Ready-frame validation, source reuse, size caching, and explicit clearing."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QSize

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.actions.cache import ActionAssetCache
from desktop_pet.actions.manifest import load_action_manifest
from desktop_pet.actions.model import ActionFrame
from desktop_pet.actions.registry import ActionRuntimeRegistry
from desktop_pet.app import create_application
from desktop_pet.paths import ACTIONS_DIR, BLINK_MANIFEST


def test_ready_blink_preloads_four_unique_sources_and_reuses_size_pixmaps() -> None:
    create_application(["pytest-action-cache"])
    cache = ActionAssetCache(ACTIONS_DIR)
    registry = ActionRuntimeRegistry()
    manifest = load_action_manifest(BLINK_MANIFEST)
    registry.register_manifest(manifest, BLINK_MANIFEST, cache)
    assert registry.action_ids == ("blink_normal",)
    assert cache.source_load_count == 4
    clip = registry.get("blink_normal")
    path = clip.frames[0].asset_path
    first = cache.pixmap(clip.action_id, path, QSize(280, 420))
    second = cache.pixmap(clip.action_id, path, QSize(280, 420))
    assert first.cacheKey() == second.cacheKey()
    assert cache.scale_count == 1
    cache.pixmap(clip.action_id, path, (320, 480))
    assert cache.scale_count == 2
    assert cache.source_load_count == 4


def test_clear_action_and_clear_all_remove_cached_entries() -> None:
    create_application(["pytest-action-cache-clear"])
    cache = ActionAssetCache(ACTIONS_DIR)
    manifest = load_action_manifest(BLINK_MANIFEST)
    ActionRuntimeRegistry().register_manifest(manifest, BLINK_MANIFEST, cache)
    cache.clear_action("blink_normal")
    with pytest.raises(KeyError):
        cache.source_record("blink_normal", "frames/blink_open.png")
    cache.clear_all()
    assert cache.source_memory_estimate_bytes == 0


@pytest.mark.parametrize(("mode", "size"), (("RGB", (1024, 1536)), ("RGBA", (100, 100))))
def test_invalid_mode_or_canvas_is_rejected(tmp_path: Path, mode: str, size: tuple[int, int]) -> None:
    create_application(["pytest-action-cache-invalid"])
    action_dir = tmp_path / "action"
    frames_dir = action_dir / "frames"
    frames_dir.mkdir(parents=True)
    Image.new(mode, size, "white").save(frames_dir / "bad.png")
    manifest = load_action_manifest(BLINK_MANIFEST)
    bad = replace(manifest, frames=(ActionFrame("frames/bad.png", 35, 0.5, 0.9733),))
    with pytest.raises(ValueError, match="1024x1536 RGBA"):
        ActionRuntimeRegistry().register_manifest(bad, action_dir / "manifest.json", ActionAssetCache(tmp_path))


def test_missing_frame_is_rejected_before_runtime_registration(tmp_path: Path) -> None:
    create_application(["pytest-action-cache-missing"])
    action_dir = tmp_path / "action"
    action_dir.mkdir()
    manifest = load_action_manifest(BLINK_MANIFEST)
    missing = replace(manifest, frames=(ActionFrame("frames/missing.png", 35, 0.5, 0.9733),))
    with pytest.raises(FileNotFoundError, match="missing"):
        ActionRuntimeRegistry().register_manifest(missing, action_dir / "manifest.json", ActionAssetCache(tmp_path))
