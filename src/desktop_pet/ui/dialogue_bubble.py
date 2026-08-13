"""Reusable translucent dialogue bubble with exact Qt text layout and screen-safe placement."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from math import ceil
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from desktop_pet.config import DialogueBubbleConfig
from desktop_pet.paths import DIALOGUE_BUBBLE_FRAME

_CLAUSE_BREAKS = frozenset("，,。！？!?；;：:…")
_EMOTICON_MARKERS = frozenset("()（）[]【】{}<>《》/\\_^=¯₍₎♡✧✌σ♪")


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return 0x3400 <= codepoint <= 0x9FFF or 0xF900 <= codepoint <= 0xFAFF


def split_trailing_emoticon(text: str) -> tuple[str, str] | None:
    """Split a likely trailing kaomoji from Chinese prose without altering either part."""
    last_han = max((index for index, character in enumerate(text) if _is_han(character)), default=-1)
    if last_han < 0:
        return None
    suffix = text[last_han + 1 :]
    visible_suffix = suffix.strip()
    marker_count = sum(character in _EMOTICON_MARKERS for character in visible_suffix)
    if len(visible_suffix) < 3 or marker_count < 2:
        return None
    return text[: last_han + 1], suffix


def _wrap_plain_text(text: str, maximum_width: float, metrics: QFontMetricsF) -> list[str]:
    """Greedily wrap Chinese prose at character boundaries without dropping content."""
    lines: list[str] = []
    current = ""
    for character in text:
        if character == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + character
        if current and metrics.horizontalAdvance(candidate) > maximum_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current or not lines:
        lines.append(current)
    return lines


def wrap_dialogue_lines(text: str, maximum_width: float, metrics: QFontMetricsF) -> tuple[str, ...]:
    """Wrap dialogue while treating its trailing kaomoji as one indivisible unit."""
    emoticon_split = split_trailing_emoticon(text)
    if emoticon_split is None:
        return tuple(_wrap_plain_text(text, maximum_width, metrics))

    prefix, emoticon = emoticon_split
    phrase_start = max((prefix.rfind(mark) + 1 for mark in _CLAUSE_BREAKS), default=0)
    trailing_phrase = prefix[phrase_start:] + emoticon
    if phrase_start > 0 and metrics.horizontalAdvance(trailing_phrase) <= maximum_width:
        head = prefix[:phrase_start]
        protected_tail = trailing_phrase
    elif metrics.horizontalAdvance(text) <= maximum_width:
        head = ""
        protected_tail = text
    else:
        candidates: list[tuple[float, int]] = []
        minimum_tail_han = min(4, sum(_is_han(character) for character in prefix[phrase_start:]))
        for start in range(phrase_start, len(prefix)):
            if sum(_is_han(character) for character in prefix[start:]) < minimum_tail_han:
                continue
            tail_width = metrics.horizontalAdvance(prefix[start:] + emoticon)
            if tail_width > maximum_width:
                continue
            head_lines = _wrap_plain_text(prefix[:start], maximum_width, metrics)
            head_width = metrics.horizontalAdvance(head_lines[-1])
            candidates.append((abs(head_width - tail_width), start))
        if candidates:
            _, protected_start = min(candidates)
            head = prefix[:protected_start]
            protected_tail = prefix[protected_start:] + emoticon
        else:
            head = prefix
            protected_tail = emoticon

    lines = [] if not head else _wrap_plain_text(head, maximum_width, metrics)
    if lines and metrics.horizontalAdvance(lines[-1] + protected_tail) <= maximum_width:
        lines[-1] += protected_tail
    else:
        lines.append(protected_tail)
    return tuple(lines)


class TailDirection(Enum):
    """The body edge from which the tail points toward the pet."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class BubblePlacement:
    """A global top-left point, tail edge, and pet target in bubble-local coordinates."""

    position: QPoint
    tail_direction: TailDirection
    anchor: QPointF
    target: QPointF


