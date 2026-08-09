"""Timer-free autonomous blink scheduling and request control."""

from desktop_pet.blink.controller import BlinkController
from desktop_pet.blink.scheduler import BlinkScheduler
from desktop_pet.config import BlinkConfig

__all__ = ["BlinkConfig", "BlinkController", "BlinkScheduler"]
