"""PetWindow paints full-canvas overlays with the same transform and cached scaling."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.app import create_application
from desktop_pet.settings.model import PetSize
from desktop_pet.ui.pet_window import PetWindow


def _start_ready_blink(window: PetWindow) -> None:
    animation = window.animation_controller
    animation.action_player.start(window.runtime_action_registry.get("blink_normal"), animation.elapsed_seconds)


def test_overlay_uses_cached_full_window_pixmap_and_never_moves_widget() -> None:
    create_application(["pytest-overlay-render"])
    window = PetWindow()
    before_position = window.pos()
    _start_ready_blink(window)
    assert window.current_overlay_frame is not None
    assert window._current_overlay_pixmap is not None
    assert window._current_overlay_pixmap.size() == window.size()
    assert window.pos() == before_position
    loads = window.action_asset_cache.source_load_count
    window.update()
    window.repaint()
    assert window.action_asset_cache.source_load_count == loads
    window.close()


def test_size_switch_keeps_current_frame_and_reuses_source_qimages() -> None:
    create_application(["pytest-overlay-size"])
    window = PetWindow()
    _start_ready_blink(window)
    frame = window.current_overlay_frame
    loads = window.action_asset_cache.source_load_count
    window.set_pet_size(PetSize.SMALL, keep_feet_global=False)
    assert window.current_overlay_frame == frame
    assert window._current_overlay_pixmap is not None
    assert window._current_overlay_pixmap.size().toTuple() == (240, 360)
    window.set_pet_size(PetSize.LARGE, keep_feet_global=False)
    assert window.current_overlay_frame == frame
    assert window._current_overlay_pixmap is not None
    assert window._current_overlay_pixmap.size().toTuple() == (320, 480)
    assert window.action_asset_cache.source_load_count == loads
    window.close()


def test_source_draw_and_overlay_draw_share_one_saved_painter_transform() -> None:
    source = open("src/desktop_pet/ui/pet_window.py", encoding="utf-8").read()
    paint = source[source.index("def paintEvent"):source.index("def showEvent")]
    assert paint.count("apply_to_painter") == 1
    assert "drawPixmap(0, 0, self._scaled_pixmap)" in paint
    assert "drawPixmap(0, 0, self._current_overlay_pixmap)" in paint
