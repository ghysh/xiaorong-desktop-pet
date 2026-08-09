"""Integration checks for state priority and Stage 7 drag-tilt reuse."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from desktop_pet.animation.controller import AnimationController
from desktop_pet.app import create_application
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.behavior.transition import is_transition_allowed
from desktop_pet.config import AnimationConfig, BehaviorConfig


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def test_every_automatic_state_allows_drag_override() -> None:
    assert all(is_transition_allowed(state, PetState.DRAGGING) for state in AUTOMATIC_STATES)


def test_animation_drag_enters_settling_and_restores_without_widget_inertia() -> None:
    application = create_application(["pytest-behavior-drag"])
    controller = AnimationController(
        AnimationConfig(),
        behavior_config=BehaviorConfig(behavior_seed=5, starting_duration_seconds=0.15),
    )
    assert isinstance(application, QApplication)
    controller.start()
    for _ in range(20):
        if controller.behavior_controller.current_state in AUTOMATIC_STATES:
            break
        _wait(25)
    assert controller.behavior_controller.current_state in AUTOMATIC_STATES
    prior_state = controller.behavior_controller.current_state
    controller.begin_drag(QPoint(0, 0))
    controller.update_drag(QPoint(160, 0), elapsed_ms=280)
    drag_rotation = controller.current_transform.rotation_degrees
    assert controller.behavior_controller.current_state is PetState.DRAGGING
    assert drag_rotation < 0.0
    assert abs(drag_rotation) <= controller.effective_drag_tilt_max_degrees
    controller.end_drag()
    assert controller.behavior_controller.current_state is PetState.SETTLING
    _wait(260)
    assert not controller.is_returning
    assert controller.behavior_controller.current_state is prior_state
    controller.shutdown()
