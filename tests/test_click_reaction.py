"""Determinism, timing, and clipping checks for paint-only click feedback."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.app import create_application
from desktop_pet.interaction.click_reaction import click_reaction_transform
from desktop_pet.ui.pet_window import PetWindow


def test_curve_has_documented_keyframes_and_returns_exact_identity() -> None:
    assert click_reaction_transform(0).is_close(AnimationTransform.identity())
    assert click_reaction_transform(90).as_tuple() == (0.0, 1.0, 1.01, 0.992, 0.0)
    assert click_reaction_transform(180).as_tuple() == (0.0, -0.5, 0.997, 1.003, 0.0)
    assert click_reaction_transform(260).is_close(AnimationTransform.identity())
    assert click_reaction_transform(140) == click_reaction_transform(140)


def test_all_diagnostic_click_samples_remain_inside_the_window() -> None:
    create_application(["pytest-click-clipping"])
    window = PetWindow()
    assert all(
        window.is_transform_safe(click_reaction_transform(elapsed))
        for elapsed in (0, 60, 90, 140, 180, 220, 260)
    )
    window.close()
