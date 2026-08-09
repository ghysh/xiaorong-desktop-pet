"""Offscreen Stage 9 settings and persistence smoke test."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offscreen", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import QPoint, QRect, QSize

    from desktop_pet.app import create_application
    from desktop_pet.settings.model import PetSize, UserSettings
    from desktop_pet.settings.repository import SettingsRepository
    from desktop_pet.settings.service import SettingsService, resolve_window_position
    from desktop_pet.ui.settings_dialog import SettingsDialog

    create_application(["smoke-test-settings"])
    with tempfile.TemporaryDirectory(prefix="desktop-pet-stage9-") as directory:
        repository = SettingsRepository(Path(directory))
        service = SettingsService(repository)
        assert service.current == UserSettings()
        service.apply(
            UserSettings(
                size=PetSize.LARGE,
                always_on_top=False,
                behavior_enabled=False,
                window_x=-300,
                window_y=40,
                screen_name="left",
            )
        )
        assert repository.load() == service.current

        dialog = SettingsDialog(service)
        dialog.size_combo.setCurrentIndex(dialog.size_combo.findData(PetSize.SMALL.name))
        dialog.apply_changes()
        assert service.current.size is PetSize.SMALL
        dialog.close()

        restored, corrected = resolve_window_position(
            service.current,
            QSize(*PetSize.SMALL.value),
            {"left": QRect(-1280, 0, 1280, 984), "primary": QRect(0, 0, 1920, 1040)},
            QPoint(1600, 650),
        )
        assert restored == QPoint(-300, 40) and not corrected

        repository.file_path.write_text("[appearance]\nsize=broken\nalways_on_top=false\n", encoding="utf-8")
        recovered = repository.load()
        assert recovered.size is PetSize.DEFAULT
        assert not recovered.always_on_top
        assert recovered.animation_enabled

    print("Stage 9 settings smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
