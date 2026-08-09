"""Build the Stage 4 comparison board and traceable manifest from full-body candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from desktop_pet.paths import (
    FULLBODY_CONCEPTS_DIR,
    FULLBODY_REPORTS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_ORIGINAL_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
STAGE_THREE_HASHES = {
    "assets/processed/base/character_cutout_rgba.png": (
        "4007456A5460A3A2A2DCCC48303A5E323C465B7488F03898343394841D671F99"
    ),
    "assets/processed/base/character_runtime_master.png": (
        "7E5BF9CD7705416B3F0BB310CD3EAA0A1395470D1DBFC9DB010E80969E7242C8"
    ),
}
COMPARISON_PATH = FULLBODY_CONCEPTS_DIR / "fullbody_concept_comparison.png"
MANIFEST_PATH = FULLBODY_REPORTS_DIR / "fullbody_concept_manifest.json"
MINIMUM_MASTER_SIZE = (1024, 1536)
CONCEPTS = (
    {
        "id": "A",
        "filename": "fullbody_concept_a.png",
        "name": "严格保守延伸",
        "head_ratio": "约 5.0 头身",
        "outfit": "简洁深色褶裙、单道红色裙边、深灰长袜、红扣短靴",
        "animation": "高：紧凑、直立、双脚清楚，适合后续轻晃与行走",
        "risk": "细发丝和键控边缘仍需用户最终视觉确认",
        "recommended": True,
    },
    {
        "id": "B",
        "filename": "fullbody_concept_b.png",
        "name": "均衡桌宠设计",
        "head_ratio": "约 5.1 头身",
        "outfit": "双层深色裙装、红色腰带与裙边、深灰长袜、红扣短靴",
        "animation": "高：略三分之四重心，轮廓与层次均衡",
        "risk": "下装层次较 A 更多，缩小显示时需要进一步评估",
        "recommended": False,
    },
    {
        "id": "C",
        "filename": "fullbody_concept_c.png",
        "name": "轻度 Q 版设计",
        "head_ratio": "约 4.5 头身",
        "outfit": "紧凑深色短裙、简化红腰带、灰紫长袜、红扣短靴",
        "animation": "高：前向稳定站姿，适合较小尺寸桌宠",
        "risk": "头身比例更短，需要用户确认是否仍足够贴近原图气质",
        "recommended": False,
    },
)


def sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def relative_path(path: Path) -> str:
    """Return a manifest-friendly project-relative Windows path."""
    return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")


def load_font(size: int) -> ImageFont.ImageFont:
    """Load a Windows UI font, with Pillow's default as the safe fallback."""
    for font_path in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ):
        if font_path.is_file():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def checkerboard(size: tuple[int, int], square_size: int = 28) -> Image.Image:
    """Create a neutral transparency checkerboard for the comparison board."""
    canvas = Image.new("RGB", size, "#E5E7EB")
    drawing = ImageDraw.Draw(canvas)
    for top in range(0, size[1], square_size):
        for left in range(0, size[0], square_size):
            if (left // square_size + top // square_size) % 2:
                drawing.rectangle(
                    (left, top, left + square_size - 1, top + square_size - 1),
                    fill="#BCC4CF",
                )
    return canvas


def verified_rgba(path: Path) -> Image.Image:
    """Verify and return an RGBA copy without leaving the input file open."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.convert("RGBA").copy()


def normalize_candidate_canvas(path: Path) -> dict[str, Any]:
    """Add transparent padding only when a generated candidate misses the minimum canvas size."""
    image = verified_rgba(path)
    target_width = max(image.width, MINIMUM_MASTER_SIZE[0])
    target_height = max(image.height, MINIMUM_MASTER_SIZE[1])
    if (target_width, target_height) == image.size:
        return {"path": relative_path(path), "normalized": False, "resize_applied": False}

    padded = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    offset = ((target_width - image.width) // 2, (target_height - image.height) // 2)
    padded.alpha_composite(image, offset)
    padded.save(path, format="PNG")
    return {
        "path": relative_path(path),
        "normalized": True,
        "resize_applied": False,
        "source_canvas": {"width": image.width, "height": image.height},
        "normalized_canvas": {"width": target_width, "height": target_height},
        "transparent_padding_offset": {"x": offset[0], "y": offset[1]},
    }


def alpha_metadata(path: Path, concept: dict[str, Any]) -> dict[str, Any]:
    """Collect image metadata and safe-margin facts for one candidate."""
    with Image.open(path) as opened_image:
        input_mode = opened_image.mode
        has_alpha = input_mode in {"RGBA", "LA"} or "transparency" in opened_image.info
    image = verified_rgba(path)
    alpha = np.asarray(image.getchannel("A"))
    bbox = Image.fromarray(alpha, mode="L").getbbox()
    if bbox is None:
        raise RuntimeError(f"Full-body candidate is fully transparent: {path}")
    left, top, right, bottom = bbox
    return {
        "path": relative_path(path),
        "sha256": sha256(path),
        "width": image.width,
        "height": image.height,
        "mode": input_mode,
        "has_alpha": has_alpha,
        "is_complete_figure": True,
        "final_asset": False,
        "head_ratio": concept["head_ratio"],
        "design_plan": concept["id"],
        "design_name": concept["name"],
        "inferred_design": True,
        "known_issues": [concept["risk"]],
        "alpha_pixel_counts": {
            "transparent": int(np.count_nonzero(alpha == 0)),
            "semi_transparent": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
            "opaque": int(np.count_nonzero(alpha == 255)),
        },
        "visible_alpha_bbox": {"left": left, "top": top, "right": right, "bottom": bottom},
        "transparent_safe_margin_pixels": {
            "left": left,
            "top": top,
            "right": image.width - right,
            "bottom": image.height - bottom,
        },
    }


def comparison_metadata(path: Path) -> dict[str, Any]:
    """Collect normal image metadata for the opaque visual comparison board."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return {
            "path": relative_path(path),
            "sha256": sha256(path),
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "has_alpha": image.mode in {"RGBA", "LA"} or "transparency" in image.info,
            "purpose": "three-candidate visual comparison",
        }


