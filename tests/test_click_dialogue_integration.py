"""Effective-click signal and dialogue feedback integration tests."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop_pet.app import DesktopPetApplicationController, create_application
from desktop_pet.behavior.controller import BehaviorController
from desktop_pet.behavior.state import PetState
from desktop_pet.config import BehaviorConfig
from desktop_pet.interaction.controller import InteractionController


def _gesture(interaction: InteractionController, **overrides: object) -> bool:
    arguments = {
        "elapsed_seconds": 0.1,
        "button": Qt.MouseButton.LeftButton,
        "press_hit": True,
        "release_hit": True,
        "movement_distance": 0.0,
        "drag_threshold": 10,
        "held_ms": 50,
        "context_menu_open": False,
    }
    arguments.update(overrides)
    return interaction.try_start_click(**arguments)


def _interaction() -> tuple[BehaviorController, InteractionController]:
    behavior = BehaviorController(BehaviorConfig(behavior_seed=1))
    behavior.start(0.0)
    return behavior, InteractionController(behavior)


def test_character_clicked_emits_once_only_for_the_existing_valid_gesture_contract() -> None:
    invalid_cases = (
        {"press_hit": False},
        {"release_hit": False},
        {"movement_distance": 10.0},
        {"button": Qt.MouseButton.RightButton},
        {"held_ms": 501},
        {"context_menu_open": True},
    )
    for invalid in invalid_cases:
        _, interaction = _interaction()
        emitted: list[bool] = []
        interaction.character_clicked.connect(lambda: emitted.append(True))
        assert not _gesture(interaction, **invalid)
        assert emitted == []

    _, interaction = _interaction()
    emitted = []
    interaction.character_clicked.connect(lambda: emitted.append(True))
    assert _gesture(interaction)
    assert emitted == [True]


def test_click_reaction_and_dialogue_start_together_and_repeat_reuses_bubble(tmp_path: Path) -> None:
    application = create_application(["pytest-click-dialogue-integration"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path, enable_tray=False)
    controller.start()
    application.processEvents()
    bubble_identity = id(controller.dialogue_bubble)

    assert _gesture(controller.interaction_controller)
    application.processEvents()
    assert controller.behavior_controller.current_state is PetState.CLICK_REACTION
    assert controller.dialogue_bubble.isVisible()
    first_count = controller.dialogue_bubble.display_count

    # The active 260 ms transform is not restarted, but the valid click signal still refreshes dialogue.
    assert not _gesture(controller.interaction_controller, elapsed_seconds=0.12)
    application.processEvents()
    assert id(controller.dialogue_bubble) == bubble_identity
    assert controller.dialogue_bubble.display_count == first_count + 1
    assert sum(widget is controller.dialogue_bubble for widget in QApplication.topLevelWidgets()) == 1
    controller.shutdown()
    controller.pet_window.close()


def test_disabled_paused_and_stopped_states_never_show_dialogue(tmp_path: Path) -> None:
    application = create_application(["pytest-click-dialogue-disabled"])
    controller = DesktopPetApplicationController(application, config_directory=tmp_path, enable_tray=False)
    controller.start()
    controller.settings_service.set_click_reaction_enabled(False)
    application.processEvents()

    assert not _gesture(controller.interaction_controller)
    assert not controller.dialogue_bubble.isVisible()

    controller.settings_service.set_click_reaction_enabled(True)
    controller.behavior_controller.pause(controller.animation_controller.elapsed_seconds)
    assert not _gesture(
        controller.interaction_controller,
        elapsed_seconds=controller.animation_controller.elapsed_seconds,
    )
    assert not controller.dialogue_bubble.isVisible()

    controller.shutdown()
    assert controller.behavior_controller.current_state is PetState.STOPPED
    assert not _gesture(
        controller.interaction_controller,
        elapsed_seconds=controller.animation_controller.elapsed_seconds,
    )
    assert not controller.dialogue_bubble.isVisible()
    controller.pet_window.close()
