"""Measured long-run stability exercise for the real Stage 10 runtime graph."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import statistics
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--sample-interval", type=float, default=5.0)
    parser.add_argument("--offscreen", action="store_true")
    return parser


class ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _process_metrics() -> dict[str, int | None]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetProcessHandleCount.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    user32.GetGuiResources.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    user32.GetGuiResources.restype = wintypes.DWORD
    process = kernel32.GetCurrentProcess()
    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    handle_count = wintypes.DWORD()
    if not kernel32.GetProcessHandleCount(process, ctypes.byref(handle_count)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {
        "working_set_bytes": int(counters.WorkingSetSize),
        "private_bytes": int(counters.PrivateUsage),
        "handle_count": int(handle_count.value),
        "gdi_objects": int(user32.GetGuiResources(process, 0)),
        "user_objects": int(user32.GetGuiResources(process, 1)),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _trend(values: list[int]) -> dict[str, float | int | bool]:
    if len(values) < 2:
        return {"initial": values[0], "final": values[0], "maximum": values[0], "net_change": 0, "slope": 0.0}
    indices = list(range(len(values)))
    mean_x = statistics.fmean(indices)
    mean_y = statistics.fmean(values)
    denominator = sum((index - mean_x) ** 2 for index in indices)
    slope = sum((index - mean_x) * (value - mean_y) for index, value in zip(indices, values, strict=True))
    slope = slope / denominator if denominator else 0.0
    monotonic_ratio = sum(right >= left for left, right in zip(values, values[1:], strict=False)) / (len(values) - 1)
    return {
        "initial": values[0],
        "final": values[-1],
        "maximum": max(values),
        "minimum": min(values),
        "net_change": values[-1] - values[0],
        "slope_per_sample": slope,
        "nondecreasing_ratio": monotonic_ratio,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.duration <= 0 or args.sample_interval <= 0:
        raise ValueError("Duration and sample interval must be positive.")
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import QEventLoop, QTimer

    from desktop_pet.app import DesktopPetApplicationController, create_application
    from desktop_pet.paths import FULLBODY_RUNTIME_MASTER, PROJECT_ROOT
    from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256

    application = create_application(["long-run-stability"])
    before_hash = _sha256(FULLBODY_RUNTIME_MASTER)
    errors: list[str] = []
    samples: list[dict[str, object]] = []
    wall_started = time.monotonic()
    cpu_started = time.process_time()
    temporary_parent = PROJECT_ROOT / "build" / "temp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="desktop-pet-long-run-", dir=temporary_parent) as directory:
        controller = DesktopPetApplicationController(application, config_directory=Path(directory))
        controller.start()
        initial_writes = controller.settings_repository.save_count
        while True:
            elapsed = time.monotonic() - wall_started
            try:
                metrics = _process_metrics()
            except OSError as error:
                errors.append(str(error))
                metrics = {
                    "working_set_bytes": 0,
                    "private_bytes": 0,
                    "handle_count": 0,
                    "gdi_objects": None,
                    "user_objects": None,
                }
            samples.append(
                {
                    "elapsed_seconds": elapsed,
                    "cpu_seconds": time.process_time() - cpu_started,
                    **metrics,
                    "timer_count": len(controller.pet_window.findChildren(QTimer)),
                    "state_transitions": controller.behavior_controller.total_transition_count,
                    "paint_count": controller.pet_window.paint_count,
                    "settings_writes": controller.settings_repository.save_count,
                    "asset_load_count": controller.pet_window.runtime_asset_load_count,
                    "tray_icon_creation_count": controller.tray_controller.icon_creation_count,
                }
            )
            if elapsed >= args.duration:
                break
            loop = QEventLoop()
            remaining = max(0.0, args.duration - elapsed)
            QTimer.singleShot(round(min(args.sample_interval, remaining) * 1000), loop.quit)
            loop.exec()
        controller.shutdown()
        terminal_state = controller.behavior_controller.current_state.name
        final_writes = controller.settings_repository.save_count
        controller.pet_window.close()

    wall_duration = time.monotonic() - wall_started
    cpu_duration = time.process_time() - cpu_started
    working = [int(sample["working_set_bytes"]) for sample in samples]
    private = [int(sample["private_bytes"]) for sample in samples]
    handles = [int(sample["handle_count"]) for sample in samples]
    working_trend = _trend(working)
    private_trend = _trend(private)
    handle_trend = _trend(handles)
    memory_growth_failure = (
        int(working_trend["net_change"]) > 25 * 1024 * 1024
        and float(working_trend["nondecreasing_ratio"]) > 0.75
    ) or (
        int(private_trend["net_change"]) > 25 * 1024 * 1024
        and float(private_trend["nondecreasing_ratio"]) > 0.75
    )
    handle_growth_failure = int(handle_trend["net_change"]) > 20
    after_hash = _sha256(FULLBODY_RUNTIME_MASTER)
    timer_count = max(int(sample["timer_count"]) for sample in samples)
    background_threads = max(0, threading.active_count() - 1)
    passed = all(
        (
            not errors,
            before_hash == EXPECTED_RUNTIME_ASSET_SHA256 == after_hash,
            not memory_growth_failure,
            not handle_growth_failure,
            timer_count == 1,
            background_threads == 0,
            final_writes - initial_writes <= 1,
            max(int(sample["asset_load_count"]) for sample in samples) == 1,
            max(int(sample["tray_icon_creation_count"]) for sample in samples) <= 1,
            terminal_state == "STOPPED",
        )
    )
    report = {
        "passed": passed,
        "requested_duration_seconds": args.duration,
        "actual_duration_seconds": wall_duration,
        "sample_interval_seconds": args.sample_interval,
        "sample_count": len(samples),
        "cpu_seconds": cpu_duration,
        "average_cpu_percent_one_core": cpu_duration / wall_duration * 100.0,
        "working_set": working_trend,
        "private_memory": private_trend,
        "handles": handle_trend,
        "initial_gdi_objects": samples[0]["gdi_objects"],
        "final_gdi_objects": samples[-1]["gdi_objects"],
        "initial_user_objects": samples[0]["user_objects"],
        "final_user_objects": samples[-1]["user_objects"],
        "high_frequency_timer_count": timer_count,
        "background_thread_count": background_threads,
        "state_transition_count": samples[-1]["state_transitions"],
        "paint_count": samples[-1]["paint_count"],
        "settings_writes_during_run": final_writes - initial_writes,
        "asset_load_count": max(int(sample["asset_load_count"]) for sample in samples),
        "tray_icon_creation_count": max(int(sample["tray_icon_creation_count"]) for sample in samples),
        "terminal_state": terminal_state,
        "asset_sha256_before": before_hash,
        "asset_sha256_after": after_hash,
        "memory_growth_failure": memory_growth_failure,
        "handle_growth_failure": handle_growth_failure,
        "errors": errors,
        "samples": samples,
    }
    reports = PROJECT_ROOT / "build" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    json_path = reports / "long_run_stability.json"
    md_path = reports / "long_run_stability.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    print(f"Long-run stability: {'passed' if passed else 'failed'} ({wall_duration:.1f}s)")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0 if passed else 1


def _markdown_report(report: dict[str, object]) -> str:
    working = report["working_set"]
    private = report["private_memory"]
    handles = report["handles"]
    return (
        "# Long-run stability report\n\n"
        f"- Result: {'PASS' if report['passed'] else 'FAIL'}\n"
        f"- Duration: {report['actual_duration_seconds']:.2f} seconds\n"
        f"- CPU time: {report['cpu_seconds']:.3f} seconds "
        f"({report['average_cpu_percent_one_core']:.2f}% of one core)\n"
        f"- Working set: {working['initial']} -> {working['final']} bytes; max {working['maximum']}\n"
        f"- Private memory: {private['initial']} -> {private['final']} bytes; max {private['maximum']}\n"
        f"- Handles: {handles['initial']} -> {handles['final']}; max {handles['maximum']}\n"
        f"- GDI objects: {report['initial_gdi_objects']} -> {report['final_gdi_objects']}\n"
        f"- USER objects: {report['initial_user_objects']} -> {report['final_user_objects']}\n"
        f"- High-frequency QTimers: {report['high_frequency_timer_count']}\n"
        f"- Background threads: {report['background_thread_count']}\n"
        f"- State transitions: {report['state_transition_count']}\n"
        f"- Paints: {report['paint_count']}\n"
        f"- Settings writes during run/exit: {report['settings_writes_during_run']}\n"
        f"- Asset loads: {report['asset_load_count']}\n"
        f"- Tray icon creations: {report['tray_icon_creation_count']}\n"
        f"- Asset SHA-256 unchanged: {report['asset_sha256_before'] == report['asset_sha256_after']}\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
