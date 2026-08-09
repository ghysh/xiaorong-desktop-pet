"""Integrated Stage 9 ownership, persistence cadence, and terminal lifecycle checks."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer

from desktop_pet.app import DesktopPetApplicationController, create_application
from desktop_pet.behavior.state import PetState
from desktop_pet.paths import ANIMATIONS_DIR, FULLBODY_RUNTIME_MASTER
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256, runtime_asset_sha256


def test_controller_owns_one_of_each_and_only_one_high_frequency_timer(tmp_path: Path) -> None:
    application = create_application(["pytest-stage9-lifecycle"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path)
    assert controller.pet_window.animation_controller is controller.animation_controller
    assert controller.animation_controller.behavior_controller is controller.behavior_controller
    assert controller.animation_controller.interaction_controller is controller.interaction_controller
    assert len(controller.pet_window.findChildren(QTimer)) == 1
    assert controller.settings_dialog is None
    controller.show_settings()
    first_dialog = controller.settings_dialog
    controller.show_settings()
    assert controller.settings_dialog is first_dialog
    controller.shutdown()
    controller.pet_window.close()


def test_hide_show_exit_and_no_per_frame_settings_writes(tmp_path: Path) -> None:
    application = create_application(["pytest-stage9-hide-show"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path)
    controller.start()
    before_writes = controller.settings_repository.save_count
    loop = QEventLoop()
    QTimer.singleShot(80, loop.quit)
    loop.exec()
    assert controller.settings_repository.save_count == before_writes
    controller.pet_window.hide()
    application.processEvents()
    assert controller.behavior_controller.current_state is PetState.PAUSED
    controller.show_pet_window()
    application.processEvents()
    assert controller.behavior_controller.current_state is not PetState.PAUSED
    controller.shutdown()
    assert controller.behavior_controller.current_state is PetState.STOPPED
    assert not controller.animation_controller.timer.isActive()
    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    assert runtime_asset_sha256(FULLBODY_RUNTIME_MASTER) == EXPECTED_RUNTIME_ASSET_SHA256
    controller.pet_window.close()


def test_window_close_uses_the_same_terminal_application_exit_path(tmp_path: Path) -> None:
    application = create_application(["pytest-stage9-window-close"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path)
    controller.start()
    controller.pet_window.close()
    application.processEvents()
    assert controller.behavior_controller.current_state is PetState.STOPPED
    assert not controller.animation_controller.timer.isActive()
    assert controller._stopping
