"""Independent nasal-bubble layer and replacement-frame rendering checks."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.actions.sleep import DROWSY_SLEEP_ACTION_ID
from desktop_pet.app import create_application
from desktop_pet.ui.pet_window import PetWindow


def test_sleep_frame_replaces_default_character_and_bubble_is_a_separate_layer() -> None:
    create_application(["pytest-sleep-bubble"])
    window = PetWindow()
    animation = window.animation_controller
    clip = window.runtime_action_registry.get(DROWSY_SLEEP_ACTION_ID)
    animation.action_player.start(clip, 0.0)
    animation.action_player.update(2.0)
    frame = animation.action_player.current_frame
    assert frame is not None and frame.event == "sleep_bubble"
    state = animation.sleep_controller.bubble_state(1.7, frame.event)
    window._on_sleep_bubble_changed(state)
    assert window._current_overlay_replaces_base
    assert window._sleep_bubble_state.visible
    assert "bubble" not in frame.asset_path
    window.repaint()
    window.close()


def test_middle_keyframes_are_opaque_swaps_and_only_boundaries_retain_a_fade_source() -> None:
    create_application(["pytest-sleep-keyframes"])
    window = PetWindow()
    animation = window.animation_controller
    clip = window.runtime_action_registry.get(DROWSY_SLEEP_ACTION_ID)
    starts_at_ms: dict[str, int] = {}
    elapsed_ms = 0
    for frame in clip.frames:
        starts_at_ms.setdefault(frame.event or "", elapsed_ms)
        elapsed_ms += frame.duration_ms

    animation.action_player.start(clip, 0.0)
    animation.action_player.update((starts_at_ms["sit_down_start"] + 1) / 1000.0)
    assert window._previous_replacement_pixmap is not None

    animation.action_player.update((starts_at_ms["sit_down_lower"] + 1) / 1000.0)
    assert window._previous_replacement_pixmap is None
    animation.action_player.update((starts_at_ms["rise_up"] + 1) / 1000.0)
    assert window._previous_replacement_pixmap is None
    animation.action_player.update((starts_at_ms["rub_eye"] + 1) / 1000.0)
    assert window._previous_replacement_pixmap is None

    animation.action_player.update((starts_at_ms["return_default"] + 1) / 1000.0)
    assert window._previous_replacement_pixmap is not None
    window.close()


def test_sleep_feature_adds_no_second_qtimer() -> None:
    create_application(["pytest-sleep-one-timer"])
    window = PetWindow()
    from PySide6.QtCore import QTimer

    assert len(window.findChildren(QTimer)) == 1
    window.close()
