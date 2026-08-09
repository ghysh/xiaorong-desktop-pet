"""Accelerated, non-blocking Stage 8 behavior smoke test."""

from __future__ import annotations

import argparse
import os
import sys

if "--offscreen" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QElapsedTimer, QPoint, QTimer

from desktop_pet.app import create_application
from desktop_pet.behavior.state import AUTOMATIC_STATES, PetState
from desktop_pet.config import BehaviorConfig, PetWindowConfig, StateDurationRange
from desktop_pet.ui.pet_window import PetWindow, runtime_asset_sha256

SMOKE_SEED = 20260805


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test Stage 8 behavior orchestration.")
    parser.add_argument("--offscreen", action="store_true", help="Use Qt's offscreen platform.")
    return parser


def _fast_config() -> PetWindowConfig:
    behavior = BehaviorConfig(
        behavior_seed=SMOKE_SEED,
        starting_duration_seconds=0.15,
        calm_duration=StateDurationRange(0.50, 0.60),
        quiet_duration=StateDurationRange(0.50, 0.60),
        sway_duration=StateDurationRange(0.50, 0.60),
        resting_duration=StateDurationRange(0.50, 0.60),
        profile_transition_duration_seconds=0.10,
    )
    return PetWindowConfig(behavior=behavior)


def main(argv: list[str] | None = None) -> int:
    """Verify scheduling, drag priority, settling, pause/resume, and terminal shutdown."""
    _parser().parse_args(argv)
    application = create_application(["smoke-test-behavior"])
    window = PetWindow(_fast_config())
    transitions = []
    window.behavior_controller.state_changed.connect(transitions.append)
    start_state = window.behavior_controller.current_state
    window.move(127, 113)
    runtime = QElapsedTimer()
    flags = {
        "dragging": False,
        "settling": False,
        "paused": False,
        "timer_stopped_while_hidden": False,
        "resumed": False,
    }
    result = {"exit_code": 1}

    def begin_drag() -> None:
        window.animation_controller.begin_drag(QPoint(100, 100))
        flags["dragging"] = window.behavior_controller.current_state is PetState.DRAGGING

    def update_drag() -> None:
        window.animation_controller.update_drag(QPoint(220, 100))

    def release_drag() -> None:
        window.animation_controller.end_drag()
        flags["settling"] = window.behavior_controller.current_state is PetState.SETTLING

    def hide_window() -> None:
        window.hide()
        application.processEvents()
        flags["paused"] = window.behavior_controller.current_state is PetState.PAUSED
        flags["timer_stopped_while_hidden"] = not window.animation_controller.timer.isActive()

    def show_window() -> None:
        window.show()
        application.processEvents()
        flags["resumed"] = window.behavior_controller.current_state in AUTOMATIC_STATES | {PetState.STARTING}

    def finish() -> None:
        end_position = window.pos()
        timer_count = len(window.findChildren(QTimer))
        automatic_transitions = [
            transition
            for transition in transitions
            if transition.reason.value in {"startup_complete", "scheduled_transition"}
        ]
        state_before_close = window.behavior_controller.current_state
        window.close()
        application.processEvents()
        stopped = window.behavior_controller.current_state is PetState.STOPPED
        sequence = [start_state.name, *(transition.next_state.name for transition in transitions)]
        passed = all(flags.values()) and len(automatic_transitions) >= 4
        passed = passed and timer_count == 1 and end_position == start_position and stopped
        passed = passed and state_before_close in AUTOMATIC_STATES | {PetState.STARTING}
        print(f"actual_seed={window.behavior_controller.actual_seed}")
        print(f"state_sequence={' -> '.join(sequence)}")
        print(
            "state_durations="
            + ", ".join(
                f"{transition.previous_state.name}:{transition.elapsed_seconds:.3f}s"
                for transition in transitions
            )
        )
        print(f"transition_count={len(transitions)}")
        print(f"drag_override={flags['dragging'] and flags['settling']}")
        print(f"pause_resume={flags['paused'] and flags['timer_stopped_while_hidden'] and flags['resumed']}")
        print(f"animation_qtimer_count={timer_count}")
        print(f"window_start_position={start_position}")
        print(f"window_end_position={end_position}")
        print(f"final_state={window.behavior_controller.current_state.name}")
        print(f"runtime_seconds={runtime.elapsed() / 1000.0:.3f}")
        print(f"runtime_asset_sha256={runtime_asset_sha256(window.asset_path)}")
        result["exit_code"] = int(not passed)
        application.quit()

    assert start_state is PetState.STARTING
    window.show()
    application.processEvents()
    start_position = window.pos()
    runtime.start()
    QTimer.singleShot(2450, begin_drag)
    QTimer.singleShot(2550, update_drag)
    QTimer.singleShot(2720, release_drag)
    QTimer.singleShot(3150, hide_window)
    QTimer.singleShot(3380, show_window)
    QTimer.singleShot(4350, finish)
    application.exec()
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
