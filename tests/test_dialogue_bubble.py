"""Offscreen reusable bubble rendering and timer contract tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from desktop_pet.app import create_application
from desktop_pet.config import DialogueBubbleConfig
from desktop_pet.dialogue.repository import DialogueRepository
from desktop_pet.paths import CLICK_DIALOGUE_FILE, DIALOGUE_BUBBLE_FRAME
from desktop_pet.ui.dialogue_bubble import DialogueBubble, TailDirection, split_trailing_emoticon


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
    assert bubble.frame_asset_path == DIALOGUE_BUBBLE_FRAME
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
    rendered = bubble.grab().toImage()
    assert not rendered.isNull()
    assert rendered.hasAlphaChannel()
    assert bubble.frame_cache_size > 0
    bubble.shutdown()


def test_trailing_emoticon_is_never_split_and_prefers_a_new_line() -> None:
    _application()
    bubble = DialogueBubble(DialogueBubbleConfig(maximum_width=250))
    text = "这是专门用于测试颜文字不能被拆开的稍长对白。(づ｡◕‿‿◕｡)づ"
    emoticon = split_trailing_emoticon(text)

    bubble.show_dialogue(text, QRect(400, 350, 180, 380), QRect(0, 0, 1200, 900))

    assert emoticon is not None
    assert "".join(bubble.layout_lines) == text
    assert sum(emoticon[1] in line for line in bubble.layout_lines) == 1
    assert bubble.layout_lines[-1].endswith(emoticon[1])
    bubble.shutdown()


def test_every_current_kaomoji_is_kept_in_one_layout_line() -> None:
    _application()
    bubble = DialogueBubble()
    dialogues = DialogueRepository(CLICK_DIALOGUE_FILE).load()

    for text in dialogues:
        bubble.show_dialogue(text, QRect(400, 350, 180, 380), QRect(0, 0, 1200, 900))
        emoticon = split_trailing_emoticon(text)
        assert "".join(bubble.layout_lines) == text
        assert 1 <= len(bubble.layout_lines) <= 3
        assert bubble.text_block_rect.width() <= bubble.content_rect.width() + 0.01
        if emoticon is not None:
            assert sum(emoticon[1] in line for line in bubble.layout_lines) == 1
    bubble.shutdown()


def test_multiline_text_block_is_horizontally_and_vertically_centered() -> None:
    _application()
    bubble = DialogueBubble(DialogueBubbleConfig(maximum_width=300))
    text = "好啦好啦，不欺负你了，过来让我陪陪你。(づ｡◕‿‿◕｡)づ"

    bubble.show_dialogue(text, QRect(400, 350, 180, 380), QRect(0, 0, 1200, 900))
    content = bubble.content_rect
    block = bubble.text_block_rect

    assert len(bubble.layout_lines) > 1
    assert abs(block.center().x() - content.center().x()) < 0.01
    assert abs(block.center().y() - content.center().y()) < 0.01
    assert block.width() <= content.width() + 0.01
    assert block.height() <= content.height() + 0.01
    bubble.shutdown()


def test_larger_default_font_remains_readable_without_breaking_kaomoji() -> None:
    _application()
    bubble = DialogueBubble()
    text = "想让我陪你就直说嘛，笨蛋。(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)"

    bubble.show_dialogue(text, QRect(400, 350, 180, 380), QRect(0, 0, 1200, 900))

    assert bubble.config.font_point_size == 13.0
    assert len(bubble.layout_lines) in {2, 3}
    assert "".join(bubble.layout_lines) == text
    assert bubble.text_block_rect.width() <= bubble.content_rect.width() + 0.01
    bubble.shutdown()


@pytest.mark.parametrize(
    "pet",
    (
        QRect(0, 300, 180, 380),
        QRect(1100, 300, 180, 380),
    ),
)
def test_dynamic_tail_tip_keeps_horizontal_connection_at_screen_edges(pet: QRect) -> None:
    _application()
    bubble = DialogueBubble()
    screen = QRect(0, 0, 1280, 900)

    bubble.show_dialogue("今天也要乖乖的哦。(｡•̀ᴗ-)✧", pet, screen)
    global_tip = QPointF(bubble.pos()) + bubble.tail_tip

    assert bubble.tail_direction is TailDirection.BOTTOM
    assert global_tip.x() == pytest.approx(pet.left() + pet.width() / 2, abs=0.75)
    assert abs(global_tip.y() - pet.top()) <= bubble.config.pet_gap + 1
    bubble.shutdown()


def test_dynamic_tail_tip_connects_when_bubble_moves_below_or_to_the_side() -> None:
    _application()
    bubble = DialogueBubble()

    top_pet = QRect(550, 0, 180, 380)
    bubble.show_dialogue("紧贴顶部也不会走丢。(｡･ω･｡)", top_pet, QRect(0, 0, 1280, 900))
    below_tip = QPointF(bubble.pos()) + bubble.tail_tip
    assert bubble.tail_direction is TailDirection.TOP
    assert below_tip.x() == pytest.approx(top_pet.left() + top_pet.width() / 2, abs=0.75)
    assert abs(below_tip.y() - (top_pet.top() + top_pet.height())) <= bubble.config.pet_gap + 1

    side_pet = QRect(550, 90, 180, 220)
    bubble.show_dialogue("上下都不够时放到侧边。(｡•̀ᴗ-)✧", side_pet, QRect(0, 0, 1280, 400))
    side_tip = QPointF(bubble.pos()) + bubble.tail_tip
    assert bubble.tail_direction in {TailDirection.LEFT, TailDirection.RIGHT}
    assert side_tip.y() == pytest.approx(side_pet.top() + side_pet.height() / 2, abs=0.75)
    if bubble.tail_direction is TailDirection.LEFT:
        assert abs(side_tip.x() - (side_pet.left() + side_pet.width())) <= bubble.config.pet_gap + 1
    else:
        assert abs(side_tip.x() - side_pet.left()) <= bubble.config.pet_gap + 1
    bubble.shutdown()


@pytest.mark.parametrize("device_pixel_ratio", (1.0, 1.5, 2.0))
@pytest.mark.parametrize(
    "pet",
    (
        QRect(0, 300, 180, 380),
        QRect(550, 300, 180, 380),
        QRect(1100, 300, 180, 380),
    ),
)
def test_unified_outline_has_no_stroke_or_protruding_endpoints_at_tail_root(
    device_pixel_ratio: float,
    pet: QRect,
) -> None:
    application = _application()
    bubble = DialogueBubble()
    bubble.show_dialogue("今天也要乖乖的哦。(｡•̀ᴗ-)✧", pet, QRect(0, 0, 1280, 900))
    application.processEvents()

    physical_width = round(bubble.width() * device_pixel_ratio)
    physical_height = round(bubble.height() * device_pixel_ratio)
    image = QImage(physical_width, physical_height, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(device_pixel_ratio)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        bubble.render(painter, QPoint())
    finally:
        painter.end()

    root_x = round(bubble.tail_tip.x() * device_pixel_ratio)
    root_y = round((bubble.height() - bubble.config.tail_size) * device_pixel_ratio)
    root_color = image.pixelColor(root_x, root_y)
    assert root_color.alpha() >= 245
    assert min(root_color.red(), root_color.green(), root_color.blue()) >= 230
    assert image.pixelColor(0, root_y).alpha() == 0
    assert image.pixelColor(physical_width - 1, root_y).alpha() == 0
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
