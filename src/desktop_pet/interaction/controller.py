"""Timer-free validation and lifecycle controller for click feedback."""

from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QObject, Qt, Signal

from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.behavior.controller import BehaviorController
from desktop_pet.behavior.state import PetState
from desktop_pet.config import CLICK_MAX_HOLD_DURATION_MS, CLICK_REACTION_DURATION_MS
from desktop_pet.interaction.click_reaction import click_reaction_transform


class InteractionController(QObject):
    """Validate clicks and expose feedback updated by the existing animation tick."""

    click_started = Signal()
    click_finished = Signal()
    character_clicked = Signal()

    def __init__(self, behavior_controller: BehaviorController, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._behavior_controller = behavior_controller
        self._enabled = True
        self._active = False
        self._started_at_seconds = 0.0
        self._current_transform = AnimationTransform.identity()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_transform(self) -> AnimationTransform:
        return self._current_transform

    def try_start_click(
        self,
        *,
        elapsed_seconds: float,
        button: Qt.MouseButton,
        press_hit: bool,
        release_hit: bool,
        movement_distance: float,
        drag_threshold: int,
        held_ms: int,
        context_menu_open: bool = False,
    ) -> bool:
        """Start only when a full press/release gesture satisfies the click contract."""
        self._validate_inputs(elapsed_seconds, movement_distance, drag_threshold, held_ms)
        valid_gesture = (
            button == Qt.MouseButton.LeftButton
            and press_hit
            and release_hit
            and movement_distance < drag_threshold
            and held_ms <= CLICK_MAX_HOLD_DURATION_MS
            and not context_menu_open
            and self._behavior_controller.current_state not in {PetState.PAUSED, PetState.STOPPED}
        )
        if not valid_gesture:
            return False

        # This is the single gesture-level notification used by independent UI feedback.
        # It remains observable while click feedback is disabled, but consumers apply the
        # setting before showing anything.
        self.character_clicked.emit()
        if self._active or not self._enabled:
            return False
        if not self._behavior_controller.begin_click_reaction(elapsed_seconds):
            return False
        self._active = True
        self._started_at_seconds = elapsed_seconds
        self._current_transform = AnimationTransform.identity()
        self.click_started.emit()
        return True

    def update(self, elapsed_seconds: float) -> AnimationTransform:
        """Advance from the sole animation tick and restore behavior at 260 ms."""
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Interaction elapsed time must be finite and nonnegative.")
        if not self._active:
            return self._current_transform
        elapsed_ms = max(0.0, (elapsed_seconds - self._started_at_seconds) * 1000.0)
        if elapsed_ms >= CLICK_REACTION_DURATION_MS:
            self._behavior_controller.finish_click_reaction(elapsed_seconds)
            self._finish()
            return self._current_transform
        self._current_transform = click_reaction_transform(elapsed_ms)
        return self._current_transform

    def cancel_for_drag(self) -> None:
        """Drop the paint feedback; BehaviorController gives the subsequent drag priority."""
        if self._active:
            self._finish()

    def cancel_active(self, elapsed_seconds: float) -> None:
        """End a running click early and restore its frozen base behavior."""
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Interaction elapsed time must be finite and nonnegative.")
        if self._active:
            self._behavior_controller.finish_click_reaction(elapsed_seconds)
            self._finish()

    def set_enabled(self, enabled: bool, elapsed_seconds: float) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Click-reaction enabled state must be boolean.")
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Interaction elapsed time must be finite and nonnegative.")
        self._enabled = enabled
        if not enabled and self._active:
            self._behavior_controller.finish_click_reaction(elapsed_seconds)
            self._finish()

    def _finish(self) -> None:
        was_active = self._active
        self._active = False
        self._current_transform = AnimationTransform.identity()
        if was_active:
            self.click_finished.emit()

    @staticmethod
    def _validate_inputs(
        elapsed_seconds: float,
        movement_distance: float,
        drag_threshold: int,
        held_ms: int,
    ) -> None:
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Interaction elapsed time must be finite and nonnegative.")
        if not isfinite(movement_distance) or movement_distance < 0:
            raise ValueError("Click movement distance must be finite and nonnegative.")
        if isinstance(drag_threshold, bool) or not isinstance(drag_threshold, int) or drag_threshold <= 0:
            raise ValueError("System drag threshold must be a positive integer.")
        if isinstance(held_ms, bool) or not isinstance(held_ms, int) or held_ms < 0:
            raise ValueError("Click hold duration must be a nonnegative integer.")
