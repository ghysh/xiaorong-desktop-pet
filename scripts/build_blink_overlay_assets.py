"""Build traceable full-canvas blink overlays from the protected Plan B master."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from desktop_pet.paths import (
    BLINK_DIAGNOSTICS_DIR,
    BLINK_FRAMES_DIR,
    BLINK_PREVIEWS_DIR,
    FULLBODY_RUNTIME_MASTER,
)

EXPECTED_MASTER_SHA256 = "6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64"
CANVAS_SIZE = (1024, 1536)
FEATHER_RADIUS = 1.0
FRAME_NAMES = (
    "blink_open.png",
    "blink_half_closed.png",
    "blink_closed.png",
    "blink_half_open.png",
)


@dataclass(frozen=True, slots=True)
class EyeGeometry:
    name: str
    bounds: tuple[int, int, int, int]
    full_polygon: tuple[tuple[int, int], ...]
    half_polygon: tuple[tuple[int, int], ...]
    half_lid: tuple[tuple[int, int], ...]
    closed_lid: tuple[tuple[int, int], ...]
    upper_skin_y: int
    lower_skin_y: int


EYES = (
    EyeGeometry(
        name="viewer_left",
        bounds=(372, 226, 435, 282),
        full_polygon=(
            (374, 246), (382, 234), (396, 228), (412, 229), (425, 236), (433, 247),
            (431, 262), (422, 274), (407, 280), (391, 276), (378, 265),
        ),
        half_polygon=(
            (374, 242), (383, 232), (397, 228), (413, 230), (426, 237), (432, 248),
            (430, 258), (419, 265), (391, 266), (376, 257),
        ),
        half_lid=((377, 244), (386, 248), (396, 251), (407, 251), (418, 247), (429, 240)),
        closed_lid=((377, 250), (386, 254), (397, 257), (408, 257), (419, 253), (429, 246)),
        upper_skin_y=235,
        lower_skin_y=274,
    ),
    EyeGeometry(
        name="viewer_right",
        bounds=(458, 194, 525, 251),
        full_polygon=(
            (460, 211), (469, 201), (482, 196), (499, 197), (513, 203), (522, 214),
            (520, 230), (511, 241), (498, 248), (482, 245), (469, 235), (462, 223),
        ),
        half_polygon=(
            (460, 207), (470, 199), (484, 196), (500, 198), (514, 204), (521, 215),
            (518, 225), (507, 232), (478, 234), (463, 223),
        ),
        half_lid=((463, 209), (473, 213), (484, 215), (496, 214), (508, 208), (519, 199)),
        closed_lid=((463, 215), (473, 219), (484, 222), (496, 221), (508, 215), (519, 206)),
        upper_skin_y=203,
        lower_skin_y=242,
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _polygon_mask(points: tuple[tuple[int, int], ...]) -> Image.Image:
    mask = Image.new("L", CANVAS_SIZE, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(FEATHER_RADIUS))


def _warp_eye(source: Image.Image, eye: EyeGeometry, *, progress: float) -> Image.Image:
    """Stretch the source eyelids toward their closure line with fixed patch edges."""
    left, top, right, bottom = eye.bounds
    padding = 4
    box = (left - padding, top - padding, right + padding, bottom + padding)
    source_patch = np.asarray(source.crop(box), dtype=np.uint8)
    height, width = source_patch.shape[:2]
    local_y, local_x = np.indices((height, width), dtype=np.float32)
    global_x = local_x + box[0]
    global_y = local_y + box[1]
    lid_x = np.asarray([point[0] for point in eye.closed_lid], dtype=np.float32)
    lid_y = np.asarray([point[1] for point in eye.closed_lid], dtype=np.float32)
    closure_y = np.interp(global_x, lid_x, lid_y, left=lid_y[0], right=lid_y[-1]).astype(np.float32)
    upper_denominator = np.maximum(closure_y - top, 1.0)
    lower_denominator = np.maximum(bottom - closure_y, 1.0)
    upper_source = top + (global_y - top) * (eye.upper_skin_y - top) / upper_denominator
    lower_source = eye.lower_skin_y + (global_y - closure_y) * (bottom - eye.lower_skin_y) / lower_denominator
    closed_source_y = np.where(global_y <= closure_y, upper_source, lower_source)
    horizontal = np.clip((global_x - left) / max(right - left, 1), 0.0, 1.0)
    horizontal_weight = np.clip(np.sin(np.pi * horizontal), 0.0, 1.0) ** 0.35
    source_y = global_y + progress * horizontal_weight * (closed_source_y - global_y)
    map_x = local_x
    map_y = np.clip(source_y - box[1], 0, height - 1).astype(np.float32)
    warped = cv2.remap(source_patch, map_x, map_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(warped, mode="RGBA")


def _draw_antialiased_lids(
    overlay: Image.Image,
    geometries: tuple[tuple[EyeGeometry, tuple[tuple[int, int], ...]], ...],
) -> None:
    combined = (350, 175, 540, 292)
    scale = 4
    layer = Image.new("RGBA", ((combined[2] - combined[0]) * scale, (combined[3] - combined[1]) * scale), 0)
    draw = ImageDraw.Draw(layer)
    for eye, points in geometries:
        local = [((x - combined[0]) * scale, (y - combined[1]) * scale) for x, y in points]
        draw.line(local, fill=(132, 77, 91, 105), width=4 * scale, joint="curve")
        draw.line(local, fill=(55, 38, 48, 235), width=2 * scale, joint="curve")
    layer = layer.resize((combined[2] - combined[0], combined[3] - combined[1]), Image.Resampling.LANCZOS)
    overlay.alpha_composite(layer, (combined[0], combined[1]))


def build_open(source: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", CANVAS_SIZE, 0)
    for eye in EYES:
        mask = _polygon_mask(eye.full_polygon).point(lambda value: 255 if value >= 128 else 0)
        opaque_source = source.getchannel("A").point(lambda value: 255 if value == 255 else 0)
        mask = ImageChops.multiply(mask, opaque_source)
        overlay.paste(source, (0, 0), mask)
    return overlay


def build_lid(source: Image.Image, *, closed: bool) -> Image.Image:
    overlay = Image.new("RGBA", CANVAS_SIZE, 0)
    lid_geometries = []
    for eye in EYES:
        points = eye.full_polygon if closed else eye.half_polygon
        hard_mask = Image.new("L", CANVAS_SIZE, 0)
        ImageDraw.Draw(hard_mask).polygon(points, fill=255)
        warped_patch = _warp_eye(source, eye, progress=1.0 if closed else 0.58)
        feathered = hard_mask.filter(ImageFilter.GaussianBlur(FEATHER_RADIUS))
        left, top, _right, _bottom = eye.bounds
        padding = 4
        patch_box = (left - padding, top - padding, left - padding + warped_patch.width,
                     top - padding + warped_patch.height)
        overlay.paste(warped_patch, (patch_box[0], patch_box[1]), feathered.crop(patch_box))
        lid_geometries.append((eye, eye.closed_lid if closed else eye.half_lid))
    _draw_antialiased_lids(overlay, tuple(lid_geometries))
    return overlay


def _alpha_bounds(image: Image.Image) -> tuple[int, int, int, int]:
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise RuntimeError("Generated blink overlay is fully transparent.")
    return bounds


def build_assets() -> dict[str, object]:
    before_hash = sha256(FULLBODY_RUNTIME_MASTER)
    if before_hash != EXPECTED_MASTER_SHA256:
        raise RuntimeError(f"Protected master hash mismatch before blink build: {before_hash}")
    with Image.open(FULLBODY_RUNTIME_MASTER) as image:
        image.verify()
    with Image.open(FULLBODY_RUNTIME_MASTER) as image:
        if image.size != CANVAS_SIZE or image.mode != "RGBA":
            raise RuntimeError("Protected master must remain a 1024x1536 RGBA PNG.")
        source = image.copy()

    BLINK_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    BLINK_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    BLINK_DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    open_overlay = build_open(source)
    half_overlay = build_lid(source, closed=False)
    closed_overlay = build_lid(source, closed=True)
    overlays = {
        "blink_open.png": open_overlay,
        "blink_half_closed.png": half_overlay,
        "blink_closed.png": closed_overlay,
        "blink_half_open.png": half_overlay.copy(),
    }
    report_frames: dict[str, object] = {}
    for name, overlay in overlays.items():
        path = BLINK_FRAMES_DIR / name
        overlay.save(path, format="PNG", optimize=True)
        report_frames[name] = {
            "sha256": sha256(path),
            "size": list(overlay.size),
            "mode": overlay.mode,
            "alpha_bounds": list(_alpha_bounds(overlay)),
            "file_size_bytes": path.stat().st_size,
            "semantic_drawing": name not in {"blink_open.png"},
        }

    eye_report = {
        "schema_version": 1,
        "source_asset": str(FULLBODY_RUNTIME_MASTER.resolve()),
        "source_asset_sha256": before_hash,
        "canvas": {"width": CANVAS_SIZE[0], "height": CANVAS_SIZE[1]},
        "eyes": {
            eye.name: {
                "bounds": list(eye.bounds),
                "full_polygon": [list(point) for point in eye.full_polygon],
                "half_polygon": [list(point) for point in eye.half_polygon],
            }
            for eye in EYES
        },
        "combined_approved_bounds": [350, 175, 540, 292],
        "feather_edge_source_pixels": FEATHER_RADIUS,
        "minimum_distance_to_hair_source_pixels": 1,
        "minimum_distance_to_face_edge_source_pixels": 52,
        "excluded_features": ["bangs", "nose", "mouth", "face_contour", "ears", "hair_edge"],
        "frames": report_frames,
        "method": "source eye extraction plus edge-fixed local eyelid warping and antialiased hand-authored lid paths",
    }
    report_path = BLINK_DIAGNOSTICS_DIR / "blink_eye_region.json"
    report_path.write_text(json.dumps(eye_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    after_hash = sha256(FULLBODY_RUNTIME_MASTER)
    if after_hash != before_hash:
        raise RuntimeError("Protected master changed while building blink overlays.")
    return eye_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="build and print a compact validation summary")
    parser.parse_args()
    report = build_assets()
    print(f"protected master: {report['source_asset_sha256']}")
    for name, details in report["frames"].items():
        print(f"{name}: {details['sha256']} bounds={details['alpha_bounds']} bytes={details['file_size_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
