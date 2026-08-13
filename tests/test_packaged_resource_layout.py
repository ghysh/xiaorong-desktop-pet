"""Spec data-minimization and generated icon checks."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from desktop_pet.paths import PROJECT_ROOT


def test_spec_packages_only_the_proven_runtime_resources() -> None:
    text = (PROJECT_ROOT / "packaging/windows/xiaorong.spec").read_text(encoding="utf-8")
    for required in (
        "fullbody_runtime_master.png",
        "dialogue.txt",
        "dialogue_bubble_frame.png",
        "character_original.ico",
        '"blink" / "manifest.json"',
        "blink_open.png",
        "blink_half_closed.png",
        "blink_closed.png",
        "blink_half_open.png",
        'DROWSY_SLEEP_MANIFEST = DROWSY_SLEEP_DIR / "manifest.json"',
        "DROWSY_SLEEP_FRAME_PATHS",
        'frame["asset_path"]',
    ):
        assert required in text
    sleep_manifest = json.loads(
        (PROJECT_ROOT / "assets/actions/drowsy_sleep/manifest.json").read_text(encoding="utf-8")
    )
    packaged_frame_names = {Path(frame["asset_path"]).name for frame in sleep_manifest["frames"]}
    assert len(packaged_frame_names) == 74
    assert {
        "sit_down_knees_50.png",
        "sit_down_knees.png",
        "sit_down_lower_50.png",
        "sit_down_lower_to_fold.png",
        "sleep_settle_final.png",
        "sleep_nod_local_micro.png",
        "sleep_nod_local_very_light.png",
        "sleep_nod_local_light.png",
        "sleep_nod_local_light_plus.png",
        "sleep_nod_local_light_mid.png",
        "sleep_nod_local_mid.png",
        "sleep_nod_local_mid_deep.png",
        "sleep_nod_local_deep.png",
        "sleep_nod_local_deep_peak.png",
        "sleep_nod_local_peak.png",
        "wake_eyes_10.png",
        "wake_eyes_half_clean.png",
        "wake_head_lift_mid.png",
        "rise_prepare.png",
        "rise_support_to_shift.png",
        "rise_weight_shift.png",
        "rise_unfold_mid.png",
        "rise_crouch_low.png",
        "rise_half_crouch.png",
        "rise_mid.png",
        "rise_near_stand.png",
        "stretch_local_prepare.png",
        "stretch_local_arms_low.png",
        "stretch_local_waist.png",
        "stretch_local_chest.png",
        "stretch_local_elbow_mid.png",
        "stretch_local_chest_to_shoulders.png",
        "stretch_local_shoulders.png",
        "stretch_local_upper.png",
        "stretch_local_open_high.png",
        "stretch_local_compact_peak.png",
        "stretch_local_end.png",
        "yawn_transition.png",
        "yawn_mouth_quarter.png",
        "yawn_mouth_three_quarter.png",
        "yawn_to_rub.png",
        "rub_eye_touch.png",
        "rub_eye_press_mid.png",
        "rub_hand_near_eye.png",
        "rub_hand_lowered.png",
        "rub_hand_down.png",
    }.issubset(packaged_frame_names)
    for forbidden in (
        "ori_figure.png",
        "assets/original",
        "assets/animations",
        "diagnostics",
        "walk_left/manifest.json",
        "dance_wave_step",
    ):
        assert forbidden not in text
    for excluded in ("PyInstaller", "cv2", "matplotlib", "numpy", "pytest", "ruff"):
        assert f'"{excluded}"' in text
    assert "upx=False" in text
    assert '"console": False' in text
    assert "XIAORONG_BUILD_MODE" in text
    assert '"name": "小融"' in text


def test_application_icon_has_all_required_layers() -> None:
    path = PROJECT_ROOT / "assets/icons/character_original.ico"
    with Image.open(path) as icon:
        assert icon.format == "ICO"
        assert (256, 256) in icon.ico.sizes()
