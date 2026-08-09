"""Bubble geometry, settings, hide/show, and shutdown lifecycle tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer

from desktop_pet.app import DesktopPetApplicationController, create_application
from desktop_pet.settings.model import PetSize


def _show_dialogue(controller: DesktopPetApplicationController) -> None:
    controller.interaction_controller.character_clicked.emit()
    controller.application.processEvents()
    assert controller.dialogue_bubble.isVisible()


def test_move_resize_hide_show_and_shutdown_lifecycle(tmp_path: Path) -> None:
    application = create_application(["pytest-dialogue-lifecycle"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path, enable_tray=False)
    controller.start()
    application.processEvents()
    _show_dialogue(controller)
    first_position = controller.dialogue_bubble.pos()

    controller.pet_window.move(controller.pet_window.pos() + QPoint(-80, -40))
    application.processEvents()
    assert controller.dialogue_bubble.pos() != first_position

    for size in PetSize:
        controller.settings_service.set_size(size)
        application.processEvents()
        screen = application.screenAt(controller.dialogue_bubble.frameGeometry().center())
        assert screen is not None
        safe = screen.availableGeometry().adjusted(12, 12, -12, -12)
        assert safe.contains(controller.dialogue_bubble.frameGeometry())

    controller.pet_window.hide()
    application.processEvents()
    assert not controller.dialogue_bubble.isVisible()
    assert not controller.dialogue_bubble.hide_timer.isActive()

    controller.show_pet_window()
    application.processEvents()
    assert not controller.dialogue_bubble.isVisible()

    controller.shutdown()
    assert not controller.dialogue_bubble.isVisible()
    assert not controller.dialogue_bubble.hide_timer.isActive()
    controller.pet_window.close()


def test_topmost_setting_syncs_without_new_window_or_timer(tmp_path: Path) -> None:
    application = create_application(["pytest-dialogue-topmost"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path, enable_tray=False)
    controller.start()
    _show_dialogue(controller)
    bubble_identity = id(controller.dialogue_bubble)
    timer_identity = id(controller.dialogue_bubble.hide_timer)
    text = controller.dialogue_bubble.current_text

    controller.settings_service.set_always_on_top(False)
    application.processEvents()

    assert id(controller.dialogue_bubble) == bubble_identity
    assert id(controller.dialogue_bubble.hide_timer) == timer_identity
    assert controller.dialogue_bubble.current_text == text
    assert controller.dialogue_bubble.isVisible()
    assert not controller.dialogue_bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert len(controller.pet_window.findChildren(QTimer)) == 1
    assert len(controller.dialogue_bubble.findChildren(QTimer)) == 1
    controller.shutdown()
    controller.pet_window.close()