def build_comparison_board() -> None:
    """Render all three transparent candidates beside their concise design differences."""
    board = Image.new("RGB", (2100, 1220), "#F4F6F8")
    drawing = ImageDraw.Draw(board)
    title_font = load_font(38)
    subtitle_font = load_font(24)
    label_font = load_font(28)
    detail_font = load_font(20)
    drawing.text((48, 34), "完整人物设计候选对比（均为推定设计，非最终素材）", font=title_font, fill="#18212F")
    drawing.text(
        (48, 85),
        "唯一身份参考：原始上半身图。推荐 A：最保守地延续既有轮廓、配色和服装语言。",
        font=subtitle_font,
        fill="#465366",
    )

    tile_width = 650
    for index, concept in enumerate(CONCEPTS):
        left = 36 + index * 690
        top = 140
        drawing.rounded_rectangle(
            (left, top, left + tile_width, 1166),
            radius=18,
            fill="#FFFFFF",
            outline="#C8D0DC",
            width=2,
        )
        image = verified_rgba(FULLBODY_CONCEPTS_DIR / concept["filename"])
        background = checkerboard((tile_width - 48, 760)).convert("RGBA")
        preview = image.copy()
        preview.thumbnail((480, 720), Image.Resampling.LANCZOS)
        preview_left = (background.width - preview.width) // 2
        preview_top = (background.height - preview.height) // 2
        background.alpha_composite(preview, (preview_left, preview_top))
        board.paste(background.convert("RGB"), (left + 24, top + 24))
        drawing.text((left + 28, 942), f"方案 {concept['id']}｜{concept['name']}", font=label_font, fill="#172033")
        details = (
            f"比例：{concept['head_ratio']}",
            f"下装与鞋袜：{concept['outfit']}",
            f"动画适配：{concept['animation']}",
            f"风险：{concept['risk']}",
        )
        for row, detail in enumerate(details):
            drawing.text((left + 30, 992 + row * 41), detail, font=detail_font, fill="#3E4A5D")
        if concept["recommended"]:
            drawing.rounded_rectangle((left + 448, 938, left + 620, 980), radius=15, fill="#FDE68A")
            drawing.text((left + 468, 947), "推荐", font=detail_font, fill="#78350F")
    board.save(COMPARISON_PATH, format="PNG")


def verify_reference_integrity() -> dict[str, Any]:
    """Report that the source copy and Stage 3 references still match their baselines."""
    original_hash = sha256(ORIGINAL_CHARACTER_IMAGE)
    if original_hash != EXPECTED_ORIGINAL_SHA256:
        raise RuntimeError("Project original copy hash does not match the approved baseline.")
    stage_three = []
    for relative, expected_hash in STAGE_THREE_HASHES.items():
        path = PROJECT_ROOT / Path(relative)
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"Stage 3 reference asset changed: {relative}")
        stage_three.append({"path": relative.replace("/", "\\"), "sha256": actual_hash, "unchanged": True})
    return {
        "project_original_copy_sha256": original_hash,
        "original_copy_unchanged": True,
        "stage_three_reference_assets": stage_three,
    }


def build_manifest() -> None:
    """Write the Stage 4 candidate manifest without promoting any image to final."""
    FULLBODY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    canvas_normalization = []
    for concept in CONCEPTS:
        path = FULLBODY_CONCEPTS_DIR / concept["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing full-body candidate: {path}")
        canvas_normalization.append(normalize_candidate_canvas(path))
    build_comparison_board()
    concept_records = []
    for concept in CONCEPTS:
        path = FULLBODY_CONCEPTS_DIR / concept["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing full-body candidate: {path}")
        concept_records.append(alpha_metadata(path, concept))
    manifest = {
        "stage": 4,
        "status": "fullbody_design_candidates_pending_user_confirmation",
        "source_role": "upper_body_identity_reference_only",
        "inferred_design_notice": (
            "All lower-body, footwear, and full-body proportions are inferred design, "
            "not facts visible in the source image."
        ),
        "generation_method": (
            "reference-guided image generation on magenta chroma background, "
            "then local chroma-key alpha extraction"
        ),
        "canvas_normalization": canvas_normalization,
        "reference_integrity": verify_reference_integrity(),
        "concepts": concept_records,
        "comparison": comparison_metadata(COMPARISON_PATH),
        "recommendation": {
            "plan": "A",
            "final_asset": False,
            "reason": "Most conservative continuation of the original visual language.",
        },
        "runtime_status": {
            "fullbody_runtime_master_created": False,
            "stage_three_upper_body_assets_are_final_runtime_assets": False,
            "transparent_window_implemented": False,
            "animation_created": False,
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Generate the comparison board and full-body candidate manifest."""
    parser = argparse.ArgumentParser(description="Build full-body concept comparison and manifest.")
    parser.parse_args(argv)
    build_manifest()
    print(f"Comparison: {relative_path(COMPARISON_PATH)}")
    print(f"Manifest: {relative_path(MANIFEST_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
