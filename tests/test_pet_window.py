"""Offscreen regression tests for the Stage 7 transparent full-body pet window."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from desktop_pet.app import create_application
from desktop_pet.config import WINDOW_TITLE, PetWindowConfig
from desktop_pet.paths import ANIMATIONS_DIR, FULLBODY_RUNTIME_MASTER, PROJECT_ROOT
from desktop_pet.ui.pet_window import (
    EXPECTED_RUNTIME_ASSET_SHA256,
    PetAssetError,
    PetWindow,
    load_runtime_asset,
    runtime_asset_sha256,
)


@pytest.fixture(scope="module")
def application() -> QApplication:
    """Create one offscreen QApplication for the widget checks."""
    return create_application(["pytest-pet-window"])


def test_runtime_asset_is_the_approved_fullbody_master_and_keeps_its_hash() -> None:
    assert FULLBODY_RUNTIME_MASTER.is_absolute()
    assert FULLBODY_RUNTIME_MASTER == PROJECT_ROOT / "assets" / "fullbody" / "final" / "fullbody_runtime_master.png"
    assert runtime_asset_sha256(FULLBODY_RUNTIME_MASTER) == EXPECTED_RUNTIME_ASSET_SHA256
    assert "character_runtime_master" not in str(FULLBODY_RUNTIME_MASTER)


def test_runtime_asset_loads_as_valid_qimage_with_alpha(application: QApplication) -> None:
    image = load_runtime_asset()

    assert application is not None
    assert image.size().toTuple() == (1024, 1536)
    assert image.hasAlphaChannel()
    assert not image.isNull()


def test_missing_runtime_asset_fails_clearly_without_fallback() -> None:
    missing_path = PROJECT_ROOT / "assets" / "fullbody" / "final" / "missing_runtime_master.png"

    with pytest.raises(PetAssetError, match="missing"):
        load_runtime_asset(missing_path)


def test_pet_window_keeps_the_approved_transparent_window_contract(application: QApplication) -> None:
    window = PetWindow()
    flags = window.windowFlags()

    assert window.windowTitle() == WINDOW_TITLE
    assert window.size().toTuple() == (280, 420)
    assert window.minimumSize() == window.maximumSize()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert not window._source_pixmap.isNull()
    assert window._scaled_pixmap.size().toTuple() == (280, 420)
    assert window._source_pixmap.width() * 3 == window._source_pixmap.height() * 2
    assert window.animation_controller.target_fps == 30
    assert window.effective_drag_tilt_max_degrees == 4.0

    window.close()


def test_pet_window_paints_a_transparent_margin_without_background_fill(application: QApplication) -> None:
    window = PetWindow()
    window.show()
    application.processEvents()
    captured = window.grab().toImage()

    assert captured.pixelColor(0, 0).alpha() == 0
    assert captured.pixelColor(140, 210).alpha() > 0

    window.close()


def test_left_mouse_drag_moves_widget_and_right_button_does_not_start_drag(
    application: QApplication,
) -> None:
    window = PetWindow()
    window.move(100, 100)
    window.show()
    application.processEvents()
    initial_position = window.pos()
    local_start = QPointF(20, 20)
    global_start = QPointF(initial_position.x() + 20, initial_position.y() + 20)
    local_end = QPointF(70, 80)
    global_end = QPointF(initial_position.x() + 70, initial_position.y() + 80)

    window.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            local_start,
            global_start,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    window.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            local_end,
            global_end,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    window.mouseReleaseEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            local_end,
            global_end,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert window.pos() == initial_position + QPoint(50, 60)
    assert window._drag_offset is None

    window.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(window.x() + 10, window.y() + 10),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert window._drag_offset is None
    window.close()


def test_context_menu_contains_only_one_exit_action(application: QApplication) -> None:
    window = PetWindow()
    menu = window.create_context_menu()

    assert application is not None
    assert len(menu.actions()) == 1

    menu.deleteLater()
    window.close()


def test_invalid_window_configurations_fail_early() -> None:
    with pytest.raises(ValueError, match="positive"):
        PetWindowConfig(width=0)
    with pytest.raises(ValueError, match="2:3"):
        PetWindowConfig(width=280, height=400)
    with pytest.raises(ValueError, match="negative"):
        PetWindowConfig(startup_margin=-1)


def test_stage_eight_runtime_keeps_animation_paint_only_and_random_is_scheduler_local() -> None:
    runtime_sources = list((PROJECT_ROOT / "src" / "desktop_pet").rglob("*.py"))
    animation_sources = list((PROJECT_ROOT / "src" / "desktop_pet" / "animation").rglob("*.py"))
    controller_source = Path(__file__).parents[1] / "src" / "desktop_pet" / "animation" / "controller.py"
    scheduler_source = Path(__file__).parents[1] / "src" / "desktop_pet" / "behavior" / "scheduler.py"

    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    assert all("import cv2" not in path.read_text(encoding="utf-8") for path in runtime_sources)
    assert all("import random" not in path.read_text(encoding="utf-8") for path in animation_sources)
    assert "random.Random" in scheduler_source.read_text(encoding="utf-8")
    assert "random.seed" not in scheduler_source.read_text(encoding="utf-8")
    assert controller_source.read_text(encoding="utf-8").count("QTimer(") == 1
