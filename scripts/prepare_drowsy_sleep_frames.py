"""Normalize and quality-check transparent drowsy-sleep runtime frames."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageStat

CANVAS_SIZE = (1024, 1536)
DEFAULT_BOTTOM = 1497
DEFAULT_CENTER_X = 512.0
MAX_SUBJECT_WIDTH = 930
DEFAULT_MAX_NEIGHBOR_CENTER_DELTA = 3.0
DEFAULT_MAX_NEIGHBOR_BOTTOM_DELTA = 1
DEFAULT_MAX_NEIGHBOR_HEIGHT_RATIO = 0.12
DEFAULT_MAX_NEIGHBOR_WIDTH_RATIO = 0.35
DEFAULT_MAX_SECONDARY_COMPONENT_RATIO = 0.02
DEFAULT_STABLE_REGION_FRACTION = 0.45
DEFAULT_STABILITY_REGION_TOP = 0.55
DEFAULT_MAX_STABILITY_ALPHA_DIFFERENCE = 0.085
DEFAULT_MAX_REFERENCE_SCALE_CORRECTION = 0.08
DEFAULT_MAX_TONE_LUMINANCE_DELTA = 10.0
DEFAULT_MAX_TONE_CHANNEL_DELTA = 14.0
DEFAULT_MAX_TONE_SATURATION_DELTA = 18.0
DEFAULT_MAX_TONE_CHANNEL_GAIN_DELTA = 0.045
DEFAULT_MAX_TONE_SATURATION_GAIN_DELTA = 0.05
COMPONENT_AUDIT_SIZE = (256, 384)


@dataclass(frozen=True, slots=True)
class FrameMetrics:
    """Alpha-derived placement metrics used by normalization and QA."""

    bounds: tuple[int, int, int, int]
    width: int
    height: int
    center_x: float
    bottom: int
    visible_pixels: int


@dataclass(frozen=True, slots=True)
class ToneMetrics:
    """Alpha-masked colour statistics used for gentle continuity checks."""

    mean_rgb: tuple[float, float, float]
    luminance: float
    saturation: float


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise argparse.ArgumentTypeError("value must be finite")
    return parsed


def _positive_float(value: str) -> float:
    parsed = _finite_float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _fraction(value: str) -> float:
    parsed = _finite_float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("value must be between zero and one")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--names", nargs="+", required=True)
    parser.add_argument(
        "--target-heights",
        nargs="+",
        type=_positive_int,
        help="Explicit subject heights; required unless scale-reference-frames is used.",
    )
    parser.add_argument(
        "--target-centers",
        nargs="+",
        type=_finite_float,
        help="Target alpha-bounds horizontal centres; defaults to 512 for every output.",
    )
    parser.add_argument(
        "--clear-left",
        nargs="+",
        type=_non_negative_int,
        metavar="PIXELS",
        help="Clear disconnected prior-panel residue left of these x coordinates.",
    )
    parser.add_argument("--bottom", type=int, default=DEFAULT_BOTTOM)
    parser.add_argument(
        "--previous-frames",
        nargs="+",
        type=Path,
        help="Optional previous runtime frame for each output, used for neighbour QA.",
    )
    parser.add_argument(
        "--next-frames",
        nargs="+",
        type=Path,
        help="Optional next runtime frame for each output, used for neighbour QA.",
    )
    parser.add_argument(
        "--scale-reference-frames",
        nargs="+",
        type=Path,
        help=(
            "Reference frame for each output. Scale is matched from the stable lower "
            "body instead of the changing full-body bounding box."
        ),
    )
    parser.add_argument(
        "--stability-reference-frames",
        nargs="+",
        type=Path,
        help="Reference frame for lower-body alpha-silhouette continuity checks.",
    )
    parser.add_argument(
        "--tone-reference-frames",
        nargs="+",
        type=Path,
        help="Reference frame for alpha-masked colour continuity checks.",
    )
    parser.add_argument(
        "--tone-match",
        action="store_true",
        help="Apply a bounded channel/saturation correction before tone validation.",
    )
    parser.add_argument(
        "--stable-region-fraction",
        type=_fraction,
        default=DEFAULT_STABLE_REGION_FRACTION,
    )
    parser.add_argument(
        "--scale-region-top",
        type=_fraction,
        help=(
            "Optional fixed normalized canvas y-coordinate for scale sampling. "
            "Use this for raised-arm poses so the sampling band stays on the legs."
        ),
    )
    parser.add_argument(
        "--stability-region-top",
        type=_fraction,
        default=DEFAULT_STABILITY_REGION_TOP,
    )
    parser.add_argument(
        "--max-stability-alpha-difference",
        type=_fraction,
        default=DEFAULT_MAX_STABILITY_ALPHA_DIFFERENCE,
    )
    parser.add_argument(
        "--max-reference-scale-correction",
        type=_fraction,
        default=DEFAULT_MAX_REFERENCE_SCALE_CORRECTION,
    )
    parser.add_argument(
        "--max-tone-luminance-delta",
        type=_positive_float,
        default=DEFAULT_MAX_TONE_LUMINANCE_DELTA,
    )
    parser.add_argument(
        "--max-tone-channel-delta",
        type=_positive_float,
        default=DEFAULT_MAX_TONE_CHANNEL_DELTA,
    )
    parser.add_argument(
        "--max-tone-saturation-delta",
        type=_positive_float,
        default=DEFAULT_MAX_TONE_SATURATION_DELTA,
    )
    parser.add_argument(
        "--max-tone-channel-gain-delta",
        type=_fraction,
        default=DEFAULT_MAX_TONE_CHANNEL_GAIN_DELTA,
    )
    parser.add_argument(
        "--max-tone-saturation-gain-delta",
        type=_fraction,
        default=DEFAULT_MAX_TONE_SATURATION_GAIN_DELTA,
    )
    parser.add_argument(
        "--max-neighbor-center-delta",
        type=_positive_float,
        default=DEFAULT_MAX_NEIGHBOR_CENTER_DELTA,
    )
    parser.add_argument(
        "--max-neighbor-bottom-delta",
        type=_non_negative_int,
        default=DEFAULT_MAX_NEIGHBOR_BOTTOM_DELTA,
    )
    parser.add_argument(
        "--max-neighbor-height-ratio",
        type=_fraction,
        default=DEFAULT_MAX_NEIGHBOR_HEIGHT_RATIO,
    )
    parser.add_argument(
        "--max-neighbor-width-ratio",
        type=_fraction,
        default=DEFAULT_MAX_NEIGHBOR_WIDTH_RATIO,
    )
    parser.add_argument(
        "--max-secondary-component-ratio",
        type=_fraction,
        default=DEFAULT_MAX_SECONDARY_COMPONENT_RATIO,
    )
    parser.add_argument("--force", action="store_true")
    return parser


def _split_panels(image: Image.Image, panel_count: int) -> tuple[Image.Image, ...]:
    width, height = image.size
    if width % panel_count:
        raise ValueError(
            f"storyboard width must be divisible by panel count {panel_count}: {image.size}"
        )
    panel_width = width // panel_count
    return tuple(
        image.crop((index * panel_width, 0, (index + 1) * panel_width, height))
        for index in range(panel_count)
    )


def _alpha_metrics(image: Image.Image) -> FrameMetrics:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("frame has no visible subject")
    left, top, right, bottom = bounds
    visible_pixels = sum(alpha.histogram()[1:])
    return FrameMetrics(
        bounds=bounds,
        width=right - left,
        height=bottom - top,
        center_x=(left + right) / 2.0,
        bottom=bottom,
        visible_pixels=visible_pixels,
    )


def _tone_metrics(image: Image.Image) -> ToneMetrics:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getbbox() is None:
        raise ValueError("frame has no visible subject")
    rgb = rgba.convert("RGB")
    mean_rgb = tuple(ImageStat.Stat(rgb, mask=alpha).mean)
    luminance = (
        0.2126 * mean_rgb[0] + 0.7152 * mean_rgb[1] + 0.0722 * mean_rgb[2]
    )
    saturation = ImageStat.Stat(rgb.convert("HSV").getchannel("S"), mask=alpha).mean[0]
    return ToneMetrics(
        mean_rgb=(mean_rgb[0], mean_rgb[1], mean_rgb[2]),
        luminance=luminance,
        saturation=saturation,
    )


def _stable_region_width(
    image: Image.Image,
    stable_region_fraction: float,
    *,
    region_top: float | None = None,
) -> int:
    metrics = _alpha_metrics(image)
    sample_top = (
        round(image.height * region_top)
        if region_top is not None
        else metrics.bottom - round(metrics.height * stable_region_fraction)
    )
    if sample_top >= metrics.bottom:
        raise ValueError("stable lower-body scale region is empty")
    bounds = image.convert("RGBA").getchannel("A").crop(
        (0, sample_top, image.width, metrics.bottom)
    ).getbbox()
    if bounds is None or bounds[2] <= bounds[0]:
        raise ValueError("stable lower-body region has no visible subject")
    return bounds[2] - bounds[0]


def _binary_alpha_sample(image: Image.Image) -> Image.Image:
    alpha = image.convert("RGBA").getchannel("A")
    return alpha.resize(COMPONENT_AUDIT_SIZE, Image.Resampling.NEAREST).point(
        lambda value: 255 if value >= 24 else 0,
        mode="1",
    )


def _alpha_region_difference_ratio(
    frame: Image.Image,
    reference: Image.Image,
    region_top: float = DEFAULT_STABILITY_REGION_TOP,
) -> float:
    if frame.size != reference.size:
        raise ValueError("stability frames must use the same canvas")
    frame_mask = _binary_alpha_sample(frame)
    reference_mask = _binary_alpha_sample(reference)
    sample_top = round(COMPONENT_AUDIT_SIZE[1] * region_top)
    crop_box = (0, sample_top, COMPONENT_AUDIT_SIZE[0], COMPONENT_AUDIT_SIZE[1])
    frame_region = frame_mask.crop(crop_box)
    reference_region = reference_mask.crop(crop_box)
    difference = ImageChops.logical_xor(frame_region, reference_region).convert("L")
    union = ImageChops.lighter(
        frame_region.convert("L"), reference_region.convert("L")
    )
    difference_pixels = difference.histogram()[255]
    union_pixels = union.histogram()[255]
    return difference_pixels / max(1, union_pixels)


def _validate_stable_region(
    frame: Image.Image,
    reference: Image.Image,
    *,
    region_top: float,
    max_alpha_difference: float,
) -> None:
    difference = _alpha_region_difference_ratio(frame, reference, region_top)
    if difference > max_alpha_difference:
        raise ValueError(
            "stable lower-body alpha difference "
            f"{difference:.4f} exceeds {max_alpha_difference:.4f}"
        )


def _validate_tone_pair(
    frame: Image.Image,
    reference: Image.Image,
    *,
    max_luminance_delta: float,
    max_channel_delta: float,
    max_saturation_delta: float,
) -> None:
    frame_tone = _tone_metrics(frame)
    reference_tone = _tone_metrics(reference)
    luminance_delta = abs(frame_tone.luminance - reference_tone.luminance)
    channel_delta = max(
        abs(value - reference_value)
        for value, reference_value in zip(
            frame_tone.mean_rgb, reference_tone.mean_rgb, strict=True
        )
    )
    saturation_delta = abs(frame_tone.saturation - reference_tone.saturation)
    if luminance_delta > max_luminance_delta:
        raise ValueError(
            f"tone luminance delta {luminance_delta:.2f} exceeds {max_luminance_delta:.2f}"
        )
    if channel_delta > max_channel_delta:
        raise ValueError(
            f"tone channel delta {channel_delta:.2f} exceeds {max_channel_delta:.2f}"
        )
    if saturation_delta > max_saturation_delta:
        raise ValueError(
            "tone saturation delta "
            f"{saturation_delta:.2f} exceeds {max_saturation_delta:.2f}"
        )


def _match_tone_lightly(
    frame: Image.Image,
    reference: Image.Image,
    *,
    max_channel_gain_delta: float = DEFAULT_MAX_TONE_CHANNEL_GAIN_DELTA,
    max_saturation_gain_delta: float = DEFAULT_MAX_TONE_SATURATION_GAIN_DELTA,
) -> Image.Image:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    frame_tone = _tone_metrics(rgba)
    reference_tone = _tone_metrics(reference)
    lower_channel_gain = 1.0 - max_channel_gain_delta
    upper_channel_gain = 1.0 + max_channel_gain_delta
    gains = tuple(
        min(
            upper_channel_gain,
            max(lower_channel_gain, reference_value / max(1.0, value)),
        )
        for value, reference_value in zip(
            frame_tone.mean_rgb, reference_tone.mean_rgb, strict=True
        )
    )
    corrected_channels = tuple(
        channel.point(
            [min(255, max(0, round(value * gain))) for value in range(256)]
        )
        for channel, gain in zip(rgba.convert("RGB").split(), gains, strict=True)
    )
    corrected_rgb = Image.merge("RGB", corrected_channels)
    corrected_tone = _tone_metrics(Image.merge("RGBA", (*corrected_channels, alpha)))
    saturation_gain = reference_tone.saturation / max(1.0, corrected_tone.saturation)
    saturation_gain = min(
        1.0 + max_saturation_gain_delta,
        max(1.0 - max_saturation_gain_delta, saturation_gain),
    )
    corrected_rgb = ImageEnhance.Color(corrected_rgb).enhance(saturation_gain)
    corrected = corrected_rgb.convert("RGBA")
    corrected.putalpha(alpha)
    return corrected


def _secondary_component_ratio(image: Image.Image) -> float:
    alpha = image.convert("RGBA").getchannel("A")
    sample = alpha.resize(COMPONENT_AUDIT_SIZE, Image.Resampling.NEAREST)
    pixels = tuple(value > 0 for value in sample.tobytes())
    width, height = sample.size
    visited = bytearray(len(pixels))
    component_sizes: list[int] = []
    for start, visible in enumerate(pixels):
        if not visible or visited[start]:
            continue
        visited[start] = 1
        queue = deque([start])
        component_size = 0
        while queue:
            index = queue.popleft()
            component_size += 1
            x = index % width
            y = index // width
            for neighbor_x, neighbor_y in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if not 0 <= neighbor_x < width or not 0 <= neighbor_y < height:
                    continue
                neighbor = neighbor_y * width + neighbor_x
                if pixels[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        component_sizes.append(component_size)
    if len(component_sizes) < 2:
        return 0.0
    component_sizes.sort(reverse=True)
    return component_sizes[1] / sum(component_sizes)


def _validate_source_panel(panel: Image.Image, max_secondary_component_ratio: float) -> None:
    metrics = _alpha_metrics(panel)
    left, top, right, bottom = metrics.bounds
    if left <= 0 or top <= 0 or right >= panel.width or bottom >= panel.height:
        raise ValueError(f"source subject is cropped or touches an edge: bounds={metrics.bounds}")
    secondary_ratio = _secondary_component_ratio(panel)
    if secondary_ratio > max_secondary_component_ratio:
        raise ValueError(
            "source contains a suspicious disconnected alpha component: "
            f"ratio={secondary_ratio:.4f}, limit={max_secondary_component_ratio:.4f}"
        )


def _normalize_panel(
    panel: Image.Image,
    target_height: int,
    bottom: int,
    target_center: float = DEFAULT_CENTER_X,
    max_secondary_component_ratio: float = DEFAULT_MAX_SECONDARY_COMPONENT_RATIO,
) -> Image.Image:
    rgba = panel.convert("RGBA")
    _validate_source_panel(rgba, max_secondary_component_ratio)
    alpha_bounds = _alpha_metrics(rgba).bounds
    subject = rgba.crop(alpha_bounds)
    scale = target_height / subject.height
    target_size = (
        max(1, round(subject.width * scale)),
        target_height,
    )
    if target_size[0] > MAX_SUBJECT_WIDTH:
        raise ValueError(
            "target height would exceed the safe subject width: "
            f"size={target_size}, max_width={MAX_SUBJECT_WIDTH}"
        )
    subject = subject.resize(target_size, Image.Resampling.LANCZOS)
    left = round(target_center - subject.width / 2.0)
    top = bottom - subject.height
    if left < 0 or top < 0 or bottom > CANVAS_SIZE[1]:
        raise ValueError(
            f"normalized subject does not fit canvas: size={subject.size}, left={left}, top={top}"
        )
    canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(subject, (left, top))
    metrics = _alpha_metrics(canvas)
    if metrics.height != target_height:
        raise ValueError(
            f"normalized height drifted: actual={metrics.height}, target={target_height}"
        )
    if metrics.bottom != bottom:
        raise ValueError(f"normalized bottom drifted: actual={metrics.bottom}, target={bottom}")
    if abs(metrics.center_x - target_center) > 1.0:
        raise ValueError(
            f"normalized centre drifted: actual={metrics.center_x}, target={target_center}"
        )
    return canvas


def _normalize_panel_to_reference(
    panel: Image.Image,
    reference: Image.Image,
    bottom: int,
    target_center: float = DEFAULT_CENTER_X,
    *,
    stable_region_fraction: float = DEFAULT_STABLE_REGION_FRACTION,
    scale_region_top: float | None = None,
    max_scale_correction: float = DEFAULT_MAX_REFERENCE_SCALE_CORRECTION,
    max_secondary_component_ratio: float = DEFAULT_MAX_SECONDARY_COMPONENT_RATIO,
) -> Image.Image:
    """Align a pose by its stable lower body without rescaling from head motion."""

    rgba = panel.convert("RGBA")
    reference_rgba = reference.convert("RGBA")
    _validate_source_panel(rgba, max_secondary_component_ratio)
    subject_bounds = _alpha_metrics(rgba).bounds
    subject = rgba.crop(subject_bounds)
    candidate_width = _stable_region_width(
        rgba,
        stable_region_fraction,
        region_top=scale_region_top,
    )
    reference_width = _stable_region_width(
        reference_rgba,
        stable_region_fraction,
        region_top=scale_region_top,
    )
    scale = reference_width / candidate_width
    if abs(scale - 1.0) > max_scale_correction:
        raise ValueError(
            "reference lower-body scale correction "
            f"{scale:.4f} exceeds allowed +/-{max_scale_correction:.4f}"
        )
    target_size = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    if target_size[0] > MAX_SUBJECT_WIDTH:
        raise ValueError(
            "reference normalization exceeds the safe subject width: "
            f"size={target_size}, max_width={MAX_SUBJECT_WIDTH}"
        )
    subject = subject.resize(target_size, Image.Resampling.LANCZOS)
    left = round(target_center - subject.width / 2.0)
    top = bottom - subject.height
    if left < 0 or top < 0 or bottom > CANVAS_SIZE[1]:
        raise ValueError(
            f"normalized subject does not fit canvas: size={subject.size}, left={left}, top={top}"
        )
    canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(subject, (left, top))
    metrics = _alpha_metrics(canvas)
    if metrics.bottom != bottom:
        raise ValueError(f"normalized bottom drifted: actual={metrics.bottom}, target={bottom}")
    if abs(metrics.center_x - target_center) > 1.0:
        raise ValueError(
            f"normalized centre drifted: actual={metrics.center_x}, target={target_center}"
        )
    return canvas


def _validate_neighbor_pair(
    frame: Image.Image,
    neighbor: Image.Image,
    *,
    max_center_delta: float,
    max_bottom_delta: int,
    max_height_ratio: float,
    max_width_ratio: float,
) -> None:
    metrics = _alpha_metrics(frame)
    neighbor_metrics = _alpha_metrics(neighbor)
    center_delta = abs(metrics.center_x - neighbor_metrics.center_x)
    bottom_delta = abs(metrics.bottom - neighbor_metrics.bottom)
    height_ratio = abs(metrics.height - neighbor_metrics.height) / max(
        metrics.height, neighbor_metrics.height
    )
    width_ratio = abs(metrics.width - neighbor_metrics.width) / max(
        metrics.width, neighbor_metrics.width
    )
    if center_delta > max_center_delta:
        raise ValueError(
            f"neighbor centre delta {center_delta:.2f} exceeds {max_center_delta:.2f}"
        )
    if bottom_delta > max_bottom_delta:
        raise ValueError(f"neighbor bottom delta {bottom_delta} exceeds {max_bottom_delta}")
    if height_ratio > max_height_ratio:
        raise ValueError(
            f"neighbor height ratio {height_ratio:.4f} exceeds {max_height_ratio:.4f}"
        )
    if width_ratio > max_width_ratio:
        raise ValueError(
            f"neighbor width ratio {width_ratio:.4f} exceeds {max_width_ratio:.4f}"
        )


def _clear_left_residue(frame: Image.Image, clear_left: int) -> Image.Image:
    if clear_left == 0:
        return frame
    if clear_left >= frame.width:
        raise ValueError(f"clear-left must be smaller than canvas width: {clear_left}")
    cleaned = frame.copy()
    cleaned.paste((0, 0, 0, 0), (0, 0, clear_left, frame.height))
    return cleaned


def main() -> int:
    args = _build_parser().parse_args()
    for input_path in args.input:
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
    if args.target_heights is None and args.scale_reference_frames is None:
        raise ValueError("target-heights or scale-reference-frames must be provided")
    if args.target_heights is not None and len(args.names) != len(args.target_heights):
        raise ValueError("names and target-heights must contain the same number of values")
    target_centers = args.target_centers or [DEFAULT_CENTER_X] * len(args.names)
    if len(target_centers) != len(args.names):
        raise ValueError("target-centers must contain one value per output name")
    clear_left_values = args.clear_left or [0] * len(args.names)
    if len(clear_left_values) != len(args.names):
        raise ValueError("clear-left must contain one value per output name")
    for label, paths in (
        ("previous-frames", args.previous_frames),
        ("next-frames", args.next_frames),
        ("scale-reference-frames", args.scale_reference_frames),
        ("stability-reference-frames", args.stability_reference_frames),
        ("tone-reference-frames", args.tone_reference_frames),
    ):
        if paths is not None and len(paths) != len(args.names):
            raise ValueError(f"{label} must contain one value per output name")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if len(args.input) == 1:
        with Image.open(args.input[0]) as storyboard:
            storyboard.load()
            panels = _split_panels(storyboard, len(args.names))
    elif len(args.input) == len(args.names):
        loaded_panels: list[Image.Image] = []
        for input_path in args.input:
            with Image.open(input_path) as panel:
                panel.load()
                loaded_panels.append(panel.convert("RGBA"))
        panels = tuple(loaded_panels)
    else:
        raise ValueError(
            "input must contain either one storyboard or one image per output name"
        )
    target_heights = args.target_heights or [None] * len(args.names)
    for index, (panel, name, target_height, target_center, clear_left) in enumerate(
        zip(
            panels,
            args.names,
            target_heights,
            target_centers,
            clear_left_values,
            strict=True,
        )
    ):
        output_path = args.output_dir / f"{name}.png"
        if output_path.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite existing frame: {output_path}")
        if args.scale_reference_frames is not None:
            scale_reference_path = args.scale_reference_frames[index]
            if not scale_reference_path.is_file():
                raise FileNotFoundError(scale_reference_path)
            with Image.open(scale_reference_path) as scale_reference:
                scale_reference.load()
                frame = _normalize_panel_to_reference(
                    panel,
                    scale_reference,
                    args.bottom,
                    target_center,
                    stable_region_fraction=args.stable_region_fraction,
                    scale_region_top=args.scale_region_top,
                    max_scale_correction=args.max_reference_scale_correction,
                    max_secondary_component_ratio=args.max_secondary_component_ratio,
                )
        else:
            if target_height is None:
                raise AssertionError("target height unexpectedly missing")
            frame = _normalize_panel(
                panel,
                target_height,
                args.bottom,
                target_center,
                args.max_secondary_component_ratio,
            )
        frame = _clear_left_residue(frame, clear_left)
        if args.tone_reference_frames is not None:
            tone_reference_path = args.tone_reference_frames[index]
            if not tone_reference_path.is_file():
                raise FileNotFoundError(tone_reference_path)
            with Image.open(tone_reference_path) as tone_reference:
                tone_reference.load()
                if args.tone_match:
                    frame = _match_tone_lightly(
                        frame,
                        tone_reference,
                        max_channel_gain_delta=args.max_tone_channel_gain_delta,
                        max_saturation_gain_delta=args.max_tone_saturation_gain_delta,
                    )
                _validate_tone_pair(
                    frame,
                    tone_reference,
                    max_luminance_delta=args.max_tone_luminance_delta,
                    max_channel_delta=args.max_tone_channel_delta,
                    max_saturation_delta=args.max_tone_saturation_delta,
                )
        if args.stability_reference_frames is not None:
            stability_reference_path = args.stability_reference_frames[index]
            if not stability_reference_path.is_file():
                raise FileNotFoundError(stability_reference_path)
            with Image.open(stability_reference_path) as stability_reference:
                stability_reference.load()
                _validate_stable_region(
                    frame,
                    stability_reference,
                    region_top=args.stability_region_top,
                    max_alpha_difference=args.max_stability_alpha_difference,
                )
        for paths in (args.previous_frames, args.next_frames):
            if paths is None:
                continue
            neighbor_path = paths[index]
            if not neighbor_path.is_file():
                raise FileNotFoundError(neighbor_path)
            with Image.open(neighbor_path) as neighbor:
                neighbor.load()
                _validate_neighbor_pair(
                    frame,
                    neighbor,
                    max_center_delta=args.max_neighbor_center_delta,
                    max_bottom_delta=args.max_neighbor_bottom_delta,
                    max_height_ratio=args.max_neighbor_height_ratio,
                    max_width_ratio=args.max_neighbor_width_ratio,
                )
        frame.save(output_path, format="PNG", optimize=True)
        metrics = _alpha_metrics(frame)
        tone = _tone_metrics(frame)
        print(
            f"created {output_path} size={frame.size} mode={frame.mode} "
            f"bounds={metrics.bounds} center={metrics.center_x:.1f} bottom={metrics.bottom} "
            f"luminance={tone.luminance:.1f} saturation={tone.saturation:.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
