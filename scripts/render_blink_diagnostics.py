"""Render deterministic blink overlay and composite diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from desktop_pet.paths import BLINK_ANALYSIS_DIR, BLINK_DIAGNOSTICS_DIR, BLINK_FRAMES_DIR, FULLBODY_RUNTIME_MASTER

FRAME_SEQUENCE = (
    ("open", "blink_open.png", 35),
    ("half closed", "blink_half_closed.png", 35),
    ("closed", "blink_closed.png", 55),
    ("half open", "blink_half_open.png", 35),
    ("open", "blink_open.png", 35),
)
EYE_CROP = (350, 175, 540, 292)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def checkerboard(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(198, 198, 198, 255))
    return image


def label_panel(image: Image.Image, label: str) -> Image.Image:
    header = 34
    panel = Image.new("RGBA", (image.width, image.height + header), "white")
    panel.alpha_composite(image, (0, header))
    ImageDraw.Draw(panel).text((8, 9), label, fill=(20, 20, 20, 255), font=ImageFont.load_default())
    return panel


def contact_sheet(panels: list[Image.Image], columns: int, gap: int = 10) -> Image.Image:
    width = max(panel.width for panel in panels)
    height = max(panel.height for panel in panels)
    rows = (len(panels) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * width + (columns + 1) * gap, rows * height + (rows + 1) * gap), "white")
    for index, panel in enumerate(panels):
        x = gap + (index % columns) * (width + gap)
        y = gap + (index // columns) * (height + gap)
        sheet.alpha_composite(panel, (x, y))
    return sheet


def render() -> dict[str, object]:
    BLINK_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(FULLBODY_RUNTIME_MASTER) as image:
        source = image.convert("RGBA")
    overlays = {name: Image.open(BLINK_FRAMES_DIR / name).convert("RGBA") for _label, name, _ms in FRAME_SEQUENCE}
    composites = [
        (label, name, duration, Image.alpha_composite(source, overlays[name]))
        for label, name, duration in FRAME_SEQUENCE
    ]

    region = source.crop((330, 150, 580, 330)).resize((750, 540), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(region)
    scale = 3
    draw.rectangle(tuple((value - (330 if index % 2 == 0 else 150)) * scale for index, value in enumerate(EYE_CROP)),
                   outline=(255, 80, 80, 255), width=3)
    region.save(BLINK_ANALYSIS_DIR / "blink_source_eye_region.png")

    overlay_panels = []
    composite_panels = []
    for label, name, duration, composite in composites:
        overlay_crop = overlays[name].crop(EYE_CROP).resize((570, 351), Image.Resampling.LANCZOS)
        background = checkerboard(overlay_crop.size)
        background.alpha_composite(overlay_crop)
        bounds = overlays[name].getchannel("A").getbbox()
        overlay_panels.append(label_panel(background, f"{name} | {duration} ms | alpha={bounds}"))
        crop = composite.crop(EYE_CROP).resize((570, 351), Image.Resampling.LANCZOS)
        composite_panels.append(label_panel(crop, f"{label} | {duration} ms"))
    contact_sheet(overlay_panels, 3).save(BLINK_ANALYSIS_DIR / "blink_overlay_contact_sheet.png")
    contact_sheet(composite_panels, 3).save(BLINK_ANALYSIS_DIR / "blink_composite_contact_sheet.png")

    size_panels: list[Image.Image] = []
    closed_composite = composites[2][3]
    for size in ((240, 360), (280, 420), (320, 480)):
        scaled = closed_composite.resize(size, Image.Resampling.LANCZOS)
        sx, sy = size[0] / 1024, size[1] / 1536
        crop_box = tuple(round(value * (sx if index % 2 == 0 else sy)) for index, value in enumerate(EYE_CROP))
        crop = scaled.crop(crop_box).resize((570, 351), Image.Resampling.LANCZOS)
        size_panels.append(label_panel(crop, f"closed composite at {size[0]}x{size[1]}"))
    contact_sheet(size_panels, 3).save(BLINK_ANALYSIS_DIR / "blink_three_size_comparison.png")

    closed_overlay = overlays["blink_closed.png"].crop(EYE_CROP).resize((570, 351), Image.Resampling.LANCZOS)
    for name, background in (
        ("white", Image.new("RGBA", closed_overlay.size, "white")),
        ("black", Image.new("RGBA", closed_overlay.size, "black")),
        ("checkerboard", checkerboard(closed_overlay.size)),
    ):
        background.alpha_composite(closed_overlay)
        background.save(BLINK_ANALYSIS_DIR / f"blink_on_{name}.png")

    open_composite = composites[0][3]
    difference = ImageChops.difference(source, open_composite)
    difference_crop = difference.crop(EYE_CROP).resize((570, 351), Image.Resampling.NEAREST)
    difference_crop.save(BLINK_ANALYSIS_DIR / "blink_difference_map.png")
    difference_bbox = difference.getbbox()
    summary = {
        "source_sha256": sha256(FULLBODY_RUNTIME_MASTER),
        "frame_sequence": [
            {"label": label, "asset": name, "duration_ms": duration} for label, name, duration in FRAME_SEQUENCE
        ],
        "total_duration_ms": sum(duration for _label, _name, duration in FRAME_SEQUENCE),
        "approved_eye_crop": list(EYE_CROP),
        "open_composite_difference_bbox": None if difference_bbox is None else list(difference_bbox),
        "open_composite_exact_match": difference_bbox is None,
        "diagnostic_files": sorted(path.name for path in BLINK_ANALYSIS_DIR.glob("*.png")),
        "eye_region_metadata": str((BLINK_DIAGNOSTICS_DIR / "blink_eye_region.json").resolve()),
    }
    (BLINK_ANALYSIS_DIR / "blink_diagnostic_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for overlay in overlays.values():
        overlay.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    render()
