"""Behavior-profile clipping, transparency, caching, and position stability tests."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from desktop_pet.animation.idle_motion import IdleMotionProfile
from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.app import create_application
from desktop_pet.behavior.profiles import ProfileBlend, calculate_behavior_transform, profile_for_state
from desktop_pet.behavior.state import PetState
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_sha256


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_all_behavior_profiles_and_blends_remain_inside_actual_alpha_canvas() -> None:
    application = create_application(["pytest-behavior-rendering"])
    window = PetWindow()
    base = IdleMotionProfile.from_config(window.config.animation)
    states = (
        PetState.IDLE_CALM,
        PetState.IDLE_QUIET,
        PetState.IDLE_SWAY,
        PetState.RESTING,
    )
    assert isinstance(application, QApplication)
    for state in states:
        profile = profile_for_state(state, window.config.behavior)
        assert all(
            window.is_transform_safe(calculate_behavior_transform(sample / 10, base, profile))
            for sample in range(100)
        )
    blend = ProfileBlend(
        profile_for_state(PetState.IDLE_SWAY, window.config.behavior),
        profile_for_state(PetState.RESTING, window.config.behavior),
        0.0,
        window.config.behavior.profile_transition_duration_seconds,
    )
    assert all(
        window.is_transform_safe(
            calculate_behavior_transform(
                sample / 100,
                base,
                blend.profile_at(sample / 100),
            )
        )
        for sample in range(36)
    )
    assert window.is_transform_safe(AnimationTransform(rotation_degrees=window.effective_drag_tilt_max_degrees))
    window.close()


def test_behavior_does_not_move_widget_reload_asset_or_break_transparency() -> None:
    application = create_application(["pytest-behavior-position"])
    assert application is not None
    window = PetWindow()
    window.move(QPoint(130, 90))
    before_position = window.pos()
    before_hash = runtime_asset_sha256(window.asset_path)
    cached_key = window._scaled_pixmap.cacheKey()
    window.show()
    _wait(650)
    captured = window.grab().toImage()

    assert window.pos() == before_position
    assert window._scaled_pixmap.cacheKey() == cached_key
    assert captured.pixelColor(0, 0).alpha() == 0
    assert runtime_asset_sha256(window.asset_path) == before_hash
    window.close()
