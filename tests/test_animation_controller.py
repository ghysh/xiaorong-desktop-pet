"""Lifecycle checks for the controller's single timer and real-time state transitions."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from desktop_pet.animation.controller import AnimationController
from desktop_pet.app import create_application
from desktop_pet.config import AnimationConfig
from desktop_pet.paths import FULLBODY_RUNTIME_MASTER
from desktop_pet.ui.pet_window import runtime_asset_sha256


@pytest.fixture()
def application() -> QApplication:
    return create_application(["pytest-animation-controller"])


def _wait_for_events(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_controller_has_one_target_30fps_timer_and_can_start_stop(application: QApplication) -> None:
    controller = AnimationController(AnimationConfig())

    assert application is not None
    assert len(controller.findChildren(QTimer)) == 1
    assert controller.target_fps == 30
    assert controller.timer.interval() == 33
    controller.start()
    assert controller.timer.isActive()
    controller.stop()
    assert not controller.timer.isActive()


def test_controller_emits_idle_transform_and_pauses_float_while_dragging(application: QApplication) -> None:
    controller = AnimationController(AnimationConfig())
    emitted = []
    controller.transform_changed.connect(emitted.append)
    controller.start()
    _wait_for_events(50)
    controller.begin_drag(QPoint(10, 10))
    controller.update_drag(QPoint(110, 10), elapsed_ms=100)

    assert emitted
    assert controller.current_transform.offset_y == 0.0
    assert abs(controller.current_transform.scale_x - 1.0) <= 0.0006
    assert 1.0002 <= controller.current_transform.scale_y <= 1.0038
    assert controller.current_transform.rotation_degrees < 0.0
    controller.stop()


def test_controller_returns_after_release_and_does_not_modify_runtime_asset(application: QApplication) -> None:
    controller = AnimationController(AnimationConfig())
    emitted = []
    controller.transform_changed.connect(emitted.append)
    before_hash = runtime_asset_sha256(FULLBODY_RUNTIME_MASTER)
    controller.start()
    controller.begin_drag(QPoint(10, 10))
    controller.update_drag(QPoint(130, 10), elapsed_ms=100)
    controller.end_drag()
    _wait_for_events(280)
    after_hash = runtime_asset_sha256(FULLBODY_RUNTIME_MASTER)

    assert not controller.is_dragging
    assert not controller.is_returning
    assert any(abs(transform.rotation_degrees) < 1e-9 for transform in emitted)
    assert before_hash == after_hash
    controller.stop()
