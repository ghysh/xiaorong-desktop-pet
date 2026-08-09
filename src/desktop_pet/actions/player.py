"""QObject action player driven exclusively by the existing animation tick."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite

from PySide6.QtCore import QObject, Signal

from desktop_pet.actions.arbiter import ArbitrationDecision
from desktop_pet.actions.model import ActionClip, ActionFrame, ActionLoopMode
from desktop_pet.actions.playback import PlaybackFrame, PlaybackTimeline


@dataclass(frozen=True, slots=True)
class ActionInterruption:
    clip: ActionClip
    reason: str


@dataclass(frozen=True, slots=True)
class _PendingAction:
    clip: ActionClip
    decision: ArbitrationDecision
    switch_at_ms: int


class ActionPlayer(QObject):
    """Advance clips from absolute monotonic time without owning a QTimer."""

    clip_started = Signal(object)
    frame_changed = Signal(object)
    clip_finished = Signal(object)
    clip_interrupted = Signal(object)

    def __init__(self, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clip: ActionClip | None = None
        self._timeline: PlaybackTimeline | None = None
        self._started_at_seconds = 0.0
        self._last_elapsed_seconds = 0.0
        self._current_playback_frame: PlaybackFrame | None = None
        self._current_token: tuple[int, int] | None = None
        self._pending: _PendingAction | None = None
        self._paused_at_seconds: float | None = None

    @property
    def current_clip(self) -> ActionClip | None:
        return self._clip

    @property
    def current_frame(self) -> ActionFrame | None:
        return None if self._current_playback_frame is None else self._current_playback_frame.frame

    @property
    def current_playback_frame(self) -> PlaybackFrame | None:
        return self._current_playback_frame

    @property
    def pending_action_id(self) -> str | None:
        return None if self._pending is None else self._pending.clip.action_id

    @property
    def last_elapsed_seconds(self) -> float:
        return self._last_elapsed_seconds

    @property
    def is_paused(self) -> bool:
        return self._paused_at_seconds is not None

    def start(self, clip: ActionClip, elapsed_seconds: float, *, loop_count: int | None = None) -> None:
        self._validate_time(elapsed_seconds, allow_before_last=False)
        if self._clip is not None:
            raise RuntimeError("ActionPlayer cannot start a clip while another clip is active.")
        self._start_at(clip, elapsed_seconds, loop_count=loop_count)

    def update(self, elapsed_seconds: float) -> ActionFrame | None:
        self._validate_time(elapsed_seconds, allow_before_last=False)
        self._last_elapsed_seconds = elapsed_seconds
        if self._clip is None or self._timeline is None or self.is_paused:
            return self.current_frame
        elapsed_ms = self._action_elapsed_ms(elapsed_seconds)
        if self._pending is not None and elapsed_ms >= self._pending.switch_at_ms:
            self._activate_pending(elapsed_seconds)
            return self.update(elapsed_seconds)
        playback_frame = self._timeline.frame_at(elapsed_ms)
        if playback_frame is None:
            finished = self._clip
            self._clear_active(emit_frame=True)
            self.clip_finished.emit(finished)
            return None
        self._emit_frame_if_changed(playback_frame)
        return playback_frame.frame

    def queue(self, clip: ActionClip, decision: ArbitrationDecision, elapsed_seconds: float) -> None:
        if decision not in {ArbitrationDecision.QUEUE_AFTER_FRAME, ArbitrationDecision.QUEUE_AFTER_CYCLE}:
            raise ValueError("Queued actions require a frame or cycle arbitration boundary.")
        if self._clip is None or self._timeline is None:
            raise RuntimeError("ActionPlayer has no active clip to queue behind.")
        elapsed_ms = self._action_elapsed_ms(elapsed_seconds)
        if decision is ArbitrationDecision.QUEUE_AFTER_FRAME:
            switch_at_ms = self._timeline.frame_boundary_after(elapsed_ms)
        else:
            switch_at_ms = self._timeline.cycle_boundary_after(elapsed_ms)
        self._pending = _PendingAction(clip=clip, decision=decision, switch_at_ms=switch_at_ms)

    def interrupt(self, elapsed_seconds: float, *, reason: str) -> bool:
        self._validate_time(elapsed_seconds, allow_before_last=True)
        self._last_elapsed_seconds = elapsed_seconds
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Action interruption reason must be nonempty.")
        if self._clip is None:
            self._pending = None
            return False
        interrupted = self._clip
        self._clear_active(emit_frame=True)
        self.clip_interrupted.emit(ActionInterruption(interrupted, reason.strip()))
        return True

    def pause(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds, allow_before_last=True)
        if self._paused_at_seconds is None:
            self._paused_at_seconds = elapsed_seconds

    def resume(self, elapsed_seconds: float) -> None:
        self._validate_time(elapsed_seconds, allow_before_last=True)
        if self._paused_at_seconds is None:
            return
        self._started_at_seconds += max(0.0, elapsed_seconds - self._paused_at_seconds)
        self._paused_at_seconds = None
        self._last_elapsed_seconds = elapsed_seconds

    def _start_at(self, clip: ActionClip, started_at_seconds: float, *, loop_count: int | None = None) -> None:
        self._clip = clip
        self._timeline = PlaybackTimeline(clip, loop_count)
        self._started_at_seconds = started_at_seconds
        self._last_elapsed_seconds = started_at_seconds
        self._pending = None
        self._paused_at_seconds = None
        self._current_playback_frame = None
        self._current_token = None
        self.clip_started.emit(clip)
        first = self._timeline.frame_at(0)
        if first is not None:
            self._emit_frame_if_changed(first)

    def _activate_pending(self, elapsed_seconds: float) -> None:
        assert self._pending is not None
        assert self._clip is not None
        assert self._timeline is not None
        pending = self._pending
        boundary_seconds = self._started_at_seconds + pending.switch_at_ms / 1000.0
        previous = self._clip
        natural_finish = (
            pending.switch_at_ms >= self._timeline.total_duration_ms
            and self._clip.loop_mode is not ActionLoopMode.HOLD_LAST_FRAME
        )
        self._clear_active(emit_frame=True)
        if natural_finish:
            self.clip_finished.emit(previous)
        else:
            self.clip_interrupted.emit(ActionInterruption(previous, pending.decision.name.lower()))
        self._start_at(pending.clip, boundary_seconds)
        self._last_elapsed_seconds = elapsed_seconds

    def _action_elapsed_ms(self, elapsed_seconds: float) -> int:
        return max(0, floor((elapsed_seconds - self._started_at_seconds) * 1000.0 + 1e-7))

    def _emit_frame_if_changed(self, playback_frame: PlaybackFrame) -> None:
        token = (playback_frame.cycle_index, playback_frame.sequence_index)
        if token == self._current_token:
            return
        self._current_token = token
        self._current_playback_frame = playback_frame
        self.frame_changed.emit(playback_frame)

    def _clear_active(self, *, emit_frame: bool) -> None:
        had_frame = self._current_playback_frame is not None
        self._clip = None
        self._timeline = None
        self._current_playback_frame = None
        self._current_token = None
        self._pending = None
        self._paused_at_seconds = None
        if emit_frame and had_frame:
            self.frame_changed.emit(None)

    def _validate_time(self, elapsed_seconds: float, *, allow_before_last: bool) -> None:
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("ActionPlayer elapsed time must be finite and nonnegative.")
        if not allow_before_last and elapsed_seconds < self._last_elapsed_seconds:
            raise ValueError("ActionPlayer elapsed time must be monotonic.")
