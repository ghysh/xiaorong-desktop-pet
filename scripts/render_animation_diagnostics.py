"""Render Stage 7 inspection-only contact sheets without creating character animation frames."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from desktop_pet.animation.easing import ease_out_cubic
from desktop_pet.animation.idle_motion import IdleMotionProfile, calculate_idle_transform
from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.app import create_application
from desktop_pet.paths import ANIMATION_ANALYSIS_DIR
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_sha256

CELL_WIDTH = 320
CELL_HEIGHT = 490
LABEL_HEIGHT = 58


def _new_canvas(width: int, height: int) -> QImage:
    """Create a diagnostic canvas; this is never used as a runtime character asset."""
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(246, 248, 250))
    return image


def _draw_transform_cell(
    painter: QPainter,
    window: PetWindow,
    transform: AnimationTransform,
    column: int,
    row: int,
    label: str,
) -> None:
    """Draw a cached-pixmap transform plus values into one inspection-only contact-sheet cell."""
    origin_x = column * CELL_WIDTH + 20
    origin_y = row * CELL_HEIGHT + LABEL_HEIGHT
    painter.save()
    painter.setPen(QPen(QColor(180, 188, 196), 1))
    painter.drawRect(origin_x, origin_y, window.width(), window.height())
    painter.translate(origin_x, origin_y)
    transform.apply_to_painter(painter, window.animation_anchor)
    painter.drawPixmap(0, 0, window._scaled_pixmap)
    painter.restore()
    del label


def _save_image(image: QImage, output_path: Path) -> None:
    """Save an inspection image and fail explicitly instead of silently omitting diagnostics."""
    if not image.save(str(output_path), "PNG"):
        raise RuntimeError(f"Unable to save animation diagnostic: {output_path}")


def _draw_cell_labels(output_path: Path, labels: list[str]) -> None:
    """Use Pillow's built-in bitmap font because offscreen Qt has no installed text fonts."""
    with Image.open(output_path) as source_image:
        image = source_image.convert("RGBA")
    draw = ImageDraw.Draw(image)
    for index, label in enumerate(labels):
        x = (index % 4) * CELL_WIDTH + 20
        y = (index // 4) * CELL_HEIGHT + 4
        if len(labels) == 5:
            x = (index % 3) * CELL_WIDTH + 20
        draw.rectangle((x, y, x + 280, y + 50), fill=(246, 248, 250, 255))
        draw.multiline_text((x, y), label, fill=(35, 42, 48, 255), spacing=2)
    image.save(output_path, "PNG")


def _draw_overlay_labels(output_path: Path) -> None:
    """Add readable ASCII legend text to the bounds overlay without touching the character asset."""
    with Image.open(output_path) as source_image:
        image = source_image.convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 8, 630, 52), fill=(246, 248, 250, 255))
    draw.text((20, 12), "Stage 7 bounds: black=window, blue dash=source alpha", fill=(30, 30, 30, 255))
    draw.text((20, 30), "red/green=idle, purple/orange=drag +/-; all stay inside", fill=(30, 30, 30, 255))
    image.save(output_path, "PNG")


def _render_idle_sheet(window: PetWindow, output_path: Path) -> None:
    """Show eight samples across the 57.6-second combined deterministic idle cycle."""
    canvas = _new_canvas(CELL_WIDTH * 4, CELL_HEIGHT * 2)
    profile = IdleMotionProfile.from_config(window.config.animation)
    combined_cycle_seconds = 57.6
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    labels: list[str] = []
    for index in range(8):
        elapsed_seconds = combined_cycle_seconds * index / 8
        transform = calculate_idle_transform(elapsed_seconds, profile)
        label = (
            f"{index * 12.5:.1f}% / {elapsed_seconds:.1f}s\n"
            f"y={transform.offset_y:+.2f}, sx={transform.scale_x:.4f}\n"
            f"sy={transform.scale_y:.4f}, rot={transform.rotation_degrees:+.2f} deg"
        )
        labels.append(label)
        _draw_transform_cell(
            painter,
            window,
            transform,
            index % 4,
            index // 4,
            label,
        )
    painter.end()
    _save_image(canvas, output_path)
    _draw_cell_labels(output_path, labels)


