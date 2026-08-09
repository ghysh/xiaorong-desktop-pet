"""Run a short non-blocking Stage 7 animation smoke test, optionally offscreen."""

from __future__ import annotations

import argparse
import os
import sys

if "--offscreen" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QElapsedTimer, QPoint, QTimer

from desktop_pet.animation.transform import AnimationTransform
from desktop_pet.app import create_application
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_sha256


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test the Stage 7 local transform animation system.")
    parser.add_argument("--offscreen", action="store_true", help="Use Qt's offscreen platform for automated checks.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Exercise idle motion, both drag directions, and eased release without blocking the Qt loop."""
    _parser().parse_args(argv)
    application = create_application(["smoke-test-animation"])
    window = PetWindow()
    window.move(127, 113)
    transforms: list[AnimationTransform] = []
    window.animation_controller.transform_changed.connect(transforms.append)
    elapsed_timer = QElapsedTimer()
    result = {"exit_code": 1, "start_position": None, "end_position": None}

    def begin_right_drag() -> None:
        window.animation_controller.begin_drag(QPoint(100, 100))

    def update_right_drag() -> None:
        window.animation_controller.update_drag(QPoint(220, 100))

    def release_right_drag() -> None:
        window.animation_controller.end_drag()

    def begin_left_drag() -> None:
        window.animation_controller.begin_drag(QPoint(220, 100))

    def update_left_drag() -> None:
        window.animation_controller.update_drag(QPoint(100, 100))

    def release_left_drag() -> None:
        window.animation_controller.end_drag()

    def finish() -> None:
        result["end_position"] = window.pos()
        all_safe = all(window.is_transform_safe(transform) for transform in transforms)
        varied = len({transform.as_tuple() for transform in transforms}) > 8
        returned = not window.animation_controller.is_returning and not window.animation_controller.is_dragging
        unchanged_position = result["start_position"] == result["end_position"]
        elapsed_seconds = elapsed_timer.elapsed() / 1000.0
        scale_x_values = [transform.scale_x for transform in transforms]
        scale_y_values = [transform.scale_y for transform in transforms]
        offset_y_values = [transform.offset_y for transform in transforms]
        rotation_values = [transform.rotation_degrees for transform in transforms]
        print(f"target_fps={window.animation_controller.target_fps}")
        print(f"actual_runtime_seconds={elapsed_seconds:.3f}")
        print(f"transform_updates={len(transforms)}")
        print(f"scale_x_min_max={min(scale_x_values):.6f},{max(scale_x_values):.6f}")
        print(f"scale_y_min_max={min(scale_y_values):.6f},{max(scale_y_values):.6f}")
        print(f"offset_y_min_max={min(offset_y_values):.3f},{max(offset_y_values):.3f}")
        print(f"rotation_min_max={min(rotation_values):.3f},{max(rotation_values):.3f}")
        print(f"window_start_position={result['start_position']}")
        print(f"window_end_position={result['end_position']}")
        print(f"clipping_detected={not all_safe}")
        print(f"runtime_asset_sha256={runtime_asset_sha256(window.asset_path)}")
        print(f"drag_return_complete={returned}")
        print(f"idle_kept_window_position={unchanged_position}")
        result["exit_code"] = int(not (all_safe and varied and returned and unchanged_position))
        window.close()
        application.quit()

    window.show()
    application.processEvents()
    result["start_position"] = window.pos()
    elapsed_timer.start()
    QTimer.singleShot(700, begin_right_drag)
    QTimer.singleShot(780, update_right_drag)
    QTimer.singleShot(950, release_right_drag)
    QTimer.singleShot(1400, begin_left_drag)
    QTimer.singleShot(1480, update_left_drag)
    QTimer.singleShot(1650, release_left_drag)
    QTimer.singleShot(4000, finish)
    application.exec()
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
