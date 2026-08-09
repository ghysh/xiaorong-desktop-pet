"""Offscreen reusable bubble rendering and timer contract tests."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtWidgets import QApplication

from desktop_pet.app import create_application
from desktop_pet.config import DialogueBubbleConfig
from desktop_pet.ui.dialogue_bubble import DialogueBubble


def _application() -> QApplication:
    return create_application(["pytest-dialogue-bubble"])


def test_bubble_window_is_translucent_tool_focus_free_and_mouse_transparent() -> None:
    _application()
    bubble = DialogueBubble()
    flags = bubble.windowFlags()

    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert bubble.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert bubble.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert bubble.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert bubble.focusPolicy() == Qt.FocusPolicy.NoFocus
    bubble.shutdown()


def test_short_and_long_chinese_layout_stays_bounded_and_wraps() -> None:
    application = _application()
    bubble = DialogueBubble()
    pet = QRect(400, 350, 180, 380)
    screen = QRect(0, 0, 1200, 900)

    bubble.show_dialogue("你好呀！", pet, screen)
    short_size = bubble.size()
    bubble.show_dialogue("这是一段用于验证中文在没有空格时仍然可以自然换行的较长对白。" * 6, pet, screen)
    application.processEvents()

    assert bubble.width() <= bubble.config.maximum_width
    assert bubble.height() <= bubble.config.maximum_height
    assert bubble.height() > short_size.height()
    assert bubble.layout_count == 2
    assert not bubble.grab().toImage().isNull()
    bubble.shutdown()


def test_one_instance_and_one_single_shot_timer_are_reused() -> None:
    application = _application()
    config = DialogueBubbleConfig(display_duration_ms=4500)
    bubble = DialogueBubble(config)
    identity = id(bubble)
    pet = QRect(400, 350, 180, 380)
    screen = QRect(0, 0, 1200, 900)

    bubble.show_dialogue("第一句", pet, screen)
    first_remaining = bubble.hide_timer.remainingTime()
    bubble.show_dialogue("第二句", pet, screen)
    application.processEvents()

    assert id(bubble) == identity
    assert bubble.current_text == "第二句"
    assert bubble.display_count == 2
    assert len(bubble.findChildren(QTimer)) == 1
    assert bubble.hide_timer.isSingleShot()
    assert bubble.hide_timer.isActive()
    assert bubble.hide_timer.remainingTime() >= first_remaining - 100
    bubble.shutdown()
    assert not bubble.hide_timer.isActive()


def test_topmost_flag_changes_in_place_and_keeps_visible_text() -> None:
    application = _application()
    bubble = DialogueBubble()
    bubble.show_dialogue("保持这一句", QRect(400, 350, 180, 380), QRect(0, 0, 1200, 900))
    identity = id(bubble)
    application.processEvents()

    bubble.set_always_on_top(False)
    application.processEvents()

    assert id(bubble) == identity
    assert bubble.current_text == "保持这一句"
    assert bubble.isVisible()
    assert not bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert bubble.hide_timer.isActive()
    bubble.shutdown()
