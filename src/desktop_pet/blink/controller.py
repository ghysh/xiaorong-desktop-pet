"""Timer-free bridge from PetState and BlinkScheduler to ActionRequest."""

from __future__ import annotations

from desktop_pet.actions.model import ActionPriority
from desktop_pet.actions.request import ActionRequest, ActionRequestSource
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.blink.scheduler import BlinkScheduler
from desktop_pet.config import BlinkConfig


class BlinkController:
    """Submit one deduplicated autonomous blink request when the scheduler is due."""

    ACTION_ID = "blink_normal"

    def __init__(self, config: BlinkConfig) -> None:
        self.config = config
        self.scheduler = BlinkScheduler(config)
        self._initialized = False
        self._request_outstanding = False
        self._active = False
        self._stopped = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def request_outstanding(self) -> bool:
        return self._request_outstanding

    def update(self, elapsed_seconds: float, state: PetState) -> ActionRequest | None:
        if self._stopped or not self.config.enabled:
            return None
        if state is PetState.STOPPED:
            self.stop()
            return None
        if state not in AUTOMATIC_STATES:
            if self._initialized and not self.scheduler.is_paused:
                self.scheduler.pause(
                    elapsed_seconds,
                    minimum_resume_delay_seconds=self.config.resume_minimum_delay_seconds,
                )
            self._request_outstanding = False
            return None
        if not self._initialized:
            self.scheduler.start(elapsed_seconds)
            self._initialized = True
        elif self.scheduler.is_paused:
            self.scheduler.resume(
                elapsed_seconds,
                minimum_delay_seconds=self.config.resume_minimum_delay_seconds,
            )
        if self._request_outstanding or self._active or not self.scheduler.is_due(elapsed_seconds):
            return None
        self._request_outstanding = True
        return ActionRequest(
            action_id=self.ACTION_ID,
            priority=ActionPriority.BLINK,
            source=ActionRequestSource.AUTONOMOUS,
            requested_at_seconds=elapsed_seconds,
            reason="scheduled_blink",
        )

    def resolve_request(self, accepted: bool, elapsed_seconds: float) -> None:
        if not self._request_outstanding:
            return
        self._request_outstanding = False
        if accepted:
            self.scheduler.mark_started()
            self._active = True
        else:
            self.scheduler.mark_interrupted(elapsed_seconds)

    def on_clip_finished(self, elapsed_seconds: float) -> None:
        if not self._active:
            return
        self._active = False
        self.scheduler.mark_finished(elapsed_seconds)

    def on_clip_interrupted(self, elapsed_seconds: float) -> None:
        self._request_outstanding = False
        if not self._active:
            return
        self._active = False
        self.scheduler.mark_interrupted(elapsed_seconds)

    def pause(self, elapsed_seconds: float) -> None:
        self._request_outstanding = False
        self._active = False
        if not self._initialized:
            return
        self.scheduler.pause(
            elapsed_seconds,
            minimum_resume_delay_seconds=self.config.resume_minimum_delay_seconds,
        )

    def stop(self) -> None:
        self._stopped = True
        self._request_outstanding = False
        self._active = False
        self.scheduler.stop()
