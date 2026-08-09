"""以只读方式分析项目内的原始角色图片。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from desktop_pet.paths import ORIGINAL_CHARACTER_IMAGE


def has_alpha_channel(image: Image.Image) -> bool:
    """判断图片是否携带 Alpha 或调色板透明信息。"""
    return image.mode in {"RGBA", "LA"} or "transparency" in image.info


def has_transparent_edge(image: Image.Image, has_alpha: bool) -> bool:
    """只读检查四条图片边缘是否含完全透明的像素。"""
    if not has_alpha:
        return False

    rgba_image = image.convert("RGBA")
    alpha = rgba_image.getchannel("A")
    border_extrema = (
        alpha.crop((0, 0, image.width, 1)).getextrema(),
        alpha.crop((0, image.height - 1, image.width, image.height)).getextrema(),
        alpha.crop((0, 0, 1, image.height)).getextrema(),
        alpha.crop((image.width - 1, 0, image.width, image.height)).getextrema(),
    )
    return any(extrema[0] == 0 for extrema in border_extrema)


def suggest_display_size(width: int, height: int) -> tuple[int, int]:
    """保持比例地建议以 240 像素长边作为初始显示大小。"""
    long_edge = 240
    if width >= height:
        return long_edge, max(1, round(long_edge * height / width))
    return max(1, round(long_edge * width / height)), long_edge


def analyze_image(image_path: Path) -> dict[str, Any]:
    """验证并读取图片元数据，不写入、重编码或改变图片。"""
    resolved_path = image_path.resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Original character image not found: {resolved_path}")

    with Image.open(resolved_path) as image:
        image.verify()

    with Image.open(resolved_path) as image:
        width, height = image.size
        has_alpha = has_alpha_channel(image)
        return {
            "path": resolved_path,
            "filename": resolved_path.name,
            "format": image.format,
            "width": width,
            "height": height,
            "mode": image.mode,
            "has_alpha": has_alpha,
            "file_size": resolved_path.stat().st_size,
            "aspect_ratio": width / height,
            "transparent_edge": has_transparent_edge(image, has_alpha),
            "suggested_display_size": suggest_display_size(width, height),
        }


def print_report(report: dict[str, Any]) -> None:
    """输出仅含 ASCII 标签的非破坏性分析结果，兼容 Conda 控制台。"""
    suggested_width, suggested_height = report["suggested_display_size"]
    print(f"File path: {report['path']}")
    print(f"Filename: {report['filename']}")
    print(f"Image format: {report['format']}")
    print(f"Image size: {report['width']} x {report['height']}")
    print(f"Color mode: {report['mode']}")
    print(f"Contains alpha information: {report['has_alpha']}")
    print(f"File size: {report['file_size']} bytes")
    print(f"Aspect ratio: {report['aspect_ratio']:.4f}")
    print(f"Transparent pixels on image edge: {report['transparent_edge']}")
    print(f"Suggested initial display size: {suggested_width} x {suggested_height}")


def main(argv: list[str] | None = None) -> int:
    """运行图片检查；缺失或损坏时返回清晰的非零状态码。"""
    parser = argparse.ArgumentParser(description="只读检查角色原始图片")
    parser.add_argument(
        "--image",
        type=Path,
        default=ORIGINAL_CHARACTER_IMAGE,
        help="要检查的图片路径，默认是项目内原始素材副本。",
    )
    args = parser.parse_args(argv)

    try:
        report = analyze_image(args.image)
    except FileNotFoundError as error:
        print(f"Error: {error}. No placeholder image was created.", file=sys.stderr)
        return 1
    except (UnidentifiedImageError, OSError) as error:
        print(
            f"Error: original character image cannot be decoded: {error}",
            file=sys.stderr,
        )
        return 2

    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
