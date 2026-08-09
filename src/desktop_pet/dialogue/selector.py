"""Local reproducible random selection with immediate-repeat avoidance."""

from __future__ import annotations

import random
import secrets
from collections.abc import Sequence


class DialogueSelector:
    """Select cached dialogue without changing global random state or source order."""

    def __init__(self, dialogues: Sequence[str], seed: int | None = None) -> None:
        immutable = tuple(dialogues)
        if not immutable:
            raise ValueError("At least one dialogue is required.")
        if any(not isinstance(dialogue, str) or not dialogue for dialogue in immutable):
            raise ValueError("Every dialogue must be a non-empty string.")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise ValueError("Dialogue seed must be an integer or None.")
        self._dialogues = immutable
        self._seed = secrets.randbits(64) if seed is None else seed
        self._random = random.Random(self._seed)
        self._last_index: int | None = None
        self._selection_count = 0

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def dialogues(self) -> tuple[str, ...]:
        return self._dialogues

    @property
    def selection_count(self) -> int:
        return self._selection_count

    def choose(self) -> str:
        """Choose once per request and avoid the prior index when alternatives exist."""
        if len(self._dialogues) == 1:
            index = 0
        elif self._last_index is None:
            index = self._random.randrange(len(self._dialogues))
        else:
            candidate = self._random.randrange(len(self._dialogues) - 1)
            index = candidate + (candidate >= self._last_index)
        self._last_index = index
        self._selection_count += 1
        return self._dialogues[index]
