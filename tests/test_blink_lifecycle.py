"""Integrated pause, hide, drag, click, stop, and one-timer blink lifecycle."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer

from desktop_pet.app import create_application
from desktop_pet.behavior.state import PetState
from desktop_pet.config import BehaviorConfig, PetWindowConfig
from desktop_pet.ui.pet_window import PetWindow


def _start_blink(window: PetWindow) -> None:
    controller = window.animation_controller
    if not controller.timer.isActive():
        controller.start()
        loop = QEventLoop()
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    clip = window.runtime_action_registry.get("blink_normal")
    controller.action_player.start(clip, controller.elapsed_seconds)


def test_click_and_drag_immediately_clear_active_blink() -> None:
    create_application(["pytest-blink-click-drag"])
    window = PetWindow(PetWindowConfig(behavior=BehaviorConfig(starting_duration_seconds=0.001)))
    _start_blink(window)
    assert window.current_overlay_frame is not None
    accepted = window.animation_controller.try_start_click(
        elapsed_seconds=window.animation_controller.elapsed_seconds,
        button=Qt.MouseButton.LeftButton,
        press_hit=True,
        release_hit=True,
        movement_distance=0.0,
        drag_threshold=5,
        held_ms=50,
        context_menu_open=False,
    )
    assert accepted
    assert window.current_overlay_frame is None
    window.interaction_controller.cancel_active(window.animation_controller.elapsed_seconds)
    _start_blink(window)
    window.animation_controller.begin_drag(QPoint(100, 100))
    assert window.current_overlay_frame is None
    window.animation_controller.end_drag()
    window.close()


def test_pause_and_shutdown_clear_overlay_and_keep_one_timer() -> None:
    create_application(["pytest-blink-lifecycle"])
    window = PetWindow()
    _start_blink(window)
    window.animation_controller.pause()
    assert window.current_overlay_frame is None
    assert len(window.findChildren(QTimer)) == 1
    assert not window.animation_controller.timer.isActive()
    window.animation_controller.shutdown()
    assert window.behavior_controller.current_state is PetState.STOPPED
    assert window.animation_controller.action_player.current_clip is None
    window.close()
