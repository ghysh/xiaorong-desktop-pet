"""Shared drowsy-sleep menu, persistence, demo, and interruption integration."""

from __future__ import annotations

import os
from math import isinf
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMenu

from desktop_pet.actions.sleep import DROWSY_SLEEP_ACTION_ID
from desktop_pet.app import DesktopPetApplicationController, create_application
from desktop_pet.behavior.state import PetState
from desktop_pet.settings.repository import SettingsRepository


def _submenu(menu: QMenu, text: str) -> QMenu:
    action = next(action for action in menu.actions() if action.text() == text)
    submenu = action.menu()
    assert submenu is not None
    return submenu


def _controller(tmp_path: Path, name: str) -> DesktopPetApplicationController:
    application = create_application([name])
    return DesktopPetApplicationController(
        application,
        config_directory=tmp_path,
        enable_tray=False,
    )


def test_shared_menu_has_exclusive_persistent_drowsy_sleep_actions(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "pytest-drowsy-menu")
    registry = controller.action_registry
    window_menu = registry.create_menu(controller.pet_window)
    tray_menu = registry.create_menu(controller.pet_window, tray_menu=True)

    window_sleep_menu = _submenu(_submenu(window_menu, "自主动作"), "打瞌睡")
    tray_sleep_menu = _submenu(_submenu(tray_menu, "自主动作"), "打瞌睡")
    expected_actions = (
        registry.drowsy_sleep_on_action,
        registry.drowsy_sleep_off_action,
        registry.drowsy_sleep_demo_action,
    )
    assert tuple(action for action in window_sleep_menu.actions() if not action.isSeparator()) == expected_actions
    assert tuple(action for action in tray_sleep_menu.actions() if not action.isSeparator()) == expected_actions
    assert registry.drowsy_sleep_action_group.isExclusive()
    assert registry.drowsy_sleep_on_action.isChecked()
    assert not registry.drowsy_sleep_off_action.isChecked()

    registry.drowsy_sleep_off_action.trigger()
    assert controller.settings_service.current.drowsy_sleep_enabled is False
    assert registry.drowsy_sleep_off_action.isChecked()
    assert not registry.drowsy_sleep_on_action.isChecked()
    assert SettingsRepository(tmp_path).load().drowsy_sleep_enabled is False

    registry.drowsy_sleep_on_action.trigger()
    assert controller.settings_service.current.drowsy_sleep_enabled is True
    assert registry.drowsy_sleep_on_action.isChecked()
    assert len(controller.pet_window.findChildren(QTimer)) == 1

    window_menu.deleteLater()
    tray_menu.deleteLater()
    controller.shutdown()
    controller.pet_window.close()


def test_disabling_stops_scheduling_and_interrupts_active_sleep(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "pytest-drowsy-disable")
    controller.start()
    controller.application.processEvents()
    animation = controller.animation_controller
    assert animation.play_drowsy_sleep_demo()
    assert animation.action_player.current_clip is not None

    started_at = animation.action_player.last_elapsed_seconds
    animation.action_player.update(started_at + 2.2)
    frame = animation.action_player.current_frame
    assert frame is not None
    animation._set_sleep_bubble(
        animation.sleep_controller.bubble_state(started_at + 2.2, frame.event),
        force=True,
    )
    assert animation.sleep_bubble_state.visible

    controller.action_registry.drowsy_sleep_off_action.trigger()
    assert animation.action_player.current_clip is None
    assert controller.pet_window.current_overlay_frame is None
    assert not animation.sleep_bubble_state.visible
    assert not animation.sleep_controller.enabled
    assert isinf(animation.sleep_controller.next_due_seconds)
    assert controller.settings_service.current.drowsy_sleep_enabled is False
    assert (
        animation.sleep_controller.update(
            started_at + 10_000.0,
            PetState.IDLE_CALM,
            None,
        )
        is None
    )

    controller.shutdown()
    controller.pet_window.close()


def test_demo_runs_while_disabled_without_changing_setting_or_stacking(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "pytest-drowsy-demo")
    controller.set_drowsy_sleep_enabled(False)
    controller.start()
    controller.application.processEvents()
    animation = controller.animation_controller
    starts: list[str] = []
    animation.action_player.clip_started.connect(
        lambda clip: starts.append(clip.action_id)
    )

    controller.action_registry.drowsy_sleep_demo_action.trigger()
    assert animation.action_player.current_clip is not None
    assert animation.action_player.current_clip.action_id == DROWSY_SLEEP_ACTION_ID
    assert controller.settings_service.current.drowsy_sleep_enabled is False
    assert not animation.play_drowsy_sleep_demo()
    assert starts == [DROWSY_SLEEP_ACTION_ID]

    started_at = animation.action_player.last_elapsed_seconds
    duration_seconds = sum(
        frame.duration_ms for frame in animation.action_player.current_clip.frames
    ) / 1000.0
    animation.action_player.update(started_at + duration_seconds)
    assert animation.action_player.current_clip is None
    assert controller.settings_service.current.drowsy_sleep_enabled is False
    assert not animation.sleep_controller.enabled
    assert isinf(animation.sleep_controller.next_due_seconds)
    assert len(controller.pet_window.findChildren(QTimer)) == 1

    controller.shutdown()
    controller.pet_window.close()
