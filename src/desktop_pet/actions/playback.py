"""Pure absolute-time timeline construction for every ActionLoopMode."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from desktop_pet.actions.model import ActionClip, ActionFrame, ActionLoopMode


@dataclass(frozen=True, slots=True)
class PlaybackFrame:
    frame: ActionFrame
    frame_index: int
    sequence_index: int
    cycle_index: int
    direction: int
    starts_at_ms: int
    ends_at_ms: int


class PlaybackTimeline:
    """Precompute a bounded deterministic timeline; no disk, Qt, or wall clock access."""

    def __init__(self, clip: ActionClip, loop_count: int | None = None) -> None:
        if not isinstance(clip, ActionClip):
            raise ValueError("PlaybackTimeline requires an ActionClip.")
        selected_loops = clip.default_loop_count if loop_count is None else loop_count
        if isinstance(selected_loops, bool) or not isinstance(selected_loops, int) or selected_loops <= 0:
            raise ValueError("Playback loop count must be a positive integer.")
        if clip.loop_mode in {ActionLoopMode.ONCE, ActionLoopMode.HOLD_LAST_FRAME}:
            selected_loops = 1
        self.clip = clip
        self.loop_count = selected_loops
        self._cycle_indices = self._build_cycle_indices(clip)
        self.cycle_duration_ms = sum(clip.frames[index].duration_ms for index, _direction in self._cycle_indices)
        self.total_duration_ms = self.cycle_duration_ms * selected_loops
        self._entries = self._build_entries()
        self._starts = tuple(entry.starts_at_ms for entry in self._entries)

    @property
    def entries(self) -> tuple[PlaybackFrame, ...]:
        return self._entries

    def frame_at(self, elapsed_ms: int) -> PlaybackFrame | None:
        if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int) or elapsed_ms < 0:
            raise ValueError("Playback elapsed milliseconds must be a nonnegative integer.")
        if elapsed_ms >= self.total_duration_ms:
            if self.clip.loop_mode is ActionLoopMode.HOLD_LAST_FRAME:
                return self._entries[-1]
            return None
        index = bisect_right(self._starts, elapsed_ms) - 1
        return self._entries[max(0, index)]

    def frame_boundary_after(self, elapsed_ms: int) -> int:
        entry = self.frame_at(min(elapsed_ms, max(0, self.total_duration_ms - 1)))
        if entry is None:
            return self.total_duration_ms
        return min(entry.ends_at_ms, self.total_duration_ms)

    def cycle_boundary_after(self, elapsed_ms: int) -> int:
        if elapsed_ms >= self.total_duration_ms:
            return self.total_duration_ms
        cycle = elapsed_ms // self.cycle_duration_ms
        return min((cycle + 1) * self.cycle_duration_ms, self.total_duration_ms)

    @staticmethod
    def _build_cycle_indices(clip: ActionClip) -> tuple[tuple[int, int], ...]:
        count = len(clip.frames)
        forward = tuple((index, 1) for index in range(count))
        if clip.loop_mode is not ActionLoopMode.PING_PONG or count <= 2:
            return forward
        backward = tuple((index, -1) for index in range(count - 2, 0, -1))
        return forward + backward

    def _build_entries(self) -> tuple[PlaybackFrame, ...]:
        entries: list[PlaybackFrame] = []
        cursor_ms = 0
        sequence_index = 0
        for cycle_index in range(self.loop_count):
            for frame_index, direction in self._cycle_indices:
                frame = self.clip.frames[frame_index]
                end_ms = cursor_ms + frame.duration_ms
                entries.append(
                    PlaybackFrame(
                        frame=frame,
                        frame_index=frame_index,
                        sequence_index=sequence_index,
                        cycle_index=cycle_index,
                        direction=direction,
                        starts_at_ms=cursor_ms,
                        ends_at_ms=end_ms,
                    )
                )
                cursor_ms = end_ms
                sequence_index += 1
        return tuple(entries)
