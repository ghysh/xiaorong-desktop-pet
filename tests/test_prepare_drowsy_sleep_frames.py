"""Strict alpha-bound normalization and candidate rejection checks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageEnhance
from scripts.prepare_drowsy_sleep_frames import (
    _alpha_metrics,
    _alpha_region_difference_ratio,
    _match_tone_lightly,
    _normalize_panel,
    _normalize_panel_to_reference,
    _stable_region_width,
    _tone_metrics,
    _validate_neighbor_pair,
    _validate_stable_region,
    _validate_tone_pair,
    main,
)


def _candidate(
    *,
    size: tuple[int, int] = (240, 320),
    bounds: tuple[int, int, int, int] = (70, 30, 170, 290),
) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle(bounds, radius=12, fill=(20, 30, 40, 255))
    return image


def test_normalize_panel_locks_canvas_height_center_and_bottom() -> None:
    normalized = _normalize_panel(
        _candidate(),
        target_height=1200,
        bottom=1497,
        target_center=512.0,
    )
    metrics = _alpha_metrics(normalized)
    assert normalized.size == (1024, 1536)
    assert normalized.mode == "RGBA"
    assert metrics.height == 1200
    assert metrics.bottom == 1497
    assert abs(metrics.center_x - 512.0) <= 1.0


def test_normalize_panel_rejects_cropped_or_large_disconnected_candidates() -> None:
    with pytest.raises(ValueError, match="cropped or touches an edge"):
        _normalize_panel(_candidate(bounds=(0, 30, 170, 290)), 1200, 1497)

    disconnected = _candidate()
    ImageDraw.Draw(disconnected).ellipse((185, 220, 225, 260), fill=(20, 30, 40, 255))
    with pytest.raises(ValueError, match="disconnected alpha component"):
        _normalize_panel(disconnected, 1200, 1497)


def test_neighbor_qa_rejects_center_or_scale_jumps() -> None:
    reference = _normalize_panel(_candidate(), 1200, 1497)
    shifted = _normalize_panel(_candidate(), 1200, 1497, target_center=520.0)
    with pytest.raises(ValueError, match="centre delta"):
        _validate_neighbor_pair(
            reference,
            shifted,
            max_center_delta=3.0,
            max_bottom_delta=1,
            max_height_ratio=0.12,
            max_width_ratio=0.35,
        )

    oversized = _normalize_panel(_candidate(), 1400, 1497)
    with pytest.raises(ValueError, match="height ratio"):
        _validate_neighbor_pair(
            reference,
            oversized,
            max_center_delta=3.0,
            max_bottom_delta=1,
            max_height_ratio=0.12,
            max_width_ratio=0.35,
        )


def test_reference_normalization_uses_stable_lower_body_scale() -> None:
    reference = _normalize_panel(_candidate(), 1200, 1497)
    undersized = _normalize_panel(_candidate(), 1140, 1497)
    normalized = _normalize_panel_to_reference(
        undersized,
        reference,
        1497,
        max_scale_correction=0.08,
    )
    metrics = _alpha_metrics(normalized)
    assert metrics.bottom == 1497
    assert abs(metrics.center_x - 512.0) <= 1.0
    assert abs(metrics.height - _alpha_metrics(reference).height) <= 2


def test_fixed_canvas_scale_band_ignores_raised_arm_bbox_height() -> None:
    reference = _candidate(bounds=(70, 30, 170, 290))
    raised_arms = reference.copy()
    ImageDraw.Draw(raised_arms).rectangle((10, 40, 230, 220), fill=(20, 30, 40, 255))

    fixed_reference_width = _stable_region_width(reference, 0.45, region_top=0.75)
    assert fixed_reference_width == 101
    assert (
        _stable_region_width(raised_arms, 0.45, region_top=0.75)
        == fixed_reference_width
    )
    assert _stable_region_width(raised_arms, 0.45) != _stable_region_width(reference, 0.45)


def test_stability_check_allows_head_change_but_rejects_lower_body_jump() -> None:
    reference = _normalize_panel(_candidate(), 1200, 1497)
    head_change = reference.copy()
    ImageDraw.Draw(head_change).ellipse((430, 250, 594, 410), fill=(20, 30, 40, 255))
    assert _alpha_region_difference_ratio(head_change, reference, 0.55) == 0.0
    _validate_stable_region(
        head_change,
        reference,
        region_top=0.55,
        max_alpha_difference=0.01,
    )

    lower_body_jump = reference.copy()
    ImageDraw.Draw(lower_body_jump).ellipse(
        (760, 1100, 940, 1420),
        fill=(20, 30, 40, 255),
    )
    with pytest.raises(ValueError, match="stable lower-body alpha difference"):
        _validate_stable_region(
            lower_body_jump,
            reference,
            region_top=0.55,
            max_alpha_difference=0.01,
        )


def test_tone_matching_is_bounded_and_reduces_reference_delta() -> None:
    reference = _normalize_panel(_candidate(), 1200, 1497)
    brighter = ImageEnhance.Brightness(reference).enhance(1.25)
    with pytest.raises(ValueError, match="tone luminance delta"):
        _validate_tone_pair(
            brighter,
            reference,
            max_luminance_delta=2.0,
            max_channel_delta=4.0,
            max_saturation_delta=8.0,
        )
    before = abs(_tone_metrics(brighter).luminance - _tone_metrics(reference).luminance)
    corrected = _match_tone_lightly(
        brighter,
        reference,
        max_channel_gain_delta=0.20,
        max_saturation_gain_delta=0.10,
    )
    after = abs(_tone_metrics(corrected).luminance - _tone_metrics(reference).luminance)
    assert corrected.getchannel("A").tobytes() == brighter.getchannel("A").tobytes()
    assert after < before


def test_cli_accepts_one_source_image_per_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = (tmp_path / "first.png", tmp_path / "second.png")
    for path in inputs:
        _candidate().save(path)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_drowsy_sleep_frames.py",
            "--input",
            *(str(path) for path in inputs),
            "--output-dir",
            str(output_dir),
            "--names",
            "first",
            "second",
            "--target-heights",
            "1100",
            "1120",
        ],
    )
    assert main() == 0
    assert (output_dir / "first.png").is_file()
    assert (output_dir / "second.png").is_file()
