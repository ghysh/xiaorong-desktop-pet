"""The sole high-frequency timer combining behavior profiles and local paint transforms."""

from __future__ import annotations

from math import pow

from PySide6.QtCore import QElapsedTimer, QObject, QPoint, Qt, QTimer, Signal

from desktop_pet.actions.arbiter import ActionArbiter, ArbitrationDecision
from desktop_pet.actions.player import ActionInterruption, ActionPlayer
from desktop_pet.actions.registry import ActionRuntimeRegistry
from desktop_pet.actions.request import ActionRequest
from desktop_pet.animation.easing import ease_in_out_sine, ease_out_cubic
from desktop_pet.animation.idle_motion import IdleMotionProfile
from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.behavior.controller import BehaviorController
from desktop_pet.behavior.profiles import calculate_behavior_transform
from desktop_pet.behavior.state import PetState
from desktop_pet.blink.controller import BlinkController
from desktop_pet.config import AnimationConfig, BehaviorConfig, BlinkConfig
from desktop_pet.interaction.controller import InteractionController


class AnimationController(QObject):
    """Drive local paint transforms and the timer-free behavior controller from one timer."""

    transform_changed = Signal(object)
    overlay_frame_changed = Signal(object)

    def __init__(
        self,
        config: AnimationConfig,
        *,
        behavior_config: BehaviorConfig | None = None,
        blink_config: BlinkConfig | None = None,
        action_registry: ActionRuntimeRegistry | None = None,
        effective_drag_tilt_max_degrees: float | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._profile = IdleMotionProfile.from_config(config)
        self._effective_drag_tilt_max_degrees = (
            config.drag_tilt_max_degrees
            if effective_drag_tilt_max_degrees is None
            else effective_drag_tilt_max_degrees
        )
        if not 0 <= self._effective_drag_tilt_max_degrees <= config.drag_tilt_max_degrees:
            raise ValueError("Effective drag tilt must be within the configured drag tilt limit.")

        self._behavior_controller = BehaviorController(behavior_config or BehaviorConfig(), parent=self)
        self._interaction_controller = InteractionController(self._behavior_controller, parent=self)
        self._action_registry = action_registry or ActionRuntimeRegistry()
        self._action_arbiter = ActionArbiter()
        self._action_player = ActionPlayer(parent=self)
        self._blink_controller = BlinkController(blink_config or BlinkConfig())
        self._action_player.frame_changed.connect(self.overlay_frame_changed)
        self._action_player.clip_finished.connect(self._on_action_finished)
        self._action_player.clip_interrupted.connect(self._on_action_interrupted)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(round(1000 / config.target_fps))
        self._timer.timeout.connect(self._on_tick)
        self._elapsed_timer = QElapsedTimer()
        self._elapsed_offset_seconds = 0.0
        self._current_transform = AnimationTransform.identity()
        self._has_started = False
        self._dragging = False
        self._returning = False
        self._drag_rotation_degrees = 0.0
        self._return_initial_rotation_degrees = 0.0
        self._return_start_ms = 0
        self._last_drag_position: QPoint | None = None
        self._last_drag_ms: int | None = None
        self._animation_enabled = True
        self._disable_pending = False
        self._disable_started_ms = 0
        self._disable_source_transform = AnimationTransform.identity()
        self._disable_duration_ms = 260

    @property
    def current_transform(self) -> AnimationTransform:
        """Return the most recently emitted local transform."""
        return self._current_transform

    @property
    def timer(self) -> QTimer:
        """Expose the sole animation timer for lifecycle checks."""
        return self._timer

    @property
    def target_fps(self) -> int:
        """Return the configured animation cadence."""
        return self._config.target_fps

    @property
    def effective_drag_tilt_max_degrees(self) -> float:
        """Return the clipping-safe drag limit selected by the window."""
        return self._effective_drag_tilt_max_degrees

    @property
    def behavior_controller(self) -> BehaviorController:
        """Expose the timer-free state machine for window events, tests, and diagnostics."""
        return self._behavior_controller

    @property
    def interaction_controller(self) -> InteractionController:
        """Expose the timer-free click controller driven by this same tick."""
        return self._interaction_controller

    @property
    def action_player(self) -> ActionPlayer:
        """Expose the timer-free action player driven by this controller's sole timer."""
        return self._action_player

    @property
    def blink_controller(self) -> BlinkController:
        """Expose the timer-free blink request controller for diagnostics and tests."""
        return self._blink_controller

    @property
    def action_registry(self) -> ActionRuntimeRegistry:
        return self._action_registry

    @property
    def elapsed_seconds(self) -> float:
        """Return active monotonic time preserved across timer pause and resume."""
        if not self._elapsed_timer.isValid():
            return self._elapsed_offset_seconds
        return self._elapsed_offset_seconds + self._elapsed_timer.elapsed() / 1000.0

    @property
    def is_dragging(self) -> bool:
        """Report whether drag tilt currently overrides automatic motion."""
        return self._dragging

    @property
    def is_returning(self) -> bool:
        """Report whether released drag tilt is easing back to zero."""
        return self._returning

    @property
    def animation_enabled(self) -> bool:
        return self._animation_enabled

    def start(self) -> None:
        """Start or resume the one timer and preserve behavior lifecycle semantics."""
        if self._behavior_controller.current_state is PetState.STOPPED:
            return
        if not self._animation_enabled:
            self._set_current(AnimationTransform.identity(), force=True)
            return
        if self._timer.isActive():
            return
        self._elapsed_timer.start()
        now = self.elapsed_seconds
        if not self._has_started:
            self._behavior_controller.start(now)
            self._has_started = True
        elif self._behavior_controller.current_state is PetState.PAUSED:
            self._behavior_controller.resume(now)
        self._dragging = False
        self._returning = False
        self._drag_rotation_degrees = 0.0
        self._last_drag_position = None
        self._last_drag_ms = None
        self._timer.start()
        self._emit_profiled_transform(now, force=True)

    def stop(self) -> None:
        """Stop periodic work without forcing a lifecycle transition; retained for direct tests."""
        now = self.elapsed_seconds
        self._timer.stop()
        self._interrupt_current_action(now, "animation_timer_stopped")
        self._blink_controller.pause(now)
        self._dragging = False
        self._last_drag_position = None
        self._last_drag_ms = None
        self._freeze_elapsed_clock(now)

    def pause(self) -> None:
        """Enter PAUSED and stop the timer, state time, drag, and all repaint emissions."""
        now = self.elapsed_seconds
        self._interaction_controller.cancel_active(now)
        self._interrupt_current_action(now, "animation_paused")
        self._blink_controller.pause(now)
        self._behavior_controller.pause(now)
        self._timer.stop()
        self._dragging = False
        self._returning = False
        self._last_drag_position = None
        self._last_drag_ms = None
        self._freeze_elapsed_clock(now)

    def shutdown(self) -> None:
        """Enter terminal STOPPED and stop the sole timer permanently."""
        now = self.elapsed_seconds
        self._timer.stop()
        self._interaction_controller.cancel_active(now)
        self._interrupt_current_action(now, "application_stopped")
        self._blink_controller.stop()
        self._dragging = False
        self._returning = False
        self._last_drag_position = None
        self._last_drag_ms = None
        self._behavior_controller.stop(now)
        self._freeze_elapsed_clock(now)

    def begin_drag(self, global_position: QPoint) -> None:
        """Immediately enter DRAGGING and begin the established lagging-tilt calculation."""
        if self._behavior_controller.current_state in {PetState.PAUSED, PetState.STOPPED}:
            return
        if not self._elapsed_timer.isValid():
            self.start()
        now = self.elapsed_seconds
        self._interaction_controller.cancel_for_drag()
        self._interrupt_current_action(now, "dragging")
        self._behavior_controller.begin_drag(now)
        self._dragging = True
        self._returning = False
        self._drag_rotation_degrees = 0.0
        self._last_drag_position = QPoint(global_position)
        self._last_drag_ms = self._elapsed_timer.elapsed()
        self._emit_profiled_transform(now, force=True)

    def update_drag(self, global_position: QPoint, *, elapsed_ms: int | None = None) -> None:
        """Smooth actual horizontal drag velocity into the documented opposite-direction tilt."""
        if not self._dragging:
            return
        now_ms = self._elapsed_timer.elapsed() if elapsed_ms is None else elapsed_ms
        if self._last_drag_position is None or self._last_drag_ms is None:
            self._last_drag_position = QPoint(global_position)
            self._last_drag_ms = now_ms
            return
        elapsed_delta_ms = now_ms - self._last_drag_ms
        delta_x = global_position.x() - self._last_drag_position.x()
        self._last_drag_position = QPoint(global_position)
        self._last_drag_ms = now_ms
        if elapsed_delta_ms <= 0:
            return
        elapsed_delta_seconds = elapsed_delta_ms / 1000.0
        horizontal_velocity = delta_x / elapsed_delta_seconds
        target_rotation = -horizontal_velocity * self._config.drag_velocity_degrees_per_pixel_per_second
        target_rotation = max(
            -self._effective_drag_tilt_max_degrees,
            min(self._effective_drag_tilt_max_degrees, target_rotation),
        )
        smoothing = 1.0 - pow(
            1.0 - self._config.drag_tilt_smoothing,
            elapsed_delta_seconds * self._config.target_fps,
        )
        self._drag_rotation_degrees += smoothing * (target_rotation - self._drag_rotation_degrees)
        self._emit_profiled_transform(self.elapsed_seconds, force=True)

    def end_drag(self) -> None:
        """Enter SETTLING and keep QWidget position fixed while local tilt eases to zero."""
        if not self._dragging:
            return
        self._dragging = False
        self._returning = True
        self._return_initial_rotation_degrees = self._drag_rotation_degrees
        self._return_start_ms = self._elapsed_timer.elapsed()
        self._last_drag_position = None
        self._last_drag_ms = None
        self._behavior_controller.release_drag(self.elapsed_seconds)

    def set_animation_enabled(self, enabled: bool) -> None:
        """Fade to identity before stopping, or allow the owning window to restart smoothly."""
        if not isinstance(enabled, bool):
            raise ValueError("Animation enabled state must be boolean.")
        if enabled is self._animation_enabled and not self._disable_pending:
            return
        self._animation_enabled = enabled
        if enabled:
            self._disable_pending = False
            return
        now = self.elapsed_seconds
        self._interaction_controller.cancel_active(now)
        self._interrupt_current_action(now, "animation_disabled")
        self._blink_controller.pause(now)
        self._dragging = False
        self._returning = False
        if not self._timer.isActive() or not self._elapsed_timer.isValid():
            self._disable_pending = False
            self._set_current(AnimationTransform.identity(), force=True)
            self._behavior_controller.pause(now)
            return
        self._disable_pending = True
        self._disable_started_ms = self._elapsed_timer.elapsed()
        self._disable_source_transform = self._current_transform

    def set_behavior_enabled(self, enabled: bool) -> None:
        """Forward an automatic-scheduling toggle using the shared monotonic clock."""
        self._behavior_controller.set_behavior_enabled(enabled, self.elapsed_seconds)

    def set_click_reaction_enabled(self, enabled: bool) -> None:
        self._interaction_controller.set_enabled(enabled, self.elapsed_seconds)

    def try_start_click(self, **gesture: object) -> bool:
        """Start the existing click response and immediately clear any blink overlay."""
        accepted = self._interaction_controller.try_start_click(**gesture)  # type: ignore[arg-type]
        if accepted:
            self._interrupt_current_action(self.elapsed_seconds, "click_reaction")
        return accepted

    def _on_tick(self) -> None:
        if not self._elapsed_timer.isValid() or self._behavior_controller.current_state is PetState.STOPPED:
            return
        elapsed_seconds = self.elapsed_seconds
        if self._disable_pending:
            progress = (self._elapsed_timer.elapsed() - self._disable_started_ms) / self._disable_duration_ms
            if progress >= 1.0:
                self._disable_pending = False
                self._set_current(AnimationTransform.identity(), force=True)
                self._behavior_controller.pause(elapsed_seconds)
                self._timer.stop()
                self._freeze_elapsed_clock(elapsed_seconds)
                return
            self._set_current(
                _interpolate_to_identity(self._disable_source_transform, ease_in_out_sine(progress)),
            )
            return
        self._behavior_controller.update(elapsed_seconds)
        self._interaction_controller.update(elapsed_seconds)
        if self._behavior_controller.current_state not in {
            PetState.IDLE_CALM,
            PetState.IDLE_QUIET,
            PetState.IDLE_SWAY,
            PetState.RESTING,
        }:
            self._interrupt_current_action(elapsed_seconds, "behavior_override")
        request = self._blink_controller.update(elapsed_seconds, self._behavior_controller.current_state)
        if request is not None:
            self._process_action_request(request)
        self._action_player.update(elapsed_seconds)
        if self._dragging:
            self._emit_profiled_transform(elapsed_seconds)
            return
        if self._returning:
            progress = (self._elapsed_timer.elapsed() - self._return_start_ms) / self._config.drag_return_duration_ms
            if progress >= 1.0:
                self._drag_rotation_degrees = 0.0
                self._returning = False
                self._behavior_controller.settling_complete(elapsed_seconds)
                self._emit_profiled_transform(elapsed_seconds, force=True)
                return
            self._drag_rotation_degrees = self._return_initial_rotation_degrees * (1.0 - ease_out_cubic(progress))
            self._emit_profiled_transform(elapsed_seconds)
            return
        self._emit_profiled_transform(elapsed_seconds)

    def _emit_profiled_transform(self, elapsed_seconds: float, *, force: bool = False) -> None:
        profile = self._behavior_controller.motion_profile_at(elapsed_seconds)
        transform = calculate_behavior_transform(elapsed_seconds, self._profile, profile)
        if self._dragging or self._returning:
            transform = transform.combined_with(
                AnimationTransform(rotation_degrees=self._drag_rotation_degrees)
            )
        if self._interaction_controller.is_active:
            transform = transform.combined_with(self._interaction_controller.current_transform)
        self._set_current(transform, force=force)

    def _set_current(self, transform: AnimationTransform, *, force: bool = False) -> None:
        if force or not transform.is_close(self._current_transform):
            self._current_transform = transform
            self.transform_changed.emit(transform)

    def _freeze_elapsed_clock(self, elapsed_seconds: float) -> None:
        """Freeze the accumulated active clock without allowing a future reset to zero."""
        self._elapsed_offset_seconds = elapsed_seconds
        self._elapsed_timer.invalidate()

    def _process_action_request(self, request: ActionRequest) -> bool:
        try:
            clip = self._action_registry.get(request.action_id)
        except KeyError:
            self._blink_controller.resolve_request(False, request.requested_at_seconds)
            return False
        decision = self._action_arbiter.decide(
            request,
            state=self._behavior_controller.current_state,
            current_clip=self._action_player.current_clip,
            pending_action_id=self._action_player.pending_action_id,
        )
        accepted = decision is not ArbitrationDecision.REJECT
        if decision is ArbitrationDecision.START_IMMEDIATELY:
            if self._action_player.current_clip is not None:
                self._action_player.interrupt(request.requested_at_seconds, reason="higher_priority_request")
            self._action_player.start(clip, request.requested_at_seconds)
        elif decision in {ArbitrationDecision.QUEUE_AFTER_FRAME, ArbitrationDecision.QUEUE_AFTER_CYCLE}:
            self._action_player.queue(clip, decision, request.requested_at_seconds)
        self._blink_controller.resolve_request(accepted, request.requested_at_seconds)
        return accepted

    def _interrupt_current_action(self, elapsed_seconds: float, reason: str) -> None:
        self._action_player.interrupt(elapsed_seconds, reason=reason)

    def _on_action_finished(self, clip: object) -> None:
        if getattr(clip, "action_id", None) == BlinkController.ACTION_ID:
            self._blink_controller.on_clip_finished(self._action_player.last_elapsed_seconds)

    def _on_action_interrupted(self, interruption: ActionInterruption) -> None:
        if interruption.clip.action_id == BlinkController.ACTION_ID:
            self._blink_controller.on_clip_interrupted(self._action_player.last_elapsed_seconds)


def _interpolate_to_identity(source: AnimationTransform, weight: float) -> AnimationTransform:
    """Blend a local transform to identity without moving the QWidget."""
    return AnimationTransform(
        offset_x=source.offset_x * (1.0 - weight),
        offset_y=source.offset_y * (1.0 - weight),
        scale_x=source.scale_x + (1.0 - source.scale_x) * weight,
        scale_y=source.scale_y + (1.0 - source.scale_y) * weight,
        rotation_degrees=source.rotation_degrees * (1.0 - weight),
    )