def calculate_bubble_placement(
    bubble_size: QSize,
    pet_rect: QRect,
    available_geometry: QRect,
    *,
    screen_margin: int,
    pet_gap: int,
) -> BubblePlacement:
    """Keep the body on-screen while preserving an explicit pet anchor for the tail."""
    if bubble_size.width() <= 0 or bubble_size.height() <= 0:
        raise ValueError("Bubble size must be positive.")
    if pet_rect.width() <= 0 or pet_rect.height() <= 0:
        raise ValueError("Pet rectangle must be positive.")
    if available_geometry.width() <= 0 or available_geometry.height() <= 0:
        raise ValueError("Available screen geometry must be positive.")
    if screen_margin < 0 or pet_gap < 0:
        raise ValueError("Placement margins must be nonnegative.")

    safe = available_geometry.adjusted(screen_margin, screen_margin, -screen_margin, -screen_margin)
    width = bubble_size.width()
    height = bubble_size.height()
    safe_right = safe.left() + safe.width()
    safe_bottom = safe.top() + safe.height()
    maximum_x = safe_right - width
    maximum_y = safe_bottom - height
    centre_x = pet_rect.left() + pet_rect.width() / 2
    centre_y = pet_rect.top() + pet_rect.height() / 2

    def clamp(value: int, lower: int, upper: int) -> int:
        return lower if upper < lower else min(max(value, lower), upper)

    def pet_anchor(direction: TailDirection) -> QPointF:
        if direction is TailDirection.BOTTOM:
            return QPointF(centre_x, pet_rect.top())
        if direction is TailDirection.TOP:
            return QPointF(centre_x, pet_rect.top() + pet_rect.height())
        if direction is TailDirection.RIGHT:
            return QPointF(pet_rect.left(), centre_y)
        return QPointF(pet_rect.left() + pet_rect.width(), centre_y)

    def placement(position: QPoint, direction: TailDirection) -> BubblePlacement:
        anchor = pet_anchor(direction)
        target = QPointF(anchor.x() - position.x(), anchor.y() - position.y())
        return BubblePlacement(position, direction, anchor, target)

    above = QPoint(round(centre_x - width / 2), pet_rect.top() - pet_gap - height)
    if above.y() >= safe.top():
        above.setX(clamp(above.x(), safe.left(), maximum_x))
        return placement(above, TailDirection.BOTTOM)

    below = QPoint(round(centre_x - width / 2), pet_rect.top() + pet_rect.height() + pet_gap)
    if below.y() + height <= safe_bottom:
        below.setX(clamp(below.x(), safe.left(), maximum_x))
        return placement(below, TailDirection.TOP)

    left = QPoint(pet_rect.left() - pet_gap - width, round(centre_y - height / 2))
    right = QPoint(pet_rect.left() + pet_rect.width() + pet_gap, round(centre_y - height / 2))
    side_candidates = (
        (right, TailDirection.LEFT, safe_right - right.x()),
        (left, TailDirection.RIGHT, left.x() + width - safe.left()),
    )
    for position, direction, _space in sorted(side_candidates, key=lambda item: item[2], reverse=True):
        if position.x() >= safe.left() and position.x() + width <= safe_right:
            position.setY(clamp(position.y(), safe.top(), maximum_y))
            return placement(position, direction)

    ideal_candidates = (
        (above, TailDirection.BOTTOM),
        (below, TailDirection.TOP),
        (right, TailDirection.LEFT),
        (left, TailDirection.RIGHT),
    )

    def overflow(candidate: QPoint) -> int:
        return (
            max(0, safe.left() - candidate.x())
            + max(0, candidate.x() + width - safe_right)
            + max(0, safe.top() - candidate.y())
            + max(0, candidate.y() + height - safe_bottom)
        )

    preferred, direction = min(ideal_candidates, key=lambda item: overflow(item[0]))
    clamped = QPoint(
        clamp(preferred.x(), safe.left(), maximum_x),
        clamp(preferred.y(), safe.top(), maximum_y),
    )
    return placement(clamped, direction)


