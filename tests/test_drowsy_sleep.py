"""Autonomous drowsy sleep scheduling, manifest flow, and asset integrity."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image
from scripts.prepare_drowsy_sleep_frames import (
    _alpha_metrics,
    _stable_region_width,
    _tone_metrics,
    _validate_stable_region,
    _validate_tone_pair,
)

from desktop_pet.actions.manifest import load_action_manifest
from desktop_pet.actions.model import ActionCategory, ActionPriority
from desktop_pet.actions.sleep import DROWSY_SLEEP_ACTION_ID, DrowsySleepController
from desktop_pet.behavior.state import PetState
from desktop_pet.config import DrowsySleepConfig
from desktop_pet.paths import DROWSY_SLEEP_MANIFEST, FULLBODY_RUNTIME_MASTER
from desktop_pet.ui.pet_window import (
    REPLACEMENT_CROSSFADE_DURATION_MS,
    REPLACEMENT_CROSSFADE_EVENTS,
)

NOD_FRAME_NAMES = (
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
)
NOD_EVENTS = tuple(
    f"sleep_bubble_nod_{Path(name).stem.removeprefix('sleep_nod_')}"
    for name in NOD_FRAME_NAMES
)
STRETCH_FRAME_NAMES = (
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
)
STRETCH_EVENT_ASSETS = (
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
    "stretch_local_open_high.png",
    "stretch_local_upper.png",
    "stretch_local_shoulders.png",
    "stretch_local_chest_to_shoulders.png",
    "stretch_local_elbow_mid.png",
    "stretch_local_chest.png",
    "stretch_local_waist.png",
    "stretch_local_arms_low.png",
    "stretch_local_prepare.png",
    "stretch_local_end.png",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_timer_free_scheduler_requests_only_when_due_in_an_automatic_state() -> None:
    controller = DrowsySleepController(
        DrowsySleepConfig(
            startup_minimum_seconds=10.0,
            startup_maximum_seconds=10.0,
            minimum_interval_seconds=20.0,
            maximum_interval_seconds=20.0,
            seed=7,
        )
    )
    assert controller.update(0.0, PetState.IDLE_CALM, None) is None
    assert controller.update(9.999, PetState.IDLE_CALM, None) is None
    assert controller.update(10.0, PetState.DRAGGING, None) is None
    request = controller.update(10.0, PetState.RESTING, None)
    assert request is not None
    assert request.action_id == DROWSY_SLEEP_ACTION_ID
    assert request.priority is ActionPriority.AUTONOMOUS_SLEEP
    controller.resolve_request(True, 10.0)
    assert controller.active
    controller.on_clip_finished(DROWSY_SLEEP_ACTION_ID, 25.0)
    assert not controller.active
    assert controller.next_due_seconds == 45.0


def test_bubble_motion_is_slow_bounded_and_visible_only_during_sleep_events() -> None:
    config = DrowsySleepConfig(seed=3)
    controller = DrowsySleepController(config)
    controller.on_clip_started(DROWSY_SLEEP_ACTION_ID)
    states = [controller.bubble_state(value, "sleep_bubble") for value in (0.0, 0.5, 1.0, 2.0, 4.0)]
    assert all(state.visible for state in states)
    assert all(abs(state.rotation_degrees) <= config.bubble_rotation_degrees for state in states)
    assert all(
        1.0 - config.bubble_scale_amplitude <= state.scale <= 1.0 + config.bubble_scale_amplitude
        for state in states
    )
    assert controller.bubble_state(1.0, "wake_up").visible is False
    nod_states = tuple(controller.bubble_state(1.0, event) for event in NOD_EVENTS)
    assert tuple(state.anchor_y for state in nod_states) == tuple(
        sorted(state.anchor_y for state in nod_states)
    )
    assert nod_states[-1].anchor_y - states[0].anchor_y >= 0.035
    assert tuple(state.anchor_x for state in nod_states) == tuple(
        sorted((state.anchor_x for state in nod_states), reverse=True)
    )
    shrinking = (
        controller.bubble_state(1.0, "sleep_bubble_shrink_start"),
        controller.bubble_state(1.0, "sleep_bubble_shrink_large"),
        controller.bubble_state(1.0, "sleep_bubble_shrink_small"),
    )
    assert all(state.visible for state in shrinking)
    assert tuple(state.scale for state in shrinking) == tuple(
        sorted((state.scale for state in shrinking), reverse=True)
    )
    assert tuple(state.opacity for state in shrinking) == tuple(
        sorted((state.opacity for state in shrinking), reverse=True)
    )


def test_ready_manifest_has_the_complete_ordered_sleep_and_wake_flow() -> None:
    manifest = load_action_manifest(DROWSY_SLEEP_MANIFEST)
    assert manifest.action_id == DROWSY_SLEEP_ACTION_ID
    assert manifest.category is ActionCategory.FRAME_SEQUENCE
    assert manifest.runtime_enabled and manifest.assets_complete
    events = tuple(frame.event for frame in manifest.frames)
    ordered_markers = (
        "sleep_prepare",
        "sit_down_start",
        "sit_down_knees",
        "sit_down_lower_50",
        "sit_down_lower",
        "sit_down_lower_to_fold",
        "sit_down_fold_75",
        "sit_down_fold",
        "sit_down_fold_to_support",
        "sit_awake",
        "sleep_eyes_quarter",
        "sleep_eyes_half",
        "sleep_eyes_closed",
        "sleep_head_droop",
        "sleep_settle_final",
        "sleep_enter",
        "sleep_bubble",
        "sleep_bubble_shrink_start",
        "sleep_bubble_shrink_large",
        "sleep_bubble_shrink_small",
        "wake_head_lift",
        "wake_head_lift_mid",
        "wake_up",
        "rise_prepare",
        "rise_support",
        "rise_support_to_shift",
        "rise_weight_shift",
        "rise_unfold_mid",
        "rise_unfold",
        "rise_low_support",
        "rise_feet_plant",
        "rise_crouch_low",
        "rise_half_crouch",
        "rise_mid",
        "rise_up",
        "rise_near_stand",
        "stretch_prepare",
        "stretch_arms_low",
        "stretch_waist",
        "stretch_chest",
        "stretch_elbow_mid",
        "stretch_chest_to_shoulders",
        "stretch_upper",
        "stretch_open_high",
        "stretch",
        "stretch_release_open_high",
        "stretch_end",
        "yawn_transition",
        "yawn_mouth_quarter",
        "yawn_mouth_three_quarter",
        "yawn_mouth_wide",
        "yawn",
        "yawn_close_small",
        "yawn_to_rub",
        "rub_eye_touch",
        "rub_eye_press_mid",
        "rub_eye",
        "rub_hand_lowered",
        "rub_hand_down",
        "standing_recover",
        "return_default",
    )
    positions = tuple(events.index(marker) for marker in ordered_markers)
    assert positions == tuple(sorted(positions))
    assets = tuple(frame.asset_path for frame in manifest.frames)
    assert assets.count("frames/sleep_nod.png") == 0
    for name in NOD_FRAME_NAMES[:-1]:
        assert assets.count(f"frames/{name}") == 6
    assert assets.count(f"frames/{NOD_FRAME_NAMES[-1]}") == 3
    assert not any("frames/sleep_nod_10.png" == asset for asset in assets)
    assert len(manifest.frames) == 148
    assert len(set(assets)) == 74


def test_stretch_sequence_uses_local_scale_locked_frames_and_gentle_timing() -> None:
    manifest = load_action_manifest(DROWSY_SLEEP_MANIFEST)
    stretch_frames = tuple(
        frame
        for frame in manifest.frames
        if frame.event is not None and frame.event.startswith("stretch")
    )
    assert tuple(Path(frame.asset_path).name for frame in stretch_frames) == (
        STRETCH_EVENT_ASSETS
    )
    assert sum(frame.duration_ms for frame in stretch_frames) == 1610
    assert max(frame.duration_ms for frame in stretch_frames) == 260


def test_stretch_frames_lock_scale_baseline_center_and_tone() -> None:
    frames_dir = DROWSY_SLEEP_MANIFEST.parent / "frames"
    metrics = []
    scale_widths = []
    tone_metrics = []

    for name in STRETCH_FRAME_NAMES:
        with Image.open(frames_dir / name) as image:
            frame = image.convert("RGBA")
        metrics.append(_alpha_metrics(frame))
        scale_widths.append(
            _stable_region_width(frame, 0.45, region_top=0.72)
        )
        tone_metrics.append(_tone_metrics(frame))

    assert all(metric.height == 1453 for metric in metrics)
    assert all(metric.bottom == 1497 for metric in metrics)
    assert all(abs(metric.center_x - 512.0) <= 1.0 for metric in metrics)
    assert (max(scale_widths) - min(scale_widths)) / max(scale_widths) <= 0.08
    luminance_values = tuple(metric.luminance for metric in tone_metrics)
    saturation_values = tuple(metric.saturation for metric in tone_metrics)
    assert max(luminance_values) - min(luminance_values) <= 3.0
    assert max(saturation_values) - min(saturation_values) <= 8.0


def test_only_clip_boundaries_are_allowed_to_crossfade() -> None:
    manifest = load_action_manifest(DROWSY_SLEEP_MANIFEST)
    events = tuple(frame.event for frame in manifest.frames)
    assert REPLACEMENT_CROSSFADE_EVENTS == {"sit_down_start", "return_default"}
    assert REPLACEMENT_CROSSFADE_DURATION_MS == 140.0
    assert tuple(event for event in events if event in REPLACEMENT_CROSSFADE_EVENTS) == (
        "sit_down_start",
        "return_default",
    )
    forbidden_middle_stages = {
        "sit_down_lower",
        "sleep_eyes_half",
        "sleep_bubble_nod_local_peak",
        "wake_up",
        "rise_up",
        "stretch",
        "yawn",
        "rub_eye",
    }
    assert forbidden_middle_stages.isdisjoint(REPLACEMENT_CROSSFADE_EVENTS)


def test_every_sleep_frame_is_transparent_full_canvas_and_master_copy_is_exact() -> None:
    manifest = load_action_manifest(DROWSY_SLEEP_MANIFEST)
    unique_paths = {frame.asset_path for frame in manifest.frames}
    for relative_path in unique_paths:
        path = DROWSY_SLEEP_MANIFEST.parent / relative_path
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.mode == "RGBA"
            assert image.size == (1024, 1536)
            assert image.getchannel("A").getbbox() is not None
            assert image.getpixel((0, 0))[3] == 0
            assert image.getpixel((image.width - 1, 0))[3] == 0
    standing_copy = DROWSY_SLEEP_MANIFEST.parent / "frames/default_standing.png"
    assert _sha256(standing_copy) == _sha256(FULLBODY_RUNTIME_MASTER)


def test_all_generated_runtime_frames_share_the_same_center_and_baseline() -> None:
    manifest = load_action_manifest(DROWSY_SLEEP_MANIFEST)
    generated_paths = {
        frame.asset_path
        for frame in manifest.frames
        if frame.asset_path != "frames/default_standing.png"
    }
    bounds_by_path: dict[str, tuple[int, int, int, int]] = {}
    for relative_path in generated_paths:
        with Image.open(DROWSY_SLEEP_MANIFEST.parent / relative_path) as image:
            bounds = image.getchannel("A").getbbox()
        assert bounds is not None
        bounds_by_path[relative_path] = bounds
    assert all(bounds[3] == 1497 for bounds in bounds_by_path.values())
    assert all(
        abs((bounds[0] + bounds[2]) / 2.0 - 512.0) <= 1.0
        for bounds in bounds_by_path.values()
    )


def test_nod_and_rise_sequences_keep_a_stable_baseline_without_scale_simulation() -> None:
    frames_dir = DROWSY_SLEEP_MANIFEST.parent / "frames"

    def alpha_bounds(name: str) -> tuple[int, int, int, int]:
        with Image.open(frames_dir / name) as image:
            bounds = image.getchannel("A").getbbox()
        assert bounds is not None
        return bounds

    nod_bounds = tuple(
        alpha_bounds(name)
        for name in ("sleep_base.png", *NOD_FRAME_NAMES)
    )
    assert max(bounds[3] for bounds in nod_bounds) - min(bounds[3] for bounds in nod_bounds) <= 1
    nod_heights = tuple(bounds[3] - bounds[1] for bounds in nod_bounds)
    # Hair tips move with the local head pitch; lower-body silhouette QA below
    # remains the guard against whole-character scaling or body-base jitter.
    assert max(nod_heights) - min(nod_heights) <= 40
    nod_widths = tuple(bounds[2] - bounds[0] for bounds in nod_bounds)
    assert max(nod_widths) - min(nod_widths) <= 2
    nod_centers = tuple((bounds[0] + bounds[2]) / 2 for bounds in nod_bounds)
    assert max(nod_centers) - min(nod_centers) <= 1.5

    rise_bounds = tuple(
        alpha_bounds(name)
        for name in (
            "rise_support.png",
            "rise_weight_shift.png",
            "rise_unfold_mid.png",
            "rise_unfold.png",
            "rise_low_support.png",
            "rise_feet_plant.png",
            "rise_crouch_low.png",
            "rise_half_crouch.png",
            "rise_mid.png",
            "rise_up.png",
            "rise_near_stand.png",
            "standing_sleepy.png",
        )
    )
    assert max(bounds[3] for bounds in rise_bounds) - min(bounds[3] for bounds in rise_bounds) <= 1
    rise_heights = tuple(bounds[3] - bounds[1] for bounds in rise_bounds)
    assert rise_heights == tuple(sorted(rise_heights))
    rise_centers = tuple((bounds[0] + bounds[2]) / 2 for bounds in rise_bounds)
    assert max(rise_centers) - min(rise_centers) <= 1.0


def test_local_nod_frames_keep_the_lower_body_and_tone_close_to_sleep_base() -> None:
    frames_dir = DROWSY_SLEEP_MANIFEST.parent / "frames"
    with Image.open(frames_dir / "sleep_base.png") as image:
        reference = image.convert("RGBA")

    for name in NOD_FRAME_NAMES:
        with Image.open(frames_dir / name) as image:
            candidate = image.convert("RGBA")
        _validate_stable_region(
            candidate,
            reference,
            region_top=0.55,
            max_alpha_difference=0.085,
        )
        _validate_tone_pair(
            candidate,
            reference,
            max_luminance_delta=10.0,
            max_channel_delta=14.0,
            max_saturation_delta=18.0,
        )
