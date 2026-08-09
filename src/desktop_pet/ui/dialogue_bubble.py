"""Reusable translucent dialogue bubble with exact Qt text layout and screen-safe placement."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from math import ceil

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import QWidget

from desktop_pet.config import DialogueBubbleConfig


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
    target: QPointF


def _fits(candidate: QPoint, size: QSize, safe: QRect) -> bool:
    return (
        candidate.x() >= safe.left()
        and candidate.y() >= safe.top()
        and candidate.x() + size.width() <= safe.left() + safe.width()
        and candidate.y() + size.height() <= safe.top() + safe.height()
    )


def calculate_bubble_placement(
    bubble_size: QSize,
    pet_rect: QRect,
    available_geometry: QRect,
    *,
    screen_margin: int,
    pet_gap: int,
) -> BubblePlacement:
    """Choose a deterministic candidate without assuming a zero-origin display."""
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
    centre_x = pet_rect.left() + pet_rect.width() // 2
    centre_y = pet_rect.top() + pet_rect.height() // 2
    left_bias = pet_rect.left() + pet_rect.width() // 3
    right_bias = pet_rect.left() + 2 * pet_rect.width() // 3

    candidates = (
        (QPoint(centre_x - width // 2, pet_rect.top() - pet_gap - height), TailDirection.BOTTOM),
        (QPoint(left_bias - width, pet_rect.top() - pet_gap - height), TailDirection.BOTTOM),
        (QPoint(right_bias, pet_rect.top() - pet_gap - height), TailDirection.BOTTOM),
        (QPoint(pet_rect.left() - pet_gap - width, centre_y - height // 2), TailDirection.RIGHT),
        (QPoint(pet_rect.right() + 1 + pet_gap, centre_y - height // 2), TailDirection.LEFT),
        (QPoint(centre_x - width // 2, pet_rect.bottom() + 1 + pet_gap), TailDirection.TOP),
    )
    for position, direction in candidates:
        if _fits(position, bubble_size, safe):
            target = QPointF(pet_rect.center() - position)
            return BubblePlacement(position, direction, target)

    maximum_x = safe.left() + max(0, safe.width() - width)
    maximum_y = safe.top() + max(0, safe.height() - height)
    preferred = candidates[0][0]
    clamped = QPoint(
        min(max(preferred.x(), safe.left()), maximum_x),
        min(max(preferred.y(), safe.top()), maximum_y),
    )
    bubble_centre = QPoint(clamped.x() + width // 2, clamped.y() + height // 2)
    pet_centre = pet_rect.center()
    horizontal = pet_centre.x() - bubble_centre.x()
    vertical = pet_centre.y() - bubble_centre.y()
    if abs(vertical) >= abs(horizontal):
        direction = TailDirection.BOTTOM if vertical >= 0 else TailDirection.TOP
    else:
        direction = TailDirection.RIGHT if horizontal >= 0 else TailDirection.LEFT
    return BubblePlacement(clamped, direction, QPointF(pet_centre - clamped))


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
        self._layout: QTextLayout | None = None
        self._tail_direction = TailDirection.BOTTOM
        self._tail_target = QPointF()
        self._display_count = 0
        self._layout_count = 0
        self._overlong_warning_count = 0
        self._font = self._dialogue_font()

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
        if self._layout is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = self._body_rect()
        border = QColor(152, 143, 170, 220)
        background = QColor(248, 246, 251, 242)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(background)
        painter.drawRoundedRect(body, self.config.corner_radius, self.config.corner_radius)
        self._draw_tail(painter, body, background, border)
        painter.setPen(QColor(55, 52, 62))
        origin = QPointF(
            body.left() + self.config.horizontal_padding,
            body.top() + self.config.vertical_padding,
        )
        self._layout.draw(painter, origin)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._hide_timer.stop()
        super().closeEvent(event)

    def _prepare_layout(self, text: str) -> None:
        candidate = text
        if len(candidate) > self.config.maximum_display_characters:
            candidate = candidate[: self.config.maximum_display_characters - 1].rstrip() + "…"
            self._warn_overlong(text)

        layout, height, width, consumed = self._build_layout(candidate)
        if consumed < len(candidate):
            candidate = candidate[: max(1, consumed - 1)].rstrip() + "…"
            layout, height, width, _ = self._build_layout(candidate)
            self._warn_overlong(text)
        self._display_text = candidate
        self._layout = layout
        self._layout_count += 1
        total_width = ceil(width) + 2 * (self.config.horizontal_padding + self.config.tail_size)
        total_height = ceil(height) + 2 * (self.config.vertical_padding + self.config.tail_size)
        self.resize(
            min(self.config.maximum_width, max(self.config.minimum_width, total_width)),
            min(self.config.maximum_height, max(1, total_height)),
        )

    def _build_layout(self, text: str) -> tuple[QTextLayout, float, float, int]:
        maximum_width = self.config.maximum_width - 2 * (
            self.config.horizontal_padding + self.config.tail_size
        )
        maximum_height = self.config.maximum_height - 2 * (
            self.config.vertical_padding + self.config.tail_size
        )
        layout = QTextLayout(text, self._font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        y = 0.0
        maximum_natural_width = 0.0
        consumed = 0
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(maximum_width)
            if y + line.height() > maximum_height:
                break
            line.setPosition(QPointF(0.0, y))
            y += line.height()
            maximum_natural_width = max(maximum_natural_width, line.naturalTextWidth())
            consumed = line.textStart() + line.textLength()
        layout.endLayout()
        return layout, y, min(maximum_width, maximum_natural_width), consumed

    def _body_rect(self) -> QRectF:
        tail = self.config.tail_size
        return QRectF(tail, tail, self.width() - 2 * tail, self.height() - 2 * tail)

    def _draw_tail(self, painter: QPainter, body: QRectF, background: QColor, border: QColor) -> None:
        tail = float(self.config.tail_size)
        half_base = max(4.0, tail * 0.62)
        if self._tail_direction in {TailDirection.TOP, TailDirection.BOTTOM}:
            anchor = min(max(self._tail_target.x(), body.left() + 18), body.right() - 18)
            edge = body.top() if self._tail_direction is TailDirection.TOP else body.bottom()
            tip_y = 0.5 if self._tail_direction is TailDirection.TOP else self.height() - 0.5
            points = QPolygonF(
                [QPointF(anchor - half_base, edge), QPointF(anchor, tip_y), QPointF(anchor + half_base, edge)]
            )
            edges = ((points[0], points[1]), (points[1], points[2]))
        else:
            anchor = min(max(self._tail_target.y(), body.top() + 18), body.bottom() - 18)
            edge = body.left() if self._tail_direction is TailDirection.LEFT else body.right()
            tip_x = 0.5 if self._tail_direction is TailDirection.LEFT else self.width() - 0.5
            points = QPolygonF(
                [QPointF(edge, anchor - half_base), QPointF(tip_x, anchor), QPointF(edge, anchor + half_base)]
            )
            edges = ((points[0], points[1]), (points[1], points[2]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawPolygon(points)
        painter.setPen(QPen(border, 1.0))
        for start, finish in edges:
            painter.drawLine(start, finish)

    def _warn_overlong(self, text: str) -> None:
        if self._overlong_warning_count == 0:
            print(
                f"小融警告：对白过长，气泡显示内容已省略 "
                f"({len(text)} characters).",
                file=sys.stderr,
            )
        self._overlong_warning_count += 1

    @staticmethod
    def _dialogue_font() -> QFont:
        installed = set(QFontDatabase.families())
        preferred = (
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Noto Sans SC",
            "SimHei",
        )
        family = next((candidate for candidate in preferred if candidate in installed), None)
        font = QFont(family) if family is not None else QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        if font.pointSizeF() < 10.0:
            font.setPointSizeF(10.0)
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