class DialogueBubble(QWidget):
    """One focus-free bubble window reused for every click dialogue."""

    dialogue_hidden = Signal()

    def __init__(
        self,
        config: DialogueBubbleConfig | None = None,
        *,
        always_on_top: bool = True,
    ) -> None:
        super().__init__(None)
        self.config = config or DialogueBubbleConfig()
        self._always_on_top = always_on_top
        self._current_text = ""
        self._display_text = ""
        self._layout_lines: tuple[str, ...] = ()
        self._line_widths: tuple[float, ...] = ()
        self._tail_direction = TailDirection.BOTTOM
        self._tail_target = QPointF()
        self._display_count = 0
        self._layout_count = 0
        self._overlong_warning_count = 0
        self._font = self._dialogue_font(self.config.font_point_size)
        self._font_metrics = QFontMetricsF(self._font)
        self._frame_source = QPixmap(str(DIALOGUE_BUBBLE_FRAME))
        if self._frame_source.isNull():
            raise FileNotFoundError(f"Dialogue bubble frame cannot be loaded: {DIALOGUE_BUBBLE_FRAME}")
        fill_left = round(self._frame_source.width() * 0.12)
        fill_top = round(self._frame_source.height() * 0.16)
        fill_width = self._frame_source.width() - 2 * fill_left
        fill_height = round(self._frame_source.height() * 0.52)
        self._frame_fill_source = self._frame_source.copy(fill_left, fill_top, fill_width, fill_height)
        self._frame_cache: dict[tuple[int, int], QPixmap] = {}

        self.setWindowFlags(self._window_flags(always_on_top))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_dialogue)

    @property
    def current_text(self) -> str:
        return self._current_text

    @property
    def display_text(self) -> str:
        return self._display_text

    @property
    def tail_direction(self) -> TailDirection:
        return self._tail_direction

    @property
    def hide_timer(self) -> QTimer:
        return self._hide_timer

    @property
    def display_count(self) -> int:
        return self._display_count

    @property
    def layout_count(self) -> int:
        return self._layout_count

    @property
    def overlong_warning_count(self) -> int:
        return self._overlong_warning_count

    @property
    def frame_asset_path(self) -> Path:
        return DIALOGUE_BUBBLE_FRAME

    @property
    def frame_cache_size(self) -> int:
        return len(self._frame_cache)

    @property
    def layout_lines(self) -> tuple[str, ...]:
        return self._layout_lines

    @property
    def content_rect(self) -> QRectF:
        return self._content_rect()

    @property
    def text_block_rect(self) -> QRectF:
        if not self._layout_lines:
            return QRectF()
        content = self._content_rect()
        block_width = max(self._line_widths)
        block_height = self._text_block_height()
        return QRectF(
            content.center().x() - block_width / 2,
            content.center().y() - block_height / 2,
            block_width,
            block_height,
        )

    @property
    def tail_target(self) -> QPointF:
        return QPointF(self._tail_target)

    @property
    def tail_tip(self) -> QPointF:
        return self._tail_tip(self._body_rect())

    def show_dialogue(self, text: str, pet_rect: QRect, available_geometry: QRect) -> None:
        """Update the existing window, reposition it, and restart one single-shot timer."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Dialogue bubble text must be a non-empty string.")
        self._current_text = text
        self._prepare_layout(text)
        self.reposition(pet_rect, available_geometry)
        self.show()
        self._hide_timer.start(self.config.display_duration_ms)
        self._display_count += 1

    def reposition(self, pet_rect: QRect, available_geometry: QRect) -> None:
        """Move only on a geometry event; never poll from an animation timer."""
        if not self._current_text:
            return
        placement = calculate_bubble_placement(
            self.size(),
            pet_rect,
            available_geometry,
            screen_margin=self.config.screen_margin,
            pet_gap=self.config.pet_gap,
        )
        self._tail_direction = placement.tail_direction
        self._tail_target = placement.target
        self.move(placement.position)
        self.update()

    def hide_dialogue(self) -> None:
        """Hide immediately and cancel the timeout without retaining visible state."""
        self._hide_timer.stop()
        was_visible = self.isVisible()
        self.hide()
        if was_visible:
            self.dialogue_hidden.emit()

    def set_always_on_top(self, enabled: bool) -> None:
        """Change flags in place while retaining text, position, and remaining timeout."""
        if not isinstance(enabled, bool):
            raise ValueError("Dialogue always-on-top state must be boolean.")
        if enabled == self._always_on_top:
            return
        position = self.pos()
        was_visible = self.isVisible()
        remaining = self._hide_timer.remainingTime() if self._hide_timer.isActive() else -1
        self._always_on_top = enabled
        self.setWindowFlags(self._window_flags(enabled))
        self.move(position)
        if was_visible:
            self.show()
            if remaining > 0:
                self._hide_timer.start(remaining)

    def shutdown(self) -> None:
        self._hide_timer.stop()
        self.hide()
        self.close()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        if not self._layout_lines:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = self._body_rect()
        frame_path = self._frame_path(body)
        painter.save()
        painter.translate(0.0, 1.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(93, 74, 84, 26))
        painter.drawPath(frame_path)
        painter.restore()
        outline = QPen(QColor(174, 153, 159, 235))
        outline.setWidthF(1.15)
        outline.setCapStyle(Qt.PenCapStyle.RoundCap)
        outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline)
        painter.setBrush(QBrush(self._frame_pixmap()))
        painter.drawPath(frame_path)
        painter.setFont(self._font)
        painter.setPen(QColor(70, 59, 68))
        content = self._content_rect()
        line_height = self._font_metrics.height()
        y = self.text_block_rect.top()
        alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
        for line in self._layout_lines:
            painter.drawText(QRectF(content.left(), y, content.width(), line_height), alignment, line)
            y += line_height + self.config.line_gap

    def closeEvent(self, event: QCloseEvent) -> None:
        self._hide_timer.stop()
        super().closeEvent(event)

    def _prepare_layout(self, text: str) -> None:
        candidate = text
        warned = False
        if len(candidate) > self.config.maximum_display_characters:
            candidate = candidate[: self.config.maximum_display_characters - 1].rstrip() + "…"
            self._warn_overlong(text)
            warned = True

        maximum_width = self._maximum_content_width()
        lines = wrap_dialogue_lines(candidate, maximum_width, self._font_metrics)
        maximum_lines = self._maximum_line_count()
        if len(lines) > maximum_lines:
            lines = lines[:maximum_lines]
            lines = (*lines[:-1], self._elide_line(lines[-1], maximum_width))
            if not warned:
                self._warn_overlong(text)

        self._layout_lines = lines
        self._line_widths = tuple(self._font_metrics.horizontalAdvance(line) for line in lines)
        self._display_text = "\n".join(lines)
        self._layout_count += 1
        total_width = ceil(max(self._line_widths, default=0.0)) + 2 * (
            self.config.horizontal_padding + self.config.tail_size
        )
        total_height = ceil(self._text_block_height()) + 2 * (
            self.config.vertical_padding + self.config.tail_size
        )
        self.resize(
            min(self.config.maximum_width, max(self.config.minimum_width, total_width)),
            min(self.config.maximum_height, max(1, total_height)),
        )

    def _maximum_content_width(self) -> float:
        return float(
            self.config.maximum_width - 2 * (self.config.horizontal_padding + self.config.tail_size)
        )

    def _maximum_line_count(self) -> int:
        maximum_height = self.config.maximum_height - 2 * (
            self.config.vertical_padding + self.config.tail_size
        )
        line_step = self._font_metrics.height() + self.config.line_gap
        return max(1, int((maximum_height + self.config.line_gap) // line_step))

    def _text_block_height(self) -> float:
        if not self._layout_lines:
            return 0.0
        return len(self._layout_lines) * self._font_metrics.height() + (
            len(self._layout_lines) - 1
        ) * self.config.line_gap

    def _elide_line(self, line: str, maximum_width: float) -> str:
        candidate = line.rstrip()
        while candidate and self._font_metrics.horizontalAdvance(candidate + "…") > maximum_width:
            candidate = candidate[:-1].rstrip()
        return candidate + "…"

    def _body_rect(self) -> QRectF:
        tail = self.config.tail_size
        return QRectF(tail, tail, self.width() - 2 * tail, self.height() - 2 * tail)

    def _content_rect(self) -> QRectF:
        return self._body_rect().adjusted(
            self.config.horizontal_padding,
            self.config.vertical_padding,
            -self.config.horizontal_padding,
            -self.config.vertical_padding,
        )

    def _frame_pixmap(self) -> QPixmap:
        key = (self.width(), self.height())
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached

        scaled = self._frame_fill_source.scaled(
            self.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if len(self._frame_cache) >= 32:
            self._frame_cache.clear()
        self._frame_cache[key] = scaled
        return scaled

    def _tail_axis_anchor(self, body: QRectF) -> float:
        if self._tail_direction in {TailDirection.TOP, TailDirection.BOTTOM}:
            clearance = min(
                float(self.config.corner_radius + self.config.tail_size),
                max(float(self.config.tail_size), body.width() / 2 - 1.0),
            )
            return min(max(self._tail_target.x(), body.left() + clearance), body.right() - clearance)
        clearance = min(
            float(self.config.corner_radius + self.config.tail_size),
            max(float(self.config.tail_size), body.height() / 2 - 1.0),
        )
        return min(max(self._tail_target.y(), body.top() + clearance), body.bottom() - clearance)

    def _tail_tip(self, body: QRectF) -> QPointF:
        anchor = self._tail_axis_anchor(body)
        if self._tail_direction is TailDirection.TOP:
            return QPointF(anchor, 0.75)
        if self._tail_direction is TailDirection.BOTTOM:
            return QPointF(anchor, self.height() - 0.75)
        if self._tail_direction is TailDirection.LEFT:
            return QPointF(0.75, anchor)
        return QPointF(self.width() - 0.75, anchor)

    def _tail_path(self, body: QRectF) -> QPainterPath:
        anchor = self._tail_axis_anchor(body)
        tail = float(self.config.tail_size)
        half_base = max(8.0, tail * 0.82)
        path = QPainterPath()

        if self._tail_direction in {TailDirection.TOP, TailDirection.BOTTOM}:
            body_edge = body.top() + 1.0 if self._tail_direction is TailDirection.TOP else body.bottom() - 1.0
            tip = self._tail_tip(body)
            sign = -1.0 if self._tail_direction is TailDirection.TOP else 1.0
            start = QPointF(anchor - half_base, body_edge)
            finish = QPointF(anchor + half_base, body_edge)
            first_control = QPointF(anchor - half_base * 0.45, body_edge + sign * tail * 0.22)
            second_control = QPointF(anchor - half_base * 0.34, tip.y() - sign * tail * 0.16)
            third_control = QPointF(anchor + half_base * 0.34, tip.y() - sign * tail * 0.16)
            fourth_control = QPointF(anchor + half_base * 0.45, body_edge + sign * tail * 0.22)
        else:
            body_edge = body.left() + 1.0 if self._tail_direction is TailDirection.LEFT else body.right() - 1.0
            tip = self._tail_tip(body)
            sign = -1.0 if self._tail_direction is TailDirection.LEFT else 1.0
            start = QPointF(body_edge, anchor - half_base)
            finish = QPointF(body_edge, anchor + half_base)
            first_control = QPointF(body_edge + sign * tail * 0.22, anchor - half_base * 0.45)
            second_control = QPointF(tip.x() - sign * tail * 0.16, anchor - half_base * 0.34)
            third_control = QPointF(tip.x() - sign * tail * 0.16, anchor + half_base * 0.34)
            fourth_control = QPointF(body_edge + sign * tail * 0.22, anchor + half_base * 0.45)

        path.moveTo(start)
        path.cubicTo(first_control, second_control, tip)
        path.cubicTo(third_control, fourth_control, finish)
        path.closeSubpath()
        return path

    def _frame_path(self, body: QRectF) -> QPainterPath:
        outline_body = body.adjusted(0.75, 0.75, -0.75, -0.75)
        body_path = QPainterPath()
        body_path.addRoundedRect(
            outline_body,
            float(self.config.corner_radius),
            float(self.config.corner_radius),
        )
        return body_path.united(self._tail_path(outline_body))

    def _warn_overlong(self, text: str) -> None:
        if self._overlong_warning_count == 0:
            print(
                f"小融警告：对白过长，气泡显示内容已省略 "
                f"({len(text)} characters).",
                file=sys.stderr,
            )
        self._overlong_warning_count += 1

    @staticmethod
    def _dialogue_font(point_size: float) -> QFont:
        installed = set(QFontDatabase.families())
        preferred = (
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Noto Sans SC",
            "SimHei",
        )
        family = next((candidate for candidate in preferred if candidate in installed), None)
        font = QFont(family) if family is not None else QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        font.setPointSizeF(point_size)
        font.setBold(False)
        return font

    @staticmethod
    def _window_flags(always_on_top: bool) -> Qt.WindowType:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        return flags
