"""Pure-Python, locally seeded behavior scheduling with no system-time dependency."""

from __future__ import annotations

import random
import secrets

from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.behavior.transition import automatic_targets
from desktop_pet.config import BehaviorConfig, StateDurationRange


class BehaviorScheduler:
    """Choose automatic states and durations from one isolated Random instance."""

    _WEIGHTS = {
        PetState.IDLE_CALM: (
            (PetState.IDLE_QUIET, 0.40),
            (PetState.IDLE_SWAY, 0.35),
            (PetState.RESTING, 0.25),
        ),
        PetState.IDLE_QUIET: (
            (PetState.IDLE_CALM, 0.65),
            (PetState.IDLE_SWAY, 0.35),
        ),
        PetState.IDLE_SWAY: (
            (PetState.IDLE_CALM, 0.70),
            (PetState.IDLE_QUIET, 0.30),
        ),
        PetState.RESTING: (
            (PetState.IDLE_CALM, 0.75),
            (PetState.IDLE_QUIET, 0.25),
        ),
    }

    def __init__(self, config: BehaviorConfig) -> None:
        self._config = config
        self._actual_seed = config.behavior_seed if config.behavior_seed is not None else secrets.randbits(64)
        self._random = random.Random(self._actual_seed)

    @property
    def actual_seed(self) -> int:
        """Return the one startup seed needed to reproduce this scheduler."""
        return self._actual_seed

    @classmethod
    def transition_weights(cls, state: PetState) -> tuple[tuple[PetState, float], ...]:
        """Expose immutable weights for diagnostics and validation."""
        try:
            return cls._WEIGHTS[state]
        except KeyError as error:
            raise ValueError(f"State is not schedulable: {state.name}") from error

    def choose_next_state(self, current_state: PetState) -> PetState:
        """Choose one legal non-self automatic target using the isolated generator."""
        weighted_targets = self.transition_weights(current_state)
        allowed = automatic_targets(current_state)
        draw = self._random.random() * sum(weight for _, weight in weighted_targets)
        cumulative = 0.0
        for state, weight in weighted_targets:
            cumulative += weight
            if draw <= cumulative:
                selected = state
                break
        else:
            selected = weighted_targets[-1][0]
        if selected is current_state or selected not in AUTOMATIC_STATES or selected not in allowed:
            raise RuntimeError("Behavior scheduler produced an invalid automatic target.")
        return selected

    def choose_duration(self, state: PetState) -> float:
        """Sample a duration only for an automatic state and remain inside its configured range."""
        duration_range = self.duration_range(state)
        return self._random.uniform(duration_range.minimum_seconds, duration_range.maximum_seconds)

    def duration_range(self, state: PetState) -> StateDurationRange:
        """Return the configured duration range for an automatic state."""
        ranges = {
            PetState.IDLE_CALM: self._config.calm_duration,
            PetState.IDLE_QUIET: self._config.quiet_duration,
            PetState.IDLE_SWAY: self._config.sway_duration,
            PetState.RESTING: self._config.resting_duration,
        }
        try:
            return ranges[state]
        except KeyError as error:
            raise ValueError(f"State has no automatic duration: {state.name}") from error
