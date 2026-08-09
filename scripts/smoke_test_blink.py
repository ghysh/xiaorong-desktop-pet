"""Accelerated deterministic offscreen smoke test for blink integration."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys

if "--offscreen" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer

from desktop_pet.app import create_application
from desktop_pet.behavior.state import PetState
from desktop_pet.blink.scheduler import BlinkScheduler
from desktop_pet.config import BlinkConfig, PetWindowConfig
from desktop_pet.paths import FULLBODY_RUNTIME_MASTER
from desktop_pet.settings.model import PetSize
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256, PetWindow


def master_hash() -> str:
    return hashlib.sha256(FULLBODY_RUNTIME_MASTER.read_bytes()).hexdigest().upper()


def working_set_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    )
    psapi.GetProcessMemoryInfo.restype = ctypes.c_bool
    process = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        return None
    return int(counters.WorkingSetSize)


def simulate_ten_minutes(seed: int) -> int:
    scheduler = BlinkScheduler(BlinkConfig(seed=seed))
    scheduler.start(0.0)
    count = 0
    while scheduler.next_due_seconds is not None and scheduler.next_due_seconds < 600.0:
        due = scheduler.next_due_seconds
        assert scheduler.is_due(due)
        scheduler.mark_started()
        scheduler.mark_finished(due + 0.195)
        count += 1
    return count


def _submit_due_blink(window: PetWindow, elapsed_seconds: float) -> float:
    blink = window.animation_controller.blink_controller
    request = blink.update(elapsed_seconds, PetState.IDLE_CALM)
    assert request is not None
    assert window.animation_controller._process_action_request(request)
    assert window.current_overlay_frame is not None
    return elapsed_seconds


def _finish_blink(window: PetWindow, started_at: float) -> None:
    window.animation_controller.action_player.update(started_at + 0.195)
    assert window.current_overlay_frame is None


def run_smoke() -> dict[str, object]:
    before_hash = master_hash()
    assert before_hash == EXPECTED_RUNTIME_ASSET_SHA256
    application = create_application(["stage10b-blink-smoke"])
    memory_before_window = working_set_bytes()
    config = PetWindowConfig(
        blink=BlinkConfig(
            minimum_interval_seconds=0.05,
            maximum_interval_seconds=0.06,
            double_blink_probability=1.0,
            seed=20260806,
        )
    )
    window = PetWindow(config)
    memory_after_window = working_set_bytes()
    initial_position = window.pos()
    behavior = window.behavior_controller
    behavior.start(0.0)
    behavior.update(1.0)
    assert behavior.current_state is PetState.IDLE_CALM
    blink = window.animation_controller.blink_controller
    assert blink.update(1.0, PetState.IDLE_CALM) is None
    due = blink.scheduler.next_due_seconds
    assert due is not None and due >= 3.0

    first_started = _submit_due_blink(window, due)
    _finish_blink(window, first_started)
    follow_up_due = blink.scheduler.next_due_seconds
    assert follow_up_due is not None and 0.08 <= follow_up_due - (first_started + 0.195) <= 0.16
    second_started = _submit_due_blink(window, follow_up_due)
    _finish_blink(window, second_started)

    third_due = blink.scheduler.next_due_seconds
    assert third_due is not None
    _submit_due_blink(window, third_due)
    window.animation_controller._interrupt_current_action(third_due + 0.02, "click_reaction")
    assert window.current_overlay_frame is None

    fourth_due = blink.scheduler.next_due_seconds
    assert fourth_due is not None
    _submit_due_blink(window, fourth_due)
    window.animation_controller._interrupt_current_action(fourth_due + 0.02, "dragging")
    assert window.current_overlay_frame is None

    fifth_due = blink.scheduler.next_due_seconds
    assert fifth_due is not None
    _submit_due_blink(window, fifth_due)
    current_frame = window.current_overlay_frame
    window.set_pet_size(PetSize.SMALL, keep_feet_global=False)
    assert window.current_overlay_frame == current_frame
    window.set_pet_size(PetSize.LARGE, keep_feet_global=False)
    assert window.current_overlay_frame == current_frame
    window.animation_controller._interrupt_current_action(fifth_due + 0.03, "pause")
    blink.pause(fifth_due + 0.03)
    resumed_due_before = blink.scheduler.random_draw_count
    blink.update(0.0, PetState.PAUSED)
    assert blink.update(0.1, PetState.IDLE_CALM) is None
    assert blink.scheduler.random_draw_count == resumed_due_before

    clip = window.runtime_action_registry.get("blink_normal")
    memory_before_repeated_playback = working_set_bytes()
    scale_count_after_first_playback = 0
    for index in range(100):
        started = 1000.0 + index
        window.animation_controller.action_player.start(clip, started)
        for offset in (0.035, 0.070, 0.125, 0.160, 0.195):
            window.animation_controller.action_player.update(started + offset)
        if index == 0:
            scale_count_after_first_playback = window.action_asset_cache.scale_count
    stable_scale_count = window.action_asset_cache.scale_count
    assert stable_scale_count == scale_count_after_first_playback
    memory_after_repeated_playback = working_set_bytes()

    assert window.pos() == initial_position
    assert len(window.findChildren(QTimer)) == 1
    assert not window.findChildren(__import__("PySide6.QtCore", fromlist=["QThread"]).QThread)
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    behavior.stop(100.0)
    window.animation_controller.blink_controller.stop()
    window.close()
    application.processEvents()
    after_hash = master_hash()
    assert after_hash == before_hash
    result = {
        "status": "passed",
        "single_and_double_blinks": 2,
        "click_interrupt": "passed",
        "drag_interrupt": "passed",
        "pause_resume_delay": "passed",
        "size_switch_phase_preserved": "passed",
        "widget_position_unchanged": True,
        "high_frequency_timer_count": 1,
        "worker_thread_count": 0,
        "test_seed": 20260806,
        "simulated_ten_minute_blink_count": simulate_ten_minutes(20260806),
        "overlay_source_memory_estimate_bytes": window.action_asset_cache.source_memory_estimate_bytes,
        "scaled_cache_memory_estimate_bytes": window.action_asset_cache.scaled_memory_estimate_bytes,
        "working_set_before_window_bytes": memory_before_window,
        "working_set_after_window_bytes": memory_after_window,
        "working_set_delta_bytes": (
            None
            if memory_before_window is None or memory_after_window is None
            else memory_after_window - memory_before_window
        ),
        "repeated_playback_count": 100,
        "scale_cache_entry_count_after_repeated_playback": stable_scale_count,
        "scale_cache_grew_after_first_playback": False,
        "working_set_before_repeated_playback_bytes": memory_before_repeated_playback,
        "working_set_after_repeated_playback_bytes": memory_after_repeated_playback,
        "working_set_repeated_playback_delta_bytes": (
            None
            if memory_before_repeated_playback is None or memory_after_repeated_playback is None
            else memory_after_repeated_playback - memory_before_repeated_playback
        ),
        "master_sha256": after_hash,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offscreen", action="store_true")
    parser.parse_args()
    run_smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
