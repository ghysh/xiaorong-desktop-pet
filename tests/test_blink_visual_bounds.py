"""Blink overlays stay on the approved canvas and local eye region."""

from __future__ import annotations

import hashlib
import json

from PIL import Image, ImageChops

from desktop_pet.paths import BLINK_DIAGNOSTICS_DIR, BLINK_FRAMES_DIR, FULLBODY_RUNTIME_MASTER
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256

EXPECTED_FRAMES = {
    "blink_open.png",
    "blink_half_closed.png",
    "blink_closed.png",
    "blink_half_open.png",
}


def test_all_overlays_are_sparse_full_canvas_rgba_inside_approved_eye_bounds() -> None:
    report = json.loads((BLINK_DIAGNOSTICS_DIR / "blink_eye_region.json").read_text(encoding="utf-8"))
    approved = tuple(report["combined_approved_bounds"])
    assert set(path.name for path in BLINK_FRAMES_DIR.glob("*.png")) == EXPECTED_FRAMES
    for path in BLINK_FRAMES_DIR.glob("*.png"):
        with Image.open(path) as image:
            assert image.size == (1024, 1536)
            assert image.mode == "RGBA"
            bounds = image.getchannel("A").getbbox()
            assert bounds is not None
            assert approved[0] <= bounds[0] < bounds[2] <= approved[2]
            assert approved[1] <= bounds[1] < bounds[3] <= approved[3]
            assert sum(image.getchannel("A").histogram()[1:]) < 20_000


def test_open_overlay_composite_is_pixel_exact_and_master_hash_is_unchanged() -> None:
    assert hashlib.sha256(FULLBODY_RUNTIME_MASTER.read_bytes()).hexdigest().upper() == EXPECTED_RUNTIME_ASSET_SHA256
    with Image.open(FULLBODY_RUNTIME_MASTER) as image:
        source = image.convert("RGBA")
    with Image.open(BLINK_FRAMES_DIR / "blink_open.png") as image:
        composite = Image.alpha_composite(source, image.convert("RGBA"))
    assert ImageChops.difference(source, composite).getbbox() is None


def test_nose_mouth_face_edges_and_canvas_edges_are_outside_overlay_bounds() -> None:
    with Image.open(BLINK_FRAMES_DIR / "blink_closed.png") as image:
        alpha = image.getchannel("A")
        assert alpha.getpixel((500, 300)) == 0
        assert alpha.getpixel((500, 345)) == 0
        assert alpha.getpixel((350, 250)) == 0
        assert alpha.getpixel((0, 0)) == 0
        assert alpha.getpixel((1023, 1535)) == 0
