"""Protected resources, paths, timer budget, and scope regression checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from desktop_pet.dialogue.repository import DialogueRepository
from desktop_pet.paths import (
    ACTIONS_DIR,
    ANIMATIONS_DIR,
    CLICK_DIALOGUE_FILE,
    CLICK_REPLY_DIR,
    FULLBODY_RUNTIME_MASTER,
    PROJECT_ROOT,
)
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256, runtime_asset_sha256

EXPECTED_DIALOGUE_SHA256 = "8C5EE195826150158765E2799F5F271B8F22AA097CC1152C6E417E5305B28A5F"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_click_dialogue_paths_are_project_relative_and_frozen_ready() -> None:
    assert CLICK_REPLY_DIR == ACTIONS_DIR / "click_reply"
    assert CLICK_DIALOGUE_FILE == CLICK_REPLY_DIR / "dialogue.txt"
    assert CLICK_DIALOGUE_FILE == PROJECT_ROOT / "assets" / "actions" / "click_reply" / "dialogue.txt"
    assert CLICK_DIALOGUE_FILE.is_absolute()


def test_protected_master_and_dialogue_hashes_are_unchanged_after_load() -> None:
    before = _sha256(CLICK_DIALOGUE_FILE)
    before_mtime = CLICK_DIALOGUE_FILE.stat().st_mtime_ns
    repository = DialogueRepository(CLICK_DIALOGUE_FILE)

    assert repository.load()
    assert runtime_asset_sha256(FULLBODY_RUNTIME_MASTER) == EXPECTED_RUNTIME_ASSET_SHA256
    assert before == EXPECTED_DIALOGUE_SHA256
    assert _sha256(CLICK_DIALOGUE_FILE) == EXPECTED_DIALOGUE_SHA256
    assert CLICK_DIALOGUE_FILE.stat().st_mtime_ns == before_mtime


def test_stage_does_not_add_animation_frames_threads_or_network_code() -> None:
    dialogue_sources = list((PROJECT_ROOT / "src" / "desktop_pet" / "dialogue").glob("*.py"))
    dialogue_sources.append(PROJECT_ROOT / "src" / "desktop_pet" / "ui" / "dialogue_bubble.py")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in dialogue_sources)

    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    assert "threading" not in combined
    assert "requests" not in combined
    assert "time.sleep" not in combined
    assert "QThread" not in combined
