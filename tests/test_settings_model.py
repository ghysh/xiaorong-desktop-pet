"""Immutable Stage 9 settings schema tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from desktop_pet.settings.model import PetSize, UserSettings


def test_defaults_and_only_approved_sizes_are_defined() -> None:
    settings = UserSettings()
    assert settings.schema_version == 1
    assert settings.size is PetSize.DEFAULT
    assert [size.value for size in PetSize] == [(240, 360), (280, 420), (320, 480)]
    assert all((size.width * 3 == size.height * 2) for size in PetSize)
    with pytest.raises(ValueError, match="Unsupported"):
        PetSize.from_dimensions(300, 450)
    with pytest.raises(FrozenInstanceError):
        settings.window_x = 1  # type: ignore[misc]


def test_schema_coordinates_and_field_types_are_validated() -> None:
    with pytest.raises(ValueError, match="schema"):
        UserSettings(schema_version=2)
    with pytest.raises(ValueError, match="both"):
        UserSettings(window_x=10)
    with pytest.raises(ValueError, match="screen name"):
        UserSettings(screen_name="DISPLAY")
    with pytest.raises(ValueError, match="boolean"):
        UserSettings(animation_enabled=1)  # type: ignore[arg-type]
