"""Generate non-destructive analysis artefacts for the fixed character source image."""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from desktop_pet.paths import (
    ANALYSIS_PREVIEWS_DIR,
    ANALYSIS_REPORTS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_SOURCE_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
PALETTE_COLOR_COUNT = 12
SUBJECT_DISTANCE_THRESHOLD = 40.0
DISPLAY_SIZES = (160, 200, 240, 280, 320)


def sha256(path: Path) -> str:
    """Return a file hash without changing the file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rgb_hex(color: tuple[int, int, int]) -> str:
    """Format an RGB triple as a hex colour."""
    return "#{:02X}{:02X}{:02X}".format(*color)


def color_distance(
    first: tuple[int, int, int], second: tuple[int, int, int]
) -> float:
    """Calculate Euclidean distance in RGB space."""
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(first, second)))


def median_color(colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    """Return the per-channel median colour for a non-empty sample."""
    return tuple(round(statistics.median(channel)) for channel in zip(*colors))


def percentile(values: list[float], percent: float) -> float:
    """Return a nearest-rank percentile without external dependencies."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, round((len(sorted_values) - 1) * percent))
    return sorted_values[index]


def edge_samples(image: Image.Image) -> dict[str, list[tuple[int, int, int]]]:
    """Collect RGB samples from each outer image edge."""
    rgb_image = image.convert("RGB")
    pixels = rgb_image.load()
    width, height = rgb_image.size
    return {
        "top": [pixels[x, 0] for x in range(width)],
        "bottom": [pixels[x, height - 1] for x in range(width)],
        "left": [pixels[0, y] for y in range(height)],
        "right": [pixels[width - 1, y] for y in range(height)],
    }


def infer_palette_role(
    color: tuple[int, int, int], background: tuple[int, int, int]
) -> str:
    """Return a conservative, non-semantic palette role."""
    distance = color_distance(color, background)
    brightness = sum(color) / 3
    if distance <= SUBJECT_DISTANCE_THRESHOLD:
        return "possibly_background"
    if brightness < 105:
        return "possibly_outline_or_shadow"
    if brightness > 210:
        return "requires_visual_confirmation"
    return "possibly_character_subject"


def extract_palette(
    image: Image.Image, background: tuple[int, int, int]
) -> list[dict[str, Any]]:
    """Quantize the image and report the most common representative colours."""
    rgb_image = image.convert("RGB")
    quantized = rgb_image.quantize(
        colors=PALETTE_COLOR_COUNT,
        method=Image.Quantize.MEDIANCUT,
    )
    palette_data = quantized.getpalette()
    color_counts = quantized.getcolors(maxcolors=PALETTE_COLOR_COUNT)
    if palette_data is None or color_counts is None:
        raise RuntimeError("Palette extraction did not produce usable colour data.")

    total_pixels = image.width * image.height
    entries: list[dict[str, Any]] = []
    for count, palette_index in sorted(color_counts, reverse=True):
        offset = palette_index * 3
        color = tuple(palette_data[offset : offset + 3])
        entries.append(
            {
                "rgb": list(color),
                "hex": rgb_hex(color),
                "pixel_count": count,
                "ratio": round(count / total_pixels, 6),
                "suggested_use": infer_palette_role(color, background),
                "confidence": "low",
                "note": "Automated quantization result; visual confirmation required.",
            }
        )
    return entries


def estimate_subject_bounds(
    image: Image.Image, background: tuple[int, int, int]
) -> dict[str, Any]:
    """Estimate a subject range from RGB distance, without producing a mask."""
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    pixels = rgb_image.load()
    foreground_coordinates: list[tuple[int, int]] = []

    for y in range(height):
        for x in range(width):
            color = pixels[x, y]
            if color_distance(color, background) > SUBJECT_DISTANCE_THRESHOLD:
                foreground_coordinates.append((x, y))

    if not foreground_coordinates:
        return {
            "label": "estimated_subject_range",
            "reliable": False,
            "confidence": "low",
            "notes": ["No pixels exceeded the background-distance threshold."],
        }

    xs, ys = zip(*foreground_coordinates)
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    subject_width = right - left + 1
    subject_height = bottom - top + 1
    margins = {
        "left": left,
        "right": width - 1 - right,
        "top": top,
        "bottom": height - 1 - bottom,
    }
    touches_edge = any(value == 0 for value in margins.values())
    margin_limit = max(12, round(min(width, height) * 0.08))
    limited_expansion_space = any(value < margin_limit for value in margins.values())
    coverage = len(foreground_coordinates) / (width * height)

    return {
        "label": "estimated_subject_range",
        "x": left,
        "y": top,
        "width": subject_width,
        "height": subject_height,
        "right": right,
        "bottom": bottom,
        "margins": margins,
        "foreground_pixel_ratio": round(coverage, 6),
        "touches_canvas_edge": touches_edge,
        "limited_future_action_space": limited_expansion_space,
        "distance_threshold": SUBJECT_DISTANCE_THRESHOLD,
        "reliable": not touches_edge,
        "confidence": "medium" if not touches_edge else "low",
        "notes": [
            "This is an RGB-distance estimate, not a mask or an exact segmentation.",
            "Pixels similar to the edge-derived background may be excluded.",
        ],
    }


def analyse_background(image: Image.Image) -> dict[str, Any]:
    """Summarise edge colours and conservative background-removal feasibility."""
    samples_by_side = edge_samples(image)
    all_samples = [color for samples in samples_by_side.values() for color in samples]
    representative = median_color(all_samples)
    distances = [color_distance(color, representative) for color in all_samples]
    average_distance = statistics.mean(distances)
    upper_distance = percentile(distances, 0.95)
    uniformity = "relatively_uniform" if upper_distance <= 25 else "mixed_edge_colours"
    corners = {
        "top_left": list(image.convert("RGB").getpixel((0, 0))),
        "top_right": list(image.convert("RGB").getpixel((image.width - 1, 0))),
        "bottom_left": list(image.convert("RGB").getpixel((0, image.height - 1))),
        "bottom_right": list(
            image.convert("RGB").getpixel((image.width - 1, image.height - 1))
        ),
    }
    bounds = estimate_subject_bounds(image, representative)
    foreground_ratio = bounds.get("foreground_pixel_ratio", 0.0)
    if uniformity == "relatively_uniform" and not bounds.get("touches_canvas_edge"):
        difficulty = "low"
    elif uniformity == "relatively_uniform" and foreground_ratio > 0:
        difficulty = "medium"
    elif foreground_ratio > 0:
        difficulty = "high"
    else:
        difficulty = "unable_to_determine_automatically"

    return {
        "corner_colors": corners,
        "edge_representative_colors": {
            side: {"rgb": list(median_color(colors)), "hex": rgb_hex(median_color(colors))}
            for side, colors in samples_by_side.items()
        },
        "edge_background_candidate": {
            "rgb": list(representative),
            "hex": rgb_hex(representative),
        },
        "edge_uniformity": uniformity,
        "mean_edge_distance": round(average_distance, 3),
        "p95_edge_distance": round(upper_distance, 3),
        "possible_near_solid_background": uniformity == "relatively_uniform",
        "estimated_removal_difficulty": difficulty,
        "confidence": "medium" if uniformity == "relatively_uniform" else "low",
        "notes": [
            "Edge statistics only assess feasibility; no background removal was performed.",
            "Light subject regions similar to the edge background require visual confirmation.",
        ],
        "estimated_subject_bounds": bounds,
    }


def display_size_options(width: int, height: int) -> list[dict[str, Any]]:
    """Provide evidence-led logical display size candidates."""
    options: list[dict[str, Any]] = []
    for size in DISPLAY_SIZES:
        scale = size / max(width, height)
        operation = "downscale" if scale < 1 else "upscale" if scale > 1 else "native"
        if scale <= 0.7:
            clarity = "high_for_silhouette; fine_detail_reduced"
            detail = "limited"
        elif scale <= 1:
            clarity = "high"
            detail = "good"
        else:
            clarity = "interpolated_upscale; inspect_before_use"
            detail = "not_increased_by_scaling"
        recommendation = "candidate_default" if size == 240 else "comparison_option"
        options.append(
            {
                "width": size,
                "height": size,
                "scale_factor": round(scale, 4),
                "operation": operation,
                "expected_clarity": clarity,
                "detail_visibility": detail,
                "desktop_footprint": "small" if size <= 200 else "medium" if size <= 280 else "large",
                "recommendation": recommendation,
                "user_confirmation_required": True,
            }
        )
    return options


def font(size: int) -> ImageFont.ImageFont:
    """Load a Windows CJK font when available, with a Pillow fallback."""
    windows_directory = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = (
        windows_directory / "Fonts" / "msyh.ttc",
        windows_directory / "Fonts" / "simhei.ttf",
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def draw_centered_text(
    drawing: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    """Draw one line horizontally centred inside a box."""
    left, top, right, _ = box
    text_box = drawing.textbbox((0, 0), text, font=text_font)
    x = left + (right - left - (text_box[2] - text_box[0])) / 2
    drawing.text((x, top), text, font=text_font, fill=fill)


def save_enlarged_reference(image: Image.Image, destination: Path) -> None:
    """Save a three-times LANCZOS inspection preview without altering the source."""
    enlarged = image.convert("RGB").resize(
        (image.width * 3, image.height * 3), Image.Resampling.LANCZOS
    )
    enlarged.save(destination, format="PNG")


def save_palette_preview(palette: list[dict[str, Any]], destination: Path) -> None:
    """Render the automated palette as a review-only chart."""
    row_height = 94
    canvas = Image.new("RGB", (1320, 130 + row_height * len(palette)), "#F4F6F8")
    drawing = ImageDraw.Draw(canvas)
    title_font = font(34)
    body_font = font(22)
    drawing.text(
        (38, 26),
        "角色配色统计（自动统计结果，需视觉确认）",
        font=title_font,
        fill="#1F2937",
    )
    for index, entry in enumerate(palette):
        top = 100 + index * row_height
        color = tuple(entry["rgb"])
        drawing.rounded_rectangle((38, top, 250, top + 62), radius=10, fill=color)
        drawing.rectangle((38, top, 250, top + 62), outline="#374151", width=2)
        drawing.text(
            (280, top + 4),
            f"{index + 1:02d}  {entry['hex']}  RGB{tuple(entry['rgb'])}",
            font=body_font,
            fill="#111827",
        )
        drawing.text(
            (780, top + 4),
            f"占比 {entry['ratio'] * 100:.2f}%",
            font=body_font,
            fill="#111827",
        )
        drawing.text(
            (1010, top + 4),
            entry["suggested_use"],
            font=body_font,
            fill="#4B5563",
        )
    canvas.save(destination, format="PNG")


def save_composition_preview(
    image: Image.Image, bounds: dict[str, Any], destination: Path
) -> None:
    """Render a grid and explicitly labelled estimated range on a derived preview."""
    scale = 2
    preview = image.convert("RGB").resize(
        (image.width * scale, image.height * scale), Image.Resampling.LANCZOS
    )
    overlay = Image.new("RGBA", preview.size, (0, 0, 0, 0))
    drawing = ImageDraw.Draw(overlay)
    width, height = preview.size
    grid_color = (59, 130, 246, 170)
    center_color = (239, 68, 68, 210)
    for fraction in (1 / 3, 2 / 3):
        drawing.line((round(width * fraction), 0, round(width * fraction), height), fill=grid_color, width=2)
        drawing.line((0, round(height * fraction), width, round(height * fraction)), fill=grid_color, width=2)
    drawing.line((width // 2, 0, width // 2, height), fill=center_color, width=3)
    drawing.line((0, height // 2, width, height // 2), fill=center_color, width=3)

    if bounds.get("reliable") is not None and "x" in bounds:
        left = bounds["x"] * scale
        top = bounds["y"] * scale
        right = (bounds["right"] + 1) * scale - 1
        bottom = (bounds["bottom"] + 1) * scale - 1
        drawing.rectangle((left, top, right, bottom), outline=(245, 158, 11, 255), width=4)
        label_font = font(24)
        drawing.rounded_rectangle(
            (left + 6, top + 6, left + 150, top + 42),
            radius=5,
            fill=(245, 158, 11, 230),
        )
        drawing.text((left + 12, top + 9), "估计范围", font=label_font, fill="#111827")

    preview = Image.alpha_composite(preview.convert("RGBA"), overlay).convert("RGB")
    preview.save(destination, format="PNG")


def save_size_comparison(image: Image.Image, destination: Path) -> None:
    """Render un-cropped, same-method display-size comparisons."""
    columns = 3
    cell_width = 380
    cell_height = 420
    canvas = Image.new("RGB", (columns * cell_width, 2 * cell_height + 86), "#D9DEE5")
    drawing = ImageDraw.Draw(canvas)
    title_font = font(32)
    label_font = font(23)
    drawing.text(
        (32, 24),
        "桌宠逻辑显示尺寸对比（RGB 原图；未去背景）",
        font=title_font,
        fill="#1F2937",
    )
    for index, size in enumerate(DISPLAY_SIZES):
        column = index % columns
        row = index // columns
        cell_left = column * cell_width
        cell_top = 86 + row * cell_height
        scaled = image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        x = cell_left + (cell_width - size) // 2
        y = cell_top + 28
        canvas.paste(scaled, (x, y))
        draw_centered_text(
            drawing,
            (cell_left, cell_top + size + 42, cell_left + cell_width, cell_top + size + 70),
            f"{size} × {size}",
            label_font,
            "#111827",
        )
    canvas.save(destination, format="PNG")


def save_review_board(
    image: Image.Image,
    report: dict[str, Any],
    destination: Path,
) -> None:
    """Render a compact review board for human confirmation, not application use."""
    canvas = Image.new("RGB", (1640, 1050), "#F3F5F7")
    drawing = ImageDraw.Draw(canvas)
    title_font = font(38)
    section_font = font(27)
    body_font = font(22)
    small_font = font(19)
    drawing.text((40, 30), "角色视觉分析总览（评审草案）", font=title_font, fill="#111827")

    preview = image.convert("RGB").resize((500, 500), Image.Resampling.LANCZOS)
    canvas.paste(preview, (48, 116))
    drawing.rectangle((48, 116, 548, 616), outline="#9CA3AF", width=2)
    drawing.text((48, 636), "原图预览：仅缩放查看，未去背景", font=body_font, fill="#374151")

    source = report["source"]
    background = report["background_analysis"]
    bounds = report["composition"]["estimated_subject_bounds"]
    drawing.text((610, 116), "基础信息", font=section_font, fill="#111827")
    technical_lines = (
        f"{source['format']} · {source['size']['width']} × {source['size']['height']} · {source['mode']}",
        f"Alpha：{source['has_alpha']} · 纵横比：{source['aspect_ratio']:.4f}",
        f"背景候选：{background['edge_background_candidate']['hex']}",
        f"背景去除难度（算法估计）：{background['estimated_removal_difficulty']}",
        f"主体估计范围：{bounds.get('width', '—')} × {bounds.get('height', '—')}",
        "默认候选：240 × 240（待用户确认）",
    )
    for index, line in enumerate(technical_lines):
        drawing.text((610, 160 + index * 34), line, font=body_font, fill="#374151")

    drawing.text((610, 386), "自动配色统计（需视觉确认）", font=section_font, fill="#111827")
    for index, entry in enumerate(report["palette"][:8]):
        x = 610 + (index % 4) * 230
        y = 430 + (index // 4) * 114
        color = tuple(entry["rgb"])
        drawing.rounded_rectangle((x, y, x + 194, y + 58), radius=9, fill=color)
        drawing.rectangle((x, y, x + 194, y + 58), outline="#4B5563", width=1)
        drawing.text((x, y + 65), entry["hex"], font=small_font, fill="#111827")
        drawing.text(
            (x, y + 89),
            f"{entry['ratio'] * 100:.2f}%",
            font=small_font,
            fill="#374151",
        )

    drawing.text((48, 718), "待用户确认", font=section_font, fill="#111827")
    pending_items = report["pending_user_confirmation"]
    for index, item in enumerate(pending_items):
        drawing.text((48, 762 + index * 36), f"• {item}", font=body_font, fill="#374151")
    drawing.text(
        (48, 978),
        "本图仅为分析评审，不是最终桌宠素材；未生成透明素材或动画。",
        font=body_font,
        fill="#6B7280",
    )
    canvas.save(destination, format="PNG")


def visual_identity_draft() -> dict[str, list[dict[str, str]]]:
    """Record observations from the source image without inventing unclear details."""
    return {
        "overall": [
            {
                "observation": "女性化日系二次元人物近景，正面略偏侧的上半身构图。",
                "evidence": "直接查看项目内原图。",
                "confidence": "high",
                "preserve": "yes",
            },
            {
                "observation": "视觉重心集中在大尺寸眼睛、头部和靠近脸部的双手。",
                "evidence": "直接查看项目内原图的构图。",
                "confidence": "high",
                "preserve": "yes",
            },
        ],
        "face": [
            {
                "observation": "大而圆润的粉紫调眼睛、深色上睫线、浅红面颊和小型嘴鼻构成柔和表情。",
                "evidence": "直接查看原图放大预览。",
                "confidence": "medium",
                "preserve": "yes",
            },
            {
                "observation": "精细的瞳孔纹理、眉毛与鼻部细节在当前分辨率下不宜作为精确复刻依据。",
                "evidence": "346 × 346 原图放大查看。",
                "confidence": "high",
                "preserve": "pending_user_confirmation",
            },
        ],
        "head": [
            {
                "observation": "深色长发以厚重刘海、左侧束发和向右展开的长发丝形成不对称轮廓。",
                "evidence": "直接查看原图轮廓。",
                "confidence": "high",
                "preserve": "yes",
            },
            {
                "observation": "红色发饰、发带或缎带位于左侧头部与头顶后侧，是高对比点缀。",
                "evidence": "直接查看原图。具体饰物结构受分辨率限制。",
                "confidence": "medium",
                "preserve": "yes",
            },
        ],
        "body": [
            {
                "observation": "画面呈上半身近景；双手在下颌前方靠拢，肢体被裁切且部分遮挡。",
                "evidence": "直接查看原图构图。",
                "confidence": "high",
                "preserve": "yes",
            },
        ],
        "clothing": [
            {
                "observation": "深灰至黑色服装配合浅灰/淡紫袖口与红色绑带、扣件细节。",
                "evidence": "直接查看原图与自动配色统计。",
                "confidence": "medium",
                "preserve": "yes",
            },
            {
                "observation": "服装完整结构、鞋袜与画外区域不可由当前单张近景确认。",
                "evidence": "原图下半身和边缘区域被裁切。",
                "confidence": "high",
                "preserve": "pending_user_confirmation",
            },
        ],
        "accessories": [
            {
                "observation": "可见红色点缀、深色背带/扣件和左下角的浅色图形细节。",
                "evidence": "直接查看原图。",
                "confidence": "medium",
                "preserve": "yes",
            },
        ],
        "style": [
            {
                "observation": "日系二次元插画风格；深色轮廓结合柔和渐变阴影、面部暖色晕染和细发丝高光。",
                "evidence": "直接查看三倍缩放预览。",
                "confidence": "high",
                "preserve": "yes",
            },
            {
                "observation": "线条、阴影和高光存在抗锯齿与软过渡；后续不应替换为硬边扁平矢量风。",
                "evidence": "直接查看原图边缘与明暗过渡。",
                "confidence": "high",
                "preserve": "yes",
            },
        ],
    }


def identity_rules() -> dict[str, list[dict[str, str]]]:
    """Return a source-observed preservation draft for later user confirmation."""
    return {
        "level_a": [
            {
                "feature": "深色不对称长发、厚重刘海和向右展开的发丝轮廓",
                "basis": "构成画面最大且最独特的外轮廓。",
                "confidence": "high",
            },
            {
                "feature": "粉紫调大眼睛、柔和面颊晕染和温和表情",
                "basis": "面部是当前构图的主要视觉重心。",
                "confidence": "high",
            },
            {
                "feature": "深色服装与红色点缀的高对比配色关系",
                "basis": "与深发色共同形成稳定的角色色彩识别。",
                "confidence": "medium",
            },
        ],
        "level_b": [
            {
                "feature": "下颌前双手靠拢的近景姿势",
                "basis": "是当前静态形象的重要姿势特征，但低改动动画可有轻微变化。",
                "confidence": "high",
            },
            {
                "feature": "红色头部点缀、深色背带和扣件关系",
                "basis": "可轻微变形，但应保留位置关系和视觉权重。",
                "confidence": "medium",
            },
        ],
        "level_c": [
            {
                "feature": "背景颜色与空白区",
                "basis": "背景不是角色身份组成；后续需经确认后处理为透明。",
                "confidence": "high",
            },
            {
                "feature": "画外身体、鞋袜和完整服装结构",
                "basis": "当前原图无法确认，任何补全均须待用户确认。",
                "confidence": "high",
            },
        ],
    }


def action_scope_draft() -> dict[str, list[dict[str, Any]]]:
    """Propose scope only; this function does not create animation materials."""
    return {
        "low_modification": [
            {
                "action": "轻微呼吸、上下浮动、左右轻晃",
                "method": "整体位移、缩放或极轻微形变",
                "identity_risk": "low",
                "confidence": "high",
            },
            {
                "action": "拖拽倾斜、点击缩放、落地弹性",
                "method": "整体变换，不新增角色像素",
                "identity_risk": "low",
                "confidence": "high",
            },
        ],
        "partial_redraw": [
            {
                "action": "眨眼、嘴部或表情微变化",
                "required_additions": "眼睑、瞳孔可见区、嘴部与局部阴影",
                "identity_risk": "medium",
                "confidence": "medium",
            },
            {
                "action": "头部轻微转动或手部小动作",
                "required_additions": "刘海遮挡关系、面部侧面、手指和袖口",
                "identity_risk": "high",
                "confidence": "medium",
            },
        ],
        "full_redraw": [
            {
                "action": "行走、跑动、跳跃、坐下、睡觉、转身、攀边",
                "key_pose_estimate": "4–12 个以上，依动作而定",
                "layering_required": "yes",
                "full_redraw_required": "yes",
                "identity_risk": "high",
                "confidence": "high",
            },
        ],
    }


def build_report(image_path: Path) -> dict[str, Any]:
    """Analyse the source copy and return serialisable review data."""
    if not image_path.is_file():
        raise FileNotFoundError(f"Original character image not found: {image_path}")

    before_hash = sha256(image_path)
    if before_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("The original character image hash does not match the approved value.")

    with Image.open(image_path) as opened_image:
        opened_image.verify()
    with Image.open(image_path) as opened_image:
        image = opened_image.convert("RGB")
        has_alpha = opened_image.mode in {"RGBA", "LA"} or "transparency" in opened_image.info
        background = analyse_background(image)
        background_color = tuple(background["edge_background_candidate"]["rgb"])
        report = {
            "source": {
                "path": str(image_path.resolve()),
                "sha256": before_hash,
                "format": opened_image.format,
                "size": {"width": image.width, "height": image.height},
                "mode": opened_image.mode,
                "has_alpha": has_alpha,
                "file_size_bytes": image_path.stat().st_size,
                "aspect_ratio": round(image.width / image.height, 6),
            },
            "background_analysis": background,
            "palette": extract_palette(image, background_color),
            "composition": {
                "estimated_subject_bounds": background["estimated_subject_bounds"],
                "margins": background["estimated_subject_bounds"].get("margins", {}),
                "confidence": background["estimated_subject_bounds"].get("confidence", "low"),
                "notes": background["estimated_subject_bounds"].get("notes", []),
            },
            "visual_identity": visual_identity_draft(),
            "identity_rules": identity_rules(),
            "display_size_options": display_size_options(image.width, image.height),
            "action_scope": action_scope_draft(),
            "pending_user_confirmation": [
                "默认逻辑显示尺寸：240 × 240 候选，需用户确认。",
                "A 级不可改变特征清单需用户确认。",
                "背景处理路线需用户确认；本阶段未去背景。",
                "首版动作方案和可接受的重绘范围需用户确认。",
                "画外身体、完整服装与细小饰物不能由当前单张近景确定。",
            ],
            "analysis_scope": {
                "non_destructive": True,
                "background_removed": False,
                "animation_frames_created": False,
                "desktop_pet_features_created": False,
            },
        }
        after_hash = sha256(image_path)
        if after_hash != before_hash:
            raise RuntimeError("The analysis unexpectedly changed the original image hash.")
        return report


def write_analysis_outputs(report: dict[str, Any]) -> None:
    """Write review-only artefacts inside assets/analysis."""
    ANALYSIS_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(ORIGINAL_CHARACTER_IMAGE) as opened_image:
        image = opened_image.convert("RGB")
        save_enlarged_reference(
            image, ANALYSIS_PREVIEWS_DIR / "character_enlarged_reference.png"
        )
        save_palette_preview(report["palette"], ANALYSIS_PREVIEWS_DIR / "character_palette.png")
        save_composition_preview(
            image,
            report["composition"]["estimated_subject_bounds"],
            ANALYSIS_PREVIEWS_DIR / "character_composition_grid.png",
        )
        save_size_comparison(
            image, ANALYSIS_PREVIEWS_DIR / "character_size_comparison.png"
        )
        save_review_board(
            image,
            report,
            ANALYSIS_PREVIEWS_DIR / "character_visual_review_board.png",
        )
    report_path = ANALYSIS_REPORTS_DIR / "character_analysis.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    """Run the non-destructive analysis and print an ASCII-only summary."""
    report = build_report(ORIGINAL_CHARACTER_IMAGE)
    write_analysis_outputs(report)
    source = report["source"]
    print("Character visual analysis completed.")
    print(f"Source: {source['path']}")
    print(f"SHA256: {source['sha256']}")
    print(f"Image: {source['format']} {source['size']['width']}x{source['size']['height']} {source['mode']}")
    print(f"Palette entries: {len(report['palette'])}")
    print(f"Reports: {ANALYSIS_REPORTS_DIR.relative_to(PROJECT_ROOT)}")
    print(f"Previews: {ANALYSIS_PREVIEWS_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
