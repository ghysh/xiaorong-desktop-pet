"""Immutable, versioned settings model for Stage 9 user preferences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PetSize(Enum):
    """The only approved 2:3 logical window sizes."""

    SMALL = (240, 360)
    DEFAULT = (280, 420)
    LARGE = (320, 480)

    @property
    def width(self) -> int:
        return self.value[0]

    @property
    def height(self) -> int:
        return self.value[1]

    @classmethod
    def from_dimensions(cls, width: int, height: int) -> PetSize:
        for size in cls:
            if size.value == (width, height):
                return size
        raise ValueError(f"Unsupported desktop-pet size: {width}x{height}.")


@dataclass(frozen=True, slots=True)
class UserSettings:
    """Validated user preferences with no asset paths or sensitive values."""

    schema_version: int = 1
    size: PetSize = PetSize.DEFAULT
    always_on_top: bool = True
    animation_enabled: bool = True
    behavior_enabled: bool = True
    click_reaction_enabled: bool = True
    remember_position: bool = True
    window_x: int | None = None
    window_y: int | None = None
    screen_name: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("Settings schema_version must be 1.")
        if not isinstance(self.size, PetSize):
            raise ValueError("Settings size must be a defined PetSize.")
        for name in (
            "always_on_top",
            "animation_enabled",
            "behavior_enabled",
            "click_reaction_enabled",
            "remember_position",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"Settings field {name} must be boolean.")
        coordinates = (self.window_x, self.window_y)
        if (coordinates[0] is None) != (coordinates[1] is None):
            raise ValueError("Window coordinates must either both exist or both be empty.")
        for value in coordinates:
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError("Window coordinates must be integers when present.")
        if self.screen_name is not None and (
            not isinstance(self.screen_name, str) or not self.screen_name.strip()
        ):
            raise ValueError("Screen name must be a nonempty string when present.")
        if coordinates[0] is None and self.screen_name is not None:
            raise ValueError("A screen name cannot be saved without window coordinates.")