def _render_drag_sheet(window: PetWindow, output_path: Path) -> None:
    """Show both allowed drag directions and the cubic half-way return state."""
    maximum = window.effective_drag_tilt_max_degrees
    return_halfway = maximum * (1.0 - ease_out_cubic(0.5))
    samples = (
        (AnimationTransform(rotation_degrees=-maximum), "right drag -> left tilt"),
        (AnimationTransform.identity(), "neutral"),
        (AnimationTransform(rotation_degrees=maximum), "left drag -> right tilt"),
        (AnimationTransform(rotation_degrees=return_halfway), "release return 50%"),
        (AnimationTransform.identity(), "release return complete"),
    )
    canvas = _new_canvas(CELL_WIDTH * 3, CELL_HEIGHT * 2)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    labels: list[str] = []
    for index, (transform, label) in enumerate(samples):
        annotated_label = (
            f"{label}\n"
            f"y={transform.offset_y:+.2f}, sx={transform.scale_x:.4f}\n"
            f"sy={transform.scale_y:.4f}, rot={transform.rotation_degrees:+.2f} deg"
        )
        labels.append(annotated_label)
        _draw_transform_cell(painter, window, transform, index % 3, index // 3, annotated_label)
    painter.end()
    _save_image(canvas, output_path)
    _draw_cell_labels(output_path, labels)


def _render_bounds_overlay(window: PetWindow, output_path: Path) -> None:
    """Overlay source and conservative transformed alpha bounds inside the unchanged window."""
    canvas = _new_canvas(640, 540)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    origin = QPointF(180.0, 70.0)
    painter.save()
    painter.translate(origin)
    painter.drawPixmap(0, 0, window._scaled_pixmap)
    painter.restore()

    painter.setPen(QPen(QColor(30, 30, 30), 2))
    painter.drawRect(QRectF(origin.x(), origin.y(), window.width(), window.height()))
    painter.setPen(QPen(QColor(28, 112, 184), 2, Qt.PenStyle.DashLine))
    painter.drawRect(window.alpha_bounds_window.translated(origin))
    colors = (QColor(218, 75, 75), QColor(68, 142, 78), QColor(126, 87, 194), QColor(239, 132, 45))
    transforms = (
        AnimationTransform(
            offset_y=-window.config.animation.floating_amplitude_pixels,
            scale_x=1.0 + window.config.animation.breathing_scale_x,
            scale_y=1.002 + window.config.animation.breathing_scale_y,
            rotation_degrees=window.config.animation.sway_amplitude_degrees,
        ),
        AnimationTransform(
            offset_y=window.config.animation.floating_amplitude_pixels,
            scale_x=1.0 - window.config.animation.breathing_scale_x,
            scale_y=1.002 - window.config.animation.breathing_scale_y,
            rotation_degrees=-window.config.animation.sway_amplitude_degrees,
        ),
        AnimationTransform(rotation_degrees=window.effective_drag_tilt_max_degrees),
        AnimationTransform(rotation_degrees=-window.effective_drag_tilt_max_degrees),
    )
    for color, transform in zip(colors, transforms, strict=True):
        painter.setPen(QPen(color, 2))
        painter.drawRect(window.transformed_alpha_bounds(transform).translated(origin))
    painter.end()
    _save_image(canvas, output_path)
    _draw_overlay_labels(output_path)


def main() -> int:
    """Create only the requested inspection diagnostics under assets/analysis/animation."""
    application = create_application(["render-animation-diagnostics"])
    window = PetWindow()
    ANIMATION_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "idle_motion_contact_sheet.png": ANIMATION_ANALYSIS_DIR / "idle_motion_contact_sheet.png",
        "drag_tilt_contact_sheet.png": ANIMATION_ANALYSIS_DIR / "drag_tilt_contact_sheet.png",
        "transform_bounds_overlay.png": ANIMATION_ANALYSIS_DIR / "transform_bounds_overlay.png",
        "animation_parameter_summary.json": ANIMATION_ANALYSIS_DIR / "animation_parameter_summary.json",
    }
    _render_idle_sheet(window, outputs["idle_motion_contact_sheet.png"])
    _render_drag_sheet(window, outputs["drag_tilt_contact_sheet.png"])
    _render_bounds_overlay(window, outputs["transform_bounds_overlay.png"])
    summary = {
        "purpose": "Stage 7 inspection diagnostics only; not runtime animation frames.",
        "runtime_asset_sha256": runtime_asset_sha256(window.asset_path),
        "source_alpha_bounds": list(window._source_alpha_bounds),
        "projected_alpha_bounds": [
            window.alpha_bounds_window.left(),
            window.alpha_bounds_window.top(),
            window.alpha_bounds_window.right(),
            window.alpha_bounds_window.bottom(),
        ],
        "feet_anchor": [window.animation_anchor.x(), window.animation_anchor.y()],
        "parameters": {
            "target_fps": window.config.animation.target_fps,
            "breathing_period_seconds": window.config.animation.breathing_period_seconds,
            "breathing_scale_x_amplitude": window.config.animation.breathing_scale_x,
            "breathing_scale_y_center": 1.002,
            "breathing_scale_y_amplitude": window.config.animation.breathing_scale_y,
            "floating_period_seconds": window.config.animation.floating_period_seconds,
            "floating_amplitude_pixels": window.config.animation.floating_amplitude_pixels,
            "sway_period_seconds": window.config.animation.sway_period_seconds,
            "sway_amplitude_degrees": window.config.animation.sway_amplitude_degrees,
            "configured_drag_tilt_max_degrees": window.config.animation.drag_tilt_max_degrees,
            "effective_drag_tilt_max_degrees": window.effective_drag_tilt_max_degrees,
            "drag_tilt_smoothing": window.config.animation.drag_tilt_smoothing,
            "drag_return_duration_ms": window.config.animation.drag_return_duration_ms,
        },
        "transform_order": [
            "overall float translation",
            "translate to feet anchor",
            "rotate",
            "scale",
            "translate back",
            "draw cached pixmap",
        ],
        "clipping_checks": window.clipping_checks(),
    }
    outputs["animation_parameter_summary.json"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for output_path in outputs.values():
        print(output_path)
    window.close()
    application.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
