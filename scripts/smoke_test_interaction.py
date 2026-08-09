"""Integrated offscreen smoke test for Stage 9 interaction and application settings."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offscreen", action="store_true")
    return parser


def _wait(milliseconds: int) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _visible_window_point(window):
    from PySide6.QtCore import QPointF

    left, top, right, bottom = window.source_alpha_bounds
    source = window._source_image
    for y in range(top, bottom, 4):
        for x in range(left, right, 4):
            if source.pixelColor(x, y).alpha() >= 16:
                return QPointF(
                    (x + 0.5) * window.width() / source.width(),
                    (y + 0.5) * window.height() / source.height(),
                )
    raise AssertionError("No visible character point was found.")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import QPoint, QPointF, Qt

    from desktop_pet.app import DesktopPetApplicationController, create_application
    from desktop_pet.behavior.state import PetState
    from desktop_pet.interaction.hit_test import is_character_pixel
    from desktop_pet.paths import FULLBODY_RUNTIME_MASTER
    from desktop_pet.settings.model import PetSize, UserSettings
    from desktop_pet.settings.repository import SettingsRepository
    from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256, runtime_asset_sha256

    before_hash = runtime_asset_sha256(FULLBODY_RUNTIME_MASTER)
    assert before_hash == EXPECTED_RUNTIME_ASSET_SHA256
    application = create_application(["smoke-test-interaction"])
    with tempfile.TemporaryDirectory(prefix="desktop-pet-interaction-") as directory:
        config_directory = Path(directory)
        controller = DesktopPetApplicationController(application, config_directory=config_directory)
        controller.start()
        window = controller.pet_window
        assert window.size().toTuple() == PetSize.DEFAULT.value
        assert not is_character_pixel(QPointF(0, 0), window.size(), window._source_image)
        visible = _visible_window_point(window)
        assert is_character_pixel(visible, window.size(), window._source_image)

        interaction = controller.interaction_controller
        now = controller.animation_controller.elapsed_seconds
        assert not interaction.try_start_click(
            elapsed_seconds=now,
            button=Qt.MouseButton.LeftButton,
            press_hit=False,
            release_hit=False,
            movement_distance=0,
            drag_threshold=10,
            held_ms=20,
        )
        assert interaction.try_start_click(
            elapsed_seconds=now,
            button=Qt.MouseButton.LeftButton,
            press_hit=True,
            release_hit=True,
            movement_distance=0,
            drag_threshold=10,
            held_ms=20,
        )
        assert controller.behavior_controller.current_state is PetState.CLICK_REACTION
        interaction.update(now + 0.261)
        assert controller.behavior_controller.current_state is not PetState.CLICK_REACTION
        assert not interaction.try_start_click(
            elapsed_seconds=now + 0.262,
            button=Qt.MouseButton.LeftButton,
            press_hit=True,
            release_hit=True,
            movement_distance=10,
            drag_threshold=10,
            held_ms=30,
        )

        for size in (PetSize.SMALL, PetSize.LARGE, PetSize.DEFAULT):
            controller.settings_service.set_size(size)
            assert window.size().toTuple() == size.value
            assert all(window.clipping_checks().values())
        controller.settings_service.set_behavior_enabled(False)
        assert not controller.behavior_controller.behavior_enabled
        controller.settings_service.set_behavior_enabled(True)
        controller.settings_service.set_always_on_top(False)
        assert not bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        controller.settings_service.set_always_on_top(True)

        controller.settings_service.set_animation_enabled(False)
        _wait(300)
        assert not controller.animation_controller.timer.isActive()
        assert controller.animation_controller.current_transform.is_close(
            controller.animation_controller.current_transform.identity()
        )
        controller.settings_service.set_animation_enabled(True)
        assert controller.animation_controller.timer.isActive()

        window.move(QPoint(120, 80))
        controller._save_position(window.pos())
        saved = controller.settings_service.current
        assert saved.window_x == 120 and saved.window_y == 80
        controller.shutdown()
        window.close()

        restored_controller = DesktopPetApplicationController(application, config_directory=config_directory)
        assert restored_controller.settings_service.current.size is PetSize.DEFAULT
        assert restored_controller.pet_window.pos() == QPoint(120, 80)
        restored_controller.shutdown()
        restored_controller.pet_window.close()

        repository = SettingsRepository(config_directory)
        repository.file_path.write_text("[appearance]\nsize=invalid\n", encoding="utf-8")
        assert repository.load() == UserSettings()

    assert runtime_asset_sha256(FULLBODY_RUNTIME_MASTER) == before_hash
    print("Stage 9 interaction smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
