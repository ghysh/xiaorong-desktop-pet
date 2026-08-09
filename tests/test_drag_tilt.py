"""Deterministic drag-tilt direction, smoothing, and release tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from desktop_pet.animation.controller import AnimationController
from desktop_pet.app import create_application
from desktop_pet.config import AnimationConfig


@pytest.fixture()
def application() -> QApplication:
    return create_application(["pytest-drag-tilt"])


def _wait_for_events(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_right_and_left_drag_use_consistent_lagging_tilt_directions(application: QApplication) -> None:
    controller = AnimationController(AnimationConfig())
    controller.start()
    controller.begin_drag(QPoint(0, 0))
    controller.update_drag(QPoint(120, 0), elapsed_ms=100)
    right_drag_rotation = controller.current_transform.rotation_degrees
    controller.end_drag()
    controller.begin_drag(QPoint(120, 0))
    controller.update_drag(QPoint(0, 0), elapsed_ms=200)
    left_drag_rotation = controller.current_transform.rotation_degrees

    assert right_drag_rotation < 0.0
    assert left_drag_rotation > 0.0
    controller.stop()


def test_drag_tilt_is_smoothed_and_clamped(application: QApplication) -> None:
    controller = AnimationController(AnimationConfig())
    controller.start()
    controller.begin_drag(QPoint(0, 0))
    controller.update_drag(QPoint(1000, 0), elapsed_ms=100)
    first_rotation = controller.current_transform.rotation_degrees
    controller.update_drag(QPoint(2000, 0), elapsed_ms=200)

    assert abs(first_rotation) < controller.effective_drag_tilt_max_degrees
    assert abs(controller.current_transform.rotation_degrees) <= controller.effective_drag_tilt_max_degrees
    controller.stop()


def test_slower_drag_has_smaller_rotation_and_release_completes_in_range(application: QApplication) -> None:
    controller = AnimationController(AnimationConfig())
    emitted = []
    controller.transform_changed.connect(emitted.append)
    controller.start()
    controller.begin_drag(QPoint(0, 0))
    controller.update_drag(QPoint(10, 0), elapsed_ms=100)
    slow_rotation = abs(controller.current_transform.rotation_degrees)
    controller.end_drag()
    _wait_for_events(250)

    assert slow_rotation < 2.0
    assert not controller.is_returning
    assert any(abs(transform.rotation_degrees) < 1e-9 for transform in emitted)
    controller.stop()
