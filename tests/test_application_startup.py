"""Lifecycle and smoke checks for the Stage 6 transparent pet-window prototype."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from scripts.smoke_test_pet_window import main as smoke_main

from desktop_pet.app import create_application, create_pet_window, position_pet_window, run


def test_application_and_pet_window_can_be_created_offscreen() -> None:
    application = create_application(["pytest-application-startup"])
    window = create_pet_window()
    position_pet_window(window)

    assert isinstance(application, QApplication)
    assert window.isWindow()
    assert window.width() == 280 and window.height() == 420

    window.close()


def test_run_returns_zero_when_the_event_loop_is_explicitly_closed(tmp_path: Path) -> None:
    application = create_application(["pytest-run"])
    QTimer.singleShot(1, application.quit)

    assert run(["--config-dir", str(tmp_path)]) == 0


def test_offscreen_smoke_test_returns_zero() -> None:
    assert smoke_main(["--offscreen"]) == 0
