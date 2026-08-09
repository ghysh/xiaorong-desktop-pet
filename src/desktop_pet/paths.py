"""Central source and frozen runtime paths with no development-machine dependency."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent


def is_frozen() -> bool:
    """Return whether the interpreter is a PyInstaller-frozen application."""
    return bool(getattr(sys, "frozen", False))


def runtime_base_dir() -> Path:
    """Return the bundled extraction root when frozen, otherwise the project root."""
    if is_frozen():
        bundle_root = getattr(sys, "_MEIPASS", None)
        if not bundle_root:
            raise RuntimeError("Frozen runtime is missing the PyInstaller bundle directory.")
        return Path(bundle_root).resolve()
    return PROJECT_ROOT


RUNTIME_BASE_DIR = runtime_base_dir()
ASSETS_DIR = RUNTIME_BASE_DIR / "assets"
ORIGINAL_ASSETS_DIR = ASSETS_DIR / "original"
PROCESSED_ASSETS_DIR = ASSETS_DIR / "processed"
ANIMATIONS_DIR = ASSETS_DIR / "animations"
ANALYSIS_DIR = ASSETS_DIR / "analysis"
ANIMATION_ANALYSIS_DIR = ANALYSIS_DIR / "animation"
BEHAVIOR_ANALYSIS_DIR = ANALYSIS_DIR / "behavior"
INTERACTION_ANALYSIS_DIR = ANALYSIS_DIR / "interaction"
BLINK_ANALYSIS_DIR = ANALYSIS_DIR / "blink"
ANALYSIS_PREVIEWS_DIR = ANALYSIS_DIR / "previews"
ANALYSIS_REPORTS_DIR = ANALYSIS_DIR / "reports"

ORIGINAL_CHARACTER_IMAGE = ORIGINAL_ASSETS_DIR / "character_original.png"

BASE_ASSETS_DIR = PROCESSED_ASSETS_DIR / "base"
MASKS_ASSETS_DIR = PROCESSED_ASSETS_DIR / "masks"
PROCESSED_PREVIEWS_DIR = PROCESSED_ASSETS_DIR / "previews"
PROCESSED_REPORTS_DIR = PROCESSED_ASSETS_DIR / "reports"
FULLBODY_ASSETS_DIR = ASSETS_DIR / "fullbody"
FULLBODY_CONCEPTS_DIR = FULLBODY_ASSETS_DIR / "concepts"
FULLBODY_REPORTS_DIR = FULLBODY_ASSETS_DIR / "reports"
FULLBODY_INTERMEDIATE_DIR = FULLBODY_ASSETS_DIR / "intermediate"
FULLBODY_SELECTED_DIR = FULLBODY_ASSETS_DIR / "selected"
FULLBODY_FINAL_DIR = FULLBODY_ASSETS_DIR / "final"
FULLBODY_PREVIEWS_DIR = FULLBODY_ASSETS_DIR / "previews"
FULLBODY_DIAGNOSTICS_DIR = FULLBODY_ASSETS_DIR / "diagnostics"
ACTIONS_DIR = ASSETS_DIR / "actions"
ICONS_DIR = ASSETS_DIR / "icons"
APPLICATION_ICON = ICONS_DIR / "character_original.ico"
BLINK_ACTION_DIR = ACTIONS_DIR / "blink"
BLINK_FRAMES_DIR = BLINK_ACTION_DIR / "frames"
BLINK_PREVIEWS_DIR = BLINK_ACTION_DIR / "previews"
BLINK_DIAGNOSTICS_DIR = BLINK_ACTION_DIR / "diagnostics"
BLINK_MANIFEST = BLINK_ACTION_DIR / "manifest.json"
CLICK_REPLY_DIR = ACTIONS_DIR / "click_reply"
CLICK_DIALOGUE_FILE = CLICK_REPLY_DIR / "dialogue.txt"
DIALOGUE_ANALYSIS_DIR = ANALYSIS_DIR / "dialogue"

# Historical source-only paths are retained for development tools, never packaged.
CHARACTER_CUTOUT_IMAGE = BASE_ASSETS_DIR / "character_cutout_rgba.png"
CHARACTER_RUNTIME_MASTER = BASE_ASSETS_DIR / "character_runtime_master.png"
FULLBODY_SELECTED_B_SOURCE = FULLBODY_SELECTED_DIR / "fullbody_selected_b_source.png"
FULLBODY_RUNTIME_MASTER = FULLBODY_FINAL_DIR / "fullbody_runtime_master.png"
FULLBODY_FINAL_MANIFEST = FULLBODY_REPORTS_DIR / "fullbody_final_asset_manifest.json"
