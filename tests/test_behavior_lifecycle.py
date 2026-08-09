"""Window show, hide, resume, close, and one-timer lifecycle checks."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer

from desktop_pet.app import create_application
from desktop_pet.behavior.state import PetState
from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.ui.pet_window import PetWindow


def test_window_lifecycle_starts_pauses_resumes_and_stops_one_timer() -> None:
    application = create_application(["pytest-behavior-lifecycle"])
    window = PetWindow()
    assert window.behavior_controller.current_state is PetState.STARTING
    window.show()
    application.processEvents()
    assert window.animation_controller.timer.isActive()
    assert len(window.findChildren(QTimer)) == 1
    window.hide()
    application.processEvents()
    assert window.behavior_controller.current_state is PetState.PAUSED
    assert not window.animation_controller.timer.isActive()
    window.show()
    application.processEvents()
    assert window.behavior_controller.current_state is PetState.STARTING
    window.close()
    application.processEvents()
    assert window.behavior_controller.current_state is PetState.STOPPED
    assert not window.animation_controller.timer.isActive()


def test_behavior_runtime_has_no_background_thread_or_second_high_frequency_timer() -> None:
    behavior_sources = list((PROJECT_ROOT / "src" / "desktop_pet" / "behavior").glob("*.py"))
    all_source = "\n".join(path.read_text(encoding="utf-8") for path in behavior_sources)
    assert "QTimer" not in all_source
    assert "QThread" not in all_source
    assert "import threading" not in all_source
    assert Path(__file__).is_file()


def test_hide_show_keeps_animation_and_action_time_monotonic() -> None:
    application = create_application(["pytest-monotonic-resume"])
    window = PetWindow()
    window.show()
    loop = QEventLoop()
    QTimer.singleShot(40, loop.quit)
    loop.exec()
    before_hide = window.animation_controller.elapsed_seconds

    window.hide()
    application.processEvents()
    frozen = window.animation_controller.elapsed_seconds
    QTimer.singleShot(40, loop.quit)
    loop.exec()
    assert frozen >= before_hide
    assert window.animation_controller.elapsed_seconds == frozen

    window.show()
    application.processEvents()
    window.animation_controller._on_tick()
    assert window.animation_controller.elapsed_seconds >= frozen
    assert window.animation_controller.action_player.last_elapsed_seconds >= frozen
    window.close()
