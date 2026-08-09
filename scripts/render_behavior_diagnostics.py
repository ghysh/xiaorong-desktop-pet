"""Render Stage 8 behavior diagnostics without creating character animation assets."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from math import hypot
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from desktop_pet.animation.idle_motion import IdleMotionProfile
from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.app import create_application
from desktop_pet.behavior.profiles import calculate_behavior_transform, profile_for_state
from desktop_pet.behavior.scheduler import BehaviorScheduler
from desktop_pet.behavior.state import AUTOMATIC_STATES, STATE_PRIORITY, PetState
from desktop_pet.behavior.transition import automatic_targets
from desktop_pet.config import BehaviorConfig
from desktop_pet.paths import BEHAVIOR_ANALYSIS_DIR
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_sha256

DIAGNOSTIC_SEED = 20260805
STATE_COLORS = {
    PetState.STARTING: (130, 150, 170),
    PetState.IDLE_CALM: (72, 139, 202),
    PetState.IDLE_QUIET: (83, 174, 138),
    PetState.IDLE_SWAY: (142, 105, 205),
    PetState.RESTING: (226, 165, 72),
    PetState.DRAGGING: (214, 83, 83),
    PetState.SETTLING: (234, 122, 68),
    PetState.CLICK_REACTION: (190, 82, 150),
    PetState.PAUSED: (105, 105, 112),
    PetState.STOPPED: (38, 40, 45),
}


def _save_pillow(image: Image.Image, path: Path) -> None:
    image.save(path, "PNG")


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    draw.line((start, end), fill=color, width=2)
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    length = hypot(delta_x, delta_y)
    if length == 0:
        return
    unit_x = delta_x / length
    unit_y = delta_y / length
    end_x, end_y = end
    base_x = end_x - 10 * unit_x
    base_y = end_y - 10 * unit_y
    perpendicular_x = -unit_y * 4
    perpendicular_y = unit_x * 4
    draw.polygon(
        (
            (end_x, end_y),
            (base_x + perpendicular_x, base_y + perpendicular_y),
            (base_x - perpendicular_x, base_y - perpendicular_y),
        ),
        fill=color,
    )


def _render_state_graph(path: Path) -> None:
    image = Image.new("RGB", (1500, 760), (247, 249, 251))
    draw = ImageDraw.Draw(image)
    positions = {
        PetState.STARTING: (80, 250),
        PetState.IDLE_CALM: (320, 210),
        PetState.IDLE_QUIET: (570, 120),
        PetState.IDLE_SWAY: (570, 300),
        PetState.RESTING: (810, 210),
        PetState.DRAGGING: (1060, 100),
        PetState.SETTLING: (1260, 250),
        PetState.CLICK_REACTION: (1010, 380),
        PetState.PAUSED: (650, 540),
        PetState.STOPPED: (1160, 540),
    }
    automatic_edges = []
    for state in AUTOMATIC_STATES:
        automatic_edges.extend((state, target) for target in automatic_targets(state))
    edges = [
        (PetState.STARTING, PetState.IDLE_CALM, (90, 110, 130)),
        *((source, target, (70, 130, 190)) for source, target in automatic_edges),
        *((state, PetState.DRAGGING, (200, 70, 70)) for state in AUTOMATIC_STATES | {PetState.STARTING}),
        (PetState.DRAGGING, PetState.SETTLING, (220, 100, 50)),
        (PetState.SETTLING, PetState.IDLE_CALM, (220, 100, 50)),
        *(
            (state, PetState.CLICK_REACTION, (180, 65, 140))
            for state in AUTOMATIC_STATES | {PetState.STARTING}
        ),
        *(
            (PetState.CLICK_REACTION, state, (180, 65, 140))
            for state in AUTOMATIC_STATES | {PetState.STARTING}
        ),
        *((state, PetState.PAUSED, (95, 95, 100)) for state in AUTOMATIC_STATES | {PetState.STARTING}),
        (PetState.PAUSED, PetState.IDLE_CALM, (95, 95, 100)),
        *((state, PetState.STOPPED, (30, 30, 35)) for state in PetState if state is not PetState.STOPPED),
    ]
    for source, target, color in edges:
        source_x, source_y = positions[source]
        target_x, target_y = positions[target]
        _draw_arrow(draw, (source_x + 85, source_y + 24), (target_x, target_y + 24), color)
    for state, (x, y) in positions.items():
        color = STATE_COLORS[state]
        draw.rounded_rectangle((x, y, x + 170, y + 48), radius=9, fill=color, outline=(25, 30, 35), width=2)
        draw.text((x + 10, y + 17), state.name, fill=(255, 255, 255))
    draw.text((30, 25), "Stage 10 behavior state graph", fill=(25, 30, 35))
    draw.text(
        (30, 48),
        "blue/green/purple/orange = automatic; red = user drag; gray/black = lifecycle",
        fill=(25, 30, 35),
    )
    draw.text(
        (30, 700),
        "Priority: STOPPED > PAUSED > DRAGGING > SETTLING > CLICK_REACTION > STARTING > automatic states",
        fill=(25, 30, 35),
    )
    _save_pillow(image, path)


def _simulate_timeline(config: BehaviorConfig, total_seconds: float = 90.0) -> list[dict[str, object]]:
    scheduler = BehaviorScheduler(config)
    segments: list[dict[str, object]] = []
    elapsed = 0.0
    segments.append({"start": elapsed, "end": config.starting_duration_seconds, "state": PetState.STARTING.name})
    elapsed = config.starting_duration_seconds
    state = PetState.IDLE_CALM
    while elapsed < total_seconds:
        duration = scheduler.choose_duration(state)
        end = min(total_seconds, elapsed + duration)
        segments.append({"start": elapsed, "end": end, "state": state.name})
        elapsed += duration
        if elapsed < total_seconds:
            state = scheduler.choose_next_state(state)
    return segments


def _render_timeline(path: Path, config: BehaviorConfig, segments: list[dict[str, object]]) -> None:
    width, height = 1800, 720
    image = Image.new("RGB", (width, height), (247, 249, 251))
    draw = ImageDraw.Draw(image)
    left, right = 100, width - 40
    timeline_top = 90
    timeline_height = 90
    total = 90.0
    draw.text((30, 22), f"90-second offline timeline / seed={DIAGNOSTIC_SEED}", fill=(25, 30, 35))
    legend_x = 420
    for state in (PetState.STARTING, PetState.IDLE_CALM, PetState.IDLE_QUIET, PetState.IDLE_SWAY, PetState.RESTING):
        draw.rectangle((legend_x, 19, legend_x + 14, 33), fill=STATE_COLORS[state])
        draw.text((legend_x + 19, 20), state.name, fill=(25, 30, 35))
        legend_x += 150
    for segment in segments:
        state = PetState[str(segment["state"])]
        x1 = left + int((float(segment["start"]) / total) * (right - left))
        x2 = left + int((float(segment["end"]) / total) * (right - left))
        draw.rectangle((x1, timeline_top, max(x1 + 1, x2), timeline_top + timeline_height), fill=STATE_COLORS[state])
    draw.rectangle((left, timeline_top, right, timeline_top + timeline_height), outline=(25, 30, 35), width=2)
    for seconds in range(0, 91, 10):
        x = left + int((seconds / total) * (right - left))
        draw.line(
            (x, timeline_top + timeline_height, x, timeline_top + timeline_height + 8),
            fill=(30, 35, 40),
            width=1,
        )
        draw.text((x - 8, timeline_top + timeline_height + 12), str(seconds), fill=(30, 35, 40))

    metric_rows = (
        ("breathing period", "breathing_period_multiplier"),
        ("breathing amplitude", "breathing_scale_y_multiplier"),
        ("floating amplitude", "floating_amplitude_multiplier"),
        ("sway amplitude", "sway_amplitude_multiplier"),
        ("fixed tilt", "fixed_rotation_degrees"),
    )
    for row_index, (label, attribute) in enumerate(metric_rows):
        y = 270 + row_index * 75
        draw.text((15, y - 7), label, fill=(25, 30, 35))
        draw.line((left, y + 30, right, y + 30), fill=(205, 210, 216), width=1)
        previous_point: tuple[int, int] | None = None
        for segment in segments:
            state = PetState[str(segment["state"])]
            profile = profile_for_state(state, config)
            value = float(getattr(profile, attribute))
            normalized = min(1.5, max(0.0, value)) / 1.5
            x1 = left + int((float(segment["start"]) / total) * (right - left))
            x2 = left + int((float(segment["end"]) / total) * (right - left))
            value_y = y + 30 - int(normalized * 50)
            if previous_point is not None:
                draw.line((previous_point, (x1, value_y)), fill=(60, 90, 145), width=2)
            draw.line((x1, value_y, x2, value_y), fill=(60, 90, 145), width=2)
            previous_point = (x2, value_y)
    _save_pillow(image, path)


def _new_qimage(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(247, 249, 251))
    return image


def _draw_character_cell(
    painter: QPainter,
    window: PetWindow,
    transform: AnimationTransform,
    index: int,
) -> None:
    origin = QPointF(index * 320 + 20, 62)
    painter.save()
    painter.setPen(QPen(QColor(180, 188, 196), 1))
    painter.drawRect(int(origin.x()), int(origin.y()), window.width(), window.height())
    painter.translate(origin)
    transform.apply_to_painter(painter, window.animation_anchor)
    painter.drawPixmap(0, 0, window._scaled_pixmap)
    painter.restore()


def _add_labels(path: Path, labels: list[str]) -> None:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    draw = ImageDraw.Draw(image)
    for index, label in enumerate(labels):
        x = index * 320 + 20
        draw.rectangle((x, 5, x + 280, 56), fill=(247, 249, 251, 255))
        draw.multiline_text((x, 7), label, fill=(25, 30, 35, 255), spacing=2)
    image.save(path, "PNG")


def _render_profile_comparison(window: PetWindow, path: Path) -> None:
    states = (PetState.IDLE_CALM, PetState.IDLE_QUIET, PetState.IDLE_SWAY, PetState.RESTING)
    base = IdleMotionProfile.from_config(window.config.animation)
    image = _new_qimage(1280, 500)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    labels = []
    for index, state in enumerate(states):
        profile = profile_for_state(state, window.config.behavior)
        transform = calculate_behavior_transform(2.4, base, profile)
        _draw_character_cell(painter, window, transform, index)
        labels.append(
            f"{state.name}\nfloat x{profile.floating_amplitude_multiplier:.2f}, "
            f"sway x{profile.sway_amplitude_multiplier:.2f}\n"
            f"breath x{profile.breathing_scale_y_multiplier:.2f}, fixed {profile.fixed_rotation_degrees:+.2f} deg"
        )
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Unable to save behavior diagnostic: {path}")
    _add_labels(path, labels)


def _render_drag_override(window: PetWindow, path: Path) -> None:
    base = IdleMotionProfile.from_config(window.config.animation)
    calm = profile_for_state(PetState.IDLE_CALM, window.config.behavior)
    dragging = profile_for_state(PetState.DRAGGING, window.config.behavior)
    settling = profile_for_state(PetState.SETTLING, window.config.behavior)
    transforms = (
        calculate_behavior_transform(1.0, base, calm),
        calculate_behavior_transform(1.0, base, dragging).combined_with(
            AnimationTransform(rotation_degrees=-3.0)
        ),
        calculate_behavior_transform(1.0, base, settling).combined_with(
            AnimationTransform(rotation_degrees=-0.4)
        ),
        calculate_behavior_transform(1.0, base, calm),
    )
    labels = [
        "IDLE_CALM / t=0.00s\nautomatic motion active",
        "DRAGGING / t=0.10s\nidle float+sway off, tilt=-3.00 deg",
        "SETTLING / t=0.22s\nease-out tilt=-0.40 deg",
        "IDLE_CALM restored / t=0.35s\nprofile blend resumes",
    ]
    image = _new_qimage(1280, 500)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for index, transform in enumerate(transforms):
        _draw_character_cell(painter, window, transform, index)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Unable to save behavior diagnostic: {path}")
    _add_labels(path, labels)


def main() -> int:
    """Create only Stage 8 inspection outputs under assets/analysis/behavior."""
    application = create_application(["render-behavior-diagnostics"])
    window = PetWindow()
    config = BehaviorConfig(behavior_seed=DIAGNOSTIC_SEED)
    BEHAVIOR_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "behavior_state_graph.png": BEHAVIOR_ANALYSIS_DIR / "behavior_state_graph.png",
        "behavior_timeline.png": BEHAVIOR_ANALYSIS_DIR / "behavior_timeline.png",
        "behavior_profile_comparison.png": BEHAVIOR_ANALYSIS_DIR / "behavior_profile_comparison.png",
        "behavior_drag_override.png": BEHAVIOR_ANALYSIS_DIR / "behavior_drag_override.png",
        "behavior_diagnostic_summary.json": BEHAVIOR_ANALYSIS_DIR / "behavior_diagnostic_summary.json",
    }
    segments = _simulate_timeline(config)
    _render_state_graph(outputs["behavior_state_graph.png"])
    _render_timeline(outputs["behavior_timeline.png"], config, segments)
    _render_profile_comparison(window, outputs["behavior_profile_comparison.png"])
    _render_drag_override(window, outputs["behavior_drag_override.png"])
    base = IdleMotionProfile.from_config(window.config.animation)
    clipping = {}
    for state in AUTOMATIC_STATES:
        profile = profile_for_state(state, config)
        clipping[state.name] = all(
            window.is_transform_safe(calculate_behavior_transform(index / 10, base, profile))
            for index in range(576)
        )
    summary = {
        "purpose": "Stage 8 inspection diagnostics only; not character animation frames.",
        "simulation_seconds": 90.0,
        "actual_seed": DIAGNOSTIC_SEED,
        "state_priority": {state.name: priority for state, priority in STATE_PRIORITY.items()},
        "duration_ranges": {
            state.name: asdict(BehaviorScheduler(config).duration_range(state)) for state in AUTOMATIC_STATES
        },
        "transition_weights": {
            state.name: {target.name: weight for target, weight in BehaviorScheduler.transition_weights(state)}
            for state in AUTOMATIC_STATES
        },
        "profile_transition_duration_seconds": config.profile_transition_duration_seconds,
        "timeline": segments,
        "clipping_checks": clipping,
        "animation_qtimer_count": 1,
        "runtime_asset_sha256": runtime_asset_sha256(window.asset_path),
    }
    outputs["behavior_diagnostic_summary.json"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for output in outputs.values():
        print(output)
    window.close()
    application.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
