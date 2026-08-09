"""Offscreen click-dialogue smoke test using an injected temporary text file."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

if "--offscreen" in os.sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent

from desktop_pet.app import create_application
from desktop_pet.dialogue.controller import DialogueController
from desktop_pet.dialogue.repository import DialogueRepository
from desktop_pet.dialogue.selector import DialogueSelector
from desktop_pet.interaction.hit_test import is_character_pixel
from desktop_pet.settings.model import PetSize
from desktop_pet.ui.dialogue_bubble import DialogueBubble
from desktop_pet.ui.pet_window import PetWindow


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offscreen", action="store_true")
    return parser.parse_args()


def _click(window: PetWindow, position: QPointF) -> None:
    global_position = QPointF(window.mapToGlobal(position.toPoint()))
    window.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            position,
            global_position,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    window.mouseReleaseEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            position,
            global_position,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def _visible_point(window: PetWindow) -> QPointF:
    for y in range(0, window.height(), 3):
        for x in range(0, window.width(), 3):
            point = QPointF(x, y)
            if is_character_pixel(point, window.size(), window._source_image):
                return point
    raise RuntimeError("No visible character pixel was found for the click smoke test.")


def main() -> int:
    _parse_args()
    application = create_application(["click-dialogue-smoke"])
    with tempfile.TemporaryDirectory(prefix="desktop-pet-dialogue-") as temporary:
        dialogue_path = Path(temporary) / "dialogue.txt"
        dialogue_path.write_text("第一句临时对白\n第二句临时对白\n第三句临时对白\n", encoding="utf-8")
        repository = DialogueRepository(dialogue_path)
        dialogues = repository.load()
        selector = DialogueSelector(dialogues, seed=20260806)
        window = PetWindow()
        bubble = DialogueBubble(always_on_top=True)
        enabled = True
        controller = DialogueController(repository, selector, bubble, window, lambda: enabled)
        window.interaction_controller.character_clicked.connect(controller.show_random_dialogue)
        window.move(180, 180)
        window.show()
        application.processEvents()

        transparent = QPointF(0, 0)
        assert not is_character_pixel(transparent, window.size(), window._source_image)
        _click(window, transparent)
        application.processEvents()
        assert not bubble.isVisible()

        visible = _visible_point(window)
        _click(window, visible)
        application.processEvents()
        assert bubble.isVisible()
        assert bubble.current_text in dialogues
        first_text = bubble.current_text
        first_bubble_identity = id(bubble)

        _click(window, visible)
        application.processEvents()
        assert id(bubble) == first_bubble_identity
        assert bubble.current_text in dialogues
        assert bubble.current_text != first_text
        assert bubble.hide_timer.isActive()
        assert len(bubble.findChildren(QTimer)) == 1

        first_position = bubble.pos()
        window.move(window.pos() + QPoint(45, 30))
        application.processEvents()
        assert bubble.pos() != first_position

        for size in PetSize:
            window.set_pet_size(size)
            application.processEvents()
            screen = application.screenAt(bubble.frameGeometry().center())
            assert screen is not None
            safe = screen.availableGeometry().adjusted(12, 12, -12, -12)
            assert safe.contains(bubble.frameGeometry())

        window.hide()
        application.processEvents()
        assert not bubble.isVisible()
        assert not bubble.hide_timer.isActive()
        assert repository.read_count == 1
        assert selector.selection_count == 2
        assert len(window.findChildren(QTimer)) == 1

        controller.shutdown()
        window.close()
        application.processEvents()
        assert not bubble.isVisible()
        assert not bubble.hide_timer.isActive()

        print(
            json.dumps(
                {
                    "status": "passed",
                    "dialogue_read_count": repository.read_count,
                    "dialogue_encoding": repository.encoding,
                    "selection_count": selector.selection_count,
                    "selector_seed": selector.seed,
                    "bubble_instances": 1,
                    "high_frequency_timers": 1,
                    "low_frequency_single_shot_timers": 1,
                    "three_sizes": [list(size.value) for size in PetSize],
                    "residual_visible_bubbles": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
