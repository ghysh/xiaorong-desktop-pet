"""Create the Stage 6 pet window briefly for manual or offscreen smoke verification."""

from __future__ import annotations

import argparse
import os
import sys


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the optional offscreen switch before importing Qt application code."""
    parser = argparse.ArgumentParser(description="Smoke-test the static transparent pet window.")
    parser.add_argument("--offscreen", action="store_true", help="Use Qt's offscreen platform for automation.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Show a verified window for 1.5 seconds and return the Qt exit code."""
    arguments = parse_arguments(argv)
    if arguments.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QGuiApplication

    from desktop_pet.app import create_application, create_pet_window, position_pet_window
    from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256

    application = create_application([sys.argv[0]])
    window = create_pet_window()
    position_pet_window(window)
    screen = window.screen() or QGuiApplication.primaryScreen()
    screen_name = screen.name() if screen is not None and screen.name() else "<unnamed>"

    print(f"Asset path: {window.asset_path}")
    print(f"Asset SHA-256: {EXPECTED_RUNTIME_ASSET_SHA256}")
    print(f"Window size: {window.width()}x{window.height()}")
    print(f"Window position: {window.pos().x()},{window.pos().y()}")
    print(f"Screen: {screen_name}")
    print(f"Window flags: {int(window.windowFlags())}")
    print(f"Translucent background: {window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)}")

    window.show()
    QTimer.singleShot(1500, application.quit)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
