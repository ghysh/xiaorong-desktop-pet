"""System-tray capability smoke test with a valid environment skip path."""

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

    from desktop_pet.app import DesktopPetApplicationController, create_application

    application = create_application(["smoke-test-tray"])
    with tempfile.TemporaryDirectory(prefix="desktop-pet-tray-") as directory:
        controller = DesktopPetApplicationController(application, config_directory=Path(directory))
        controller.start()
        registry = controller.action_registry
        assert len(registry.all_actions) == 9
        assert registry.size_action_group.isExclusive()
        if controller.tray_controller.available:
            assert controller.tray_controller.tray_icon is not None
            assert controller.tray_controller.tray_icon.isVisible()
            print("System tray smoke test passed on this platform.")
        else:
            assert not registry.show_hide_action.isEnabled()
            print("System tray environment skip: tray unavailable; shared actions and fallback passed.")
        controller.shutdown()
        controller.pet_window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
