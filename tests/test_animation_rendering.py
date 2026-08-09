"""Offscreen rendering and clipping regression checks for Stage 7 transforms."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.app import create_application
from desktop_pet.ui import pet_window
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_alpha_bounds, runtime_asset_sha256


@pytest.fixture()
def application() -> QApplication:
    return create_application(["pytest-animation-rendering"])


def test_cached_pixmap_alpha_anchor_and_conservative_extrema_are_safe(application: QApplication) -> None:
    window = PetWindow()
    source_bounds = runtime_asset_alpha_bounds(window.asset_path)

    assert application is not None
    assert window._scaled_pixmap.size().toTuple() == (280, 420)
    assert source_bounds == window._source_alpha_bounds
    assert window.animation_anchor.y() == pytest.approx(window.alpha_bounds_window.bottom())
    assert all(window.clipping_checks().values())
    assert window.is_transform_safe(
        AnimationTransform(
            offset_y=-1.5,
            scale_x=1.002,
            scale_y=1.008,
            rotation_degrees=0.7 + window.effective_drag_tilt_max_degrees,
        )
    )
    window.close()


def test_multiple_paints_reuse_cached_asset_and_keep_transparent_margin(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = PetWindow()
    before_hash = runtime_asset_sha256(window.asset_path)
    original_pixmap_key = window._scaled_pixmap.cacheKey()
    calls = []

    def unexpected_load(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("paint frames must not reload the runtime PNG")

    monkeypatch.setattr(pet_window, "load_runtime_asset", unexpected_load)
    window.show()
    application.processEvents()
    for rotation in (-0.7, 0.0, 0.7):
        window._on_transform_changed(AnimationTransform(offset_y=1.0, rotation_degrees=rotation))
        application.processEvents()
        captured = window.grab().toImage()
        assert captured.pixelColor(0, 0).alpha() == 0

    assert calls == []
    assert window._scaled_pixmap.cacheKey() == original_pixmap_key
    assert runtime_asset_sha256(window.asset_path) == before_hash
    window.close()
