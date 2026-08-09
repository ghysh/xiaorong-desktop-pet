"""Render non-runtime Stage 9 click, alpha, size, and schema diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from desktop_pet.app import create_application
from desktop_pet.config import ALPHA_HIT_TEST_THRESHOLD, CLICK_REACTION_DURATION_MS
from desktop_pet.interaction.click_reaction import click_reaction_transform
from desktop_pet.paths import FULLBODY_RUNTIME_MASTER, INTERACTION_ANALYSIS_DIR
from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_sha256

SAMPLES_MS = (0, 60, 90, 140, 180, 220, 260)
DIAGNOSTIC_FONT_PATH = Path("C:/Windows/Fonts/arial.ttf")


def _save(image: QImage, path: Path) -> None:
    if not image.save(str(path), "PNG"):
        raise OSError(f"Could not save diagnostic image: {path}")


def _annotate_with_pillow(
    path: Path,
    labels: list[tuple[tuple[int, int], str, int]],
    clear_rectangles: list[tuple[int, int, int, int]],
) -> None:
    """Use an explicit Windows font because Qt offscreen text can lack glyphs."""
    with Image.open(path) as source:
        image = source.convert("RGBA")
    draw = ImageDraw.Draw(image)
    for rectangle in clear_rectangles:
        draw.rectangle(rectangle, fill="#111820")
    for position, label, size in labels:
        font = (
            ImageFont.truetype(str(DIAGNOSTIC_FONT_PATH), size)
            if DIAGNOSTIC_FONT_PATH.is_file()
            else ImageFont.load_default()
        )
        draw.text(position, label, font=font, fill="#f4f7fb")
    image.save(path, "PNG")


def _checker(painter: QPainter, rect: QRect, cell: int = 16) -> None:
    for y in range(rect.top(), rect.bottom() + 1, cell):
        for x in range(rect.left(), rect.right() + 1, cell):
            parity = ((x - rect.left()) // cell + (y - rect.top()) // cell) % 2
            painter.fillRect(QRect(x, y, cell, cell), QColor("#24303b" if parity else "#1b242d"))


def _render_alpha_map(window: PetWindow, output: Path) -> dict[str, int]:
    width, height = window.size().toTuple()
    scaled = window._source_image.scaled(
        window.size(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    image = QImage(width, height + 42, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#111820"))
    transparent = low = visible = 0
    for y in range(height):
        for x in range(width):
            alpha = scaled.pixelColor(x, y).alpha()
            if alpha == 0:
                color = QColor("#27323d")
                transparent += 1
            elif alpha < ALPHA_HIT_TEST_THRESHOLD:
                color = QColor("#f4b942")
                low += 1
            else:
                color = QColor("#41c7a5")
                visible += 1
            image.setPixelColor(x, y, color)
    painter = QPainter(image)
    painter.setFont(QFont("Arial", 10))
    painter.setPen(QPen(QColor("#ff5c7a"), 2))
    painter.drawRect(window.alpha_bounds_window)
    painter.setPen(QColor("#f4f7fb"))
    painter.drawText(8, height + 27, f"Alpha threshold >= {ALPHA_HIT_TEST_THRESHOLD} | red: alpha bounds")
    painter.end()
    _save(image, output)
    _annotate_with_pillow(
        output,
        [((8, height + 12), f"Alpha >= {ALPHA_HIT_TEST_THRESHOLD}: interactive | red: alpha bounds", 13)],
        [(0, height, width, height + 42)],
    )
    return {"transparent_pixels": transparent, "low_alpha_pixels": low, "interactive_pixels": visible}


def _render_pet_frame(window: PetWindow, elapsed_ms: int) -> QImage:
    frame = QImage(window.size(), QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(Qt.GlobalColor.transparent)
    painter = QPainter(frame)
    click_reaction_transform(elapsed_ms).apply_to_painter(painter, window.animation_anchor)
    painter.drawPixmap(0, 0, window._scaled_pixmap)
    painter.end()
    return frame


def _render_contact_sheet(window: PetWindow, output: Path) -> list[dict[str, object]]:
    panel_width, panel_height = 220, 370
    sheet = QImage(panel_width * len(SAMPLES_MS), panel_height, QImage.Format.Format_ARGB32_Premultiplied)
    sheet.fill(QColor("#111820"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Arial", 10))
    samples: list[dict[str, object]] = []
    for index, elapsed in enumerate(SAMPLES_MS):
        panel = QRect(index * panel_width, 0, panel_width, panel_height)
        _checker(painter, panel.adjusted(8, 42, -8, -48), 14)
        frame = _render_pet_frame(window, elapsed)
        target = QRect(panel.x() + 20, 48, 180, 270)
        painter.drawImage(target, frame)
        transform = click_reaction_transform(elapsed)
        painter.setPen(QColor("#f4f7fb"))
        painter.drawText(panel.x() + 10, 24, f"{elapsed} ms")
        painter.drawText(
            panel.x() + 10,
            340,
            f"sx {transform.scale_x:.4f}  sy {transform.scale_y:.4f}  y {transform.offset_y:+.2f}",
        )
        samples.append({"elapsed_ms": elapsed, "transform": transform.as_tuple()})
    painter.end()
    _save(sheet, output)
    labels = []
    for index, sample in enumerate(samples):
        x = index * panel_width + 10
        labels.append(((x, 10), f"{sample['elapsed_ms']} ms", 14))
        transform = sample["transform"]
        labels.append(
            (
                (x, 330),
                f"sx {transform[2]:.4f}  sy {transform[3]:.4f}  y {transform[1]:+.2f}",
                11,
            )
        )
    _annotate_with_pillow(
        output,
        labels,
        [(0, 0, sheet.width(), 40), (0, 322, sheet.width(), sheet.height())],
    )
    return samples


def _render_size_comparison(window: PetWindow, output: Path) -> list[dict[str, object]]:
    panel_width, panel_height = 360, 560
    image = QImage(panel_width * 3, panel_height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#111820"))
    painter = QPainter(image)
    painter.setFont(QFont("Arial", 11))
    results = []
    for index, size in enumerate(PetSize):
        window.set_pet_size(size, keep_feet_global=False)
        panel = QRect(index * panel_width + 20, 55, panel_width - 40, 480)
        _checker(painter, panel, 18)
        painter.drawPixmap(panel, window._scaled_pixmap)
        anchor = QPointF(
            panel.x() + window.animation_anchor.x() * panel.width() / window.width(),
            panel.y() + window.animation_anchor.y() * panel.height() / window.height(),
        )
        painter.setPen(QPen(QColor("#ff5c7a"), 2))
        painter.drawLine(int(anchor.x() - 10), int(anchor.y()), int(anchor.x() + 10), int(anchor.y()))
        painter.drawLine(int(anchor.x()), int(anchor.y() - 10), int(anchor.x()), int(anchor.y() + 10))
        painter.setPen(QColor("#f4f7fb"))
        painter.drawText(index * panel_width + 20, 30, f"{size.name}: {size.width} x {size.height}")
        results.append(
            {
                "size": size.name,
                "dimensions": size.value,
                "feet_anchor": [window.animation_anchor.x(), window.animation_anchor.y()],
                "clipping_safe": all(window.clipping_checks().values()),
            }
        )
    painter.end()
    _save(image, output)
    _annotate_with_pillow(
        output,
        [
            ((index * panel_width + 20, 14), f"{size.name}: {size.width} x {size.height}", 16)
            for index, size in enumerate(PetSize)
        ],
        [(0, 0, image.width(), 52)],
    )
    return results


def main() -> int:
    create_application(["render-interaction-diagnostics"])
    INTERACTION_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    window = PetWindow()
    alpha_counts = _render_alpha_map(window, INTERACTION_ANALYSIS_DIR / "alpha_hit_test_map.png")
    click_samples = _render_contact_sheet(
        window,
        INTERACTION_ANALYSIS_DIR / "click_reaction_contact_sheet.png",
    )
    sizes = _render_size_comparison(window, INTERACTION_ANALYSIS_DIR / "size_comparison.png")
    defaults = UserSettings()
    schema = {
        "schema_version": defaults.schema_version,
        "sizes": {size.name: list(size.value) for size in PetSize},
        "defaults": {
            "size": defaults.size.name,
            "always_on_top": defaults.always_on_top,
            "animation_enabled": defaults.animation_enabled,
            "behavior_enabled": defaults.behavior_enabled,
            "click_reaction_enabled": defaults.click_reaction_enabled,
            "remember_position": defaults.remember_position,
            "window_x": None,
            "window_y": None,
            "screen_name": None,
        },
    }
    (INTERACTION_ANALYSIS_DIR / "settings_schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "runtime_asset": str(FULLBODY_RUNTIME_MASTER),
        "runtime_asset_sha256": runtime_asset_sha256(FULLBODY_RUNTIME_MASTER),
        "alpha_threshold": ALPHA_HIT_TEST_THRESHOLD,
        "alpha_counts": alpha_counts,
        "click_duration_ms": CLICK_REACTION_DURATION_MS,
        "click_samples": click_samples,
        "sizes": sizes,
        "high_frequency_timer_count": 1,
        "diagnostics_are_runtime_frames": False,
    }
    (INTERACTION_ANALYSIS_DIR / "interaction_diagnostic_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    window.close()
    print(f"Stage 9 diagnostics written to: {INTERACTION_ANALYSIS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
