"""Build the transparent multi-resolution Windows icon from the approved cached design."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from desktop_pet.paths import ASSETS_DIR, FULLBODY_RUNTIME_MASTER
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICON_PATH = ASSETS_DIR / "icons" / "desktop_pet.ico"
PREVIEW_PATH = ASSETS_DIR / "icons" / "desktop_pet_icon_preview.png"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build_icon() -> tuple[Path, Path]:
    before_hash = _sha256(FULLBODY_RUNTIME_MASTER)
    if before_hash != EXPECTED_RUNTIME_ASSET_SHA256:
        raise ValueError(f"Approved runtime asset hash mismatch: {before_hash}")
    with Image.open(FULLBODY_RUNTIME_MASTER) as source:
        source.verify()
    with Image.open(FULLBODY_RUNTIME_MASTER) as source:
        if source.format != "PNG" or source.mode != "RGBA":
            raise ValueError("Approved runtime asset must remain an RGBA PNG.")
        alpha_bounds = source.getchannel("A").getbbox()
        if alpha_bounds is None:
            raise ValueError("Approved runtime asset is fully transparent.")
        character = source.crop(alpha_bounds).copy()

    canvas_size = 1024
    margin = 72
    available = canvas_size - 2 * margin
    scale = min(available / character.width, available / character.height)
    target_size = (max(1, round(character.width * scale)), max(1, round(character.height * scale)))
    character = character.resize(target_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.alpha_composite(character, ((canvas_size - character.width) // 2, (canvas_size - character.height) // 2))

    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(ICON_PATH, format="ICO", sizes=[(size, size) for size in ICON_SIZES], bitmap_format="png")
    canvas.resize((512, 512), Image.Resampling.LANCZOS).save(PREVIEW_PATH, format="PNG")

    with Image.open(ICON_PATH) as icon:
        available_sizes = {size[0] for size in icon.ico.sizes()}
        missing = set(ICON_SIZES) - available_sizes
        if missing:
            raise ValueError(f"ICO is missing required sizes: {sorted(missing)}")
    after_hash = _sha256(FULLBODY_RUNTIME_MASTER)
    if after_hash != before_hash:
        raise RuntimeError("Approved runtime asset changed while building the icon.")
    return ICON_PATH, PREVIEW_PATH


def main() -> int:
    icon_path, preview_path = build_icon()
    print(f"Application icon: {icon_path}")
    print(f"Icon preview: {preview_path}")
    print(f"Source SHA-256 unchanged: {EXPECTED_RUNTIME_ASSET_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
