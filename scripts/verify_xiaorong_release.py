"""Verify a frozen XiaoRong executable without relying on a Python runtime at launch."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from desktop_pet.paths import DROWSY_SLEEP_MANIFEST
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256
from desktop_pet.version import WINDOWS_FILE_VERSION, __version__

PRODUCT_NAME = "小融"
EXPECTED_SIZES = [[240, 360], [280, 420], [320, 480]]
_DROWSY_PAYLOAD = json.loads(DROWSY_SLEEP_MANIFEST.read_text(encoding="utf-8"))
EXPECTED_DROWSY_FRAME_COUNT = len(_DROWSY_PAYLOAD["frames"])
EXPECTED_DROWSY_UNIQUE_ASSET_COUNT = len(
    {frame["asset_path"] for frame in _DROWSY_PAYLOAD["frames"]}
)
DEVELOPMENT_PATH_NEEDLES = (
    r"D:\DesktopPet",
    r"D:\anaconda3",
    r"C:\Users\11064",
)


class VSFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", wintypes.DWORD),
        ("structure_version", wintypes.DWORD),
        ("file_version_ms", wintypes.DWORD),
        ("file_version_ls", wintypes.DWORD),
        ("product_version_ms", wintypes.DWORD),
        ("product_version_ls", wintypes.DWORD),
        ("file_flags_mask", wintypes.DWORD),
        ("file_flags", wintypes.DWORD),
        ("file_os", wintypes.DWORD),
        ("file_type", wintypes.DWORD),
        ("file_subtype", wintypes.DWORD),
        ("file_date_ms", wintypes.DWORD),
        ("file_date_ls", wintypes.DWORD),
    ]


class SHFileInfo(ctypes.Structure):
    _fields_ = [
        ("icon", wintypes.HICON),
        ("icon_index", ctypes.c_int),
        ("attributes", wintypes.DWORD),
        ("display_name", wintypes.WCHAR * 260),
        ("type_name", wintypes.WCHAR * 80),
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_pe_metadata(path: Path) -> dict[str, int]:
    """Read architecture and subsystem directly from the PE headers."""
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError(f"Not a PE executable: {path}")
        stream.seek(0x3C)
        pe_offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError(f"Invalid PE signature: {path}")
        machine = struct.unpack("<H", stream.read(2))[0]
        stream.seek(pe_offset + 24)
        optional_magic = struct.unpack("<H", stream.read(2))[0]
        stream.seek(pe_offset + 24 + 68)
        subsystem = struct.unpack("<H", stream.read(2))[0]
    return {"machine": machine, "optional_magic": optional_magic, "subsystem": subsystem}


def _version_tuple(ms: int, ls: int) -> tuple[int, int, int, int]:
    return (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)


def read_windows_version_info(path: Path) -> dict[str, object]:
    """Read VERSIONINFO through the Windows API, including Unicode product strings."""
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.UINT),
    ]
    version.VerQueryValueW.restype = wintypes.BOOL
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise OSError(ctypes.get_last_error(), f"No Windows version resource: {path}")
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        raise OSError(ctypes.get_last_error(), f"Cannot read Windows version resource: {path}")

    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise OSError(ctypes.get_last_error(), "Cannot query fixed version information")
    fixed = ctypes.cast(pointer, ctypes.POINTER(VSFixedFileInfo)).contents

    language, codepage = 0x0804, 0x04B0
    translation_pointer = ctypes.c_void_p()
    translation_length = wintypes.UINT()
    if version.VerQueryValueW(
        buffer,
        "\\VarFileInfo\\Translation",
        ctypes.byref(translation_pointer),
        ctypes.byref(translation_length),
    ) and translation_length.value >= 4:
        words = ctypes.cast(translation_pointer, ctypes.POINTER(wintypes.WORD))
        language, codepage = int(words[0]), int(words[1])

    strings: dict[str, str] = {}
    for key in ("FileDescription", "FileVersion", "InternalName", "OriginalFilename", "ProductName", "ProductVersion"):
        value_pointer = ctypes.c_void_p()
        value_length = wintypes.UINT()
        query = f"\\StringFileInfo\\{language:04X}{codepage:04X}\\{key}"
        if version.VerQueryValueW(buffer, query, ctypes.byref(value_pointer), ctypes.byref(value_length)):
            strings[key] = ctypes.wstring_at(value_pointer, max(0, value_length.value - 1))
    return {
        "file_version": list(_version_tuple(fixed.file_version_ms, fixed.file_version_ls)),
        "product_version": list(_version_tuple(fixed.product_version_ms, fixed.product_version_ls)),
        "strings": strings,
    }


def has_associated_icon(path: Path) -> bool:
    """Ask the Windows shell to extract the icon attached to the executable."""
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32.SHGetFileInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(SHFileInfo),
        wintypes.UINT,
        wintypes.UINT,
    ]
    shell32.SHGetFileInfoW.restype = ctypes.c_size_t
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.DestroyIcon.restype = wintypes.BOOL
    info = SHFileInfo()
    result = shell32.SHGetFileInfoW(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), 0x00000100)
    if not result or not info.icon:
        return False
    user32.DestroyIcon(info.icon)
    return True


def visible_windows_with_title(title: str) -> set[int]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    handles: set[int] = set()
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(handle: int, _parameter: int) -> bool:
        if not user32.IsWindowVisible(handle):
            return True
        length = user32.GetWindowTextLengthW(handle)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, buffer, length + 1)
        if buffer.value == title:
            handles.add(int(handle))
        return True

    if not user32.EnumWindows(callback, 0):
        raise OSError(ctypes.get_last_error(), "EnumWindows failed")
    return handles


def development_path_hits(path: Path) -> list[str]:
    payload = path.read_bytes()
    hits: list[str] = []
    for value in DEVELOPMENT_PATH_NEEDLES:
        if value.encode("utf-8") in payload or value.encode("utf-16-le") in payload:
            hits.append(value)
    return hits


def sanitized_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for variable in tuple(environment):
        if variable.startswith(("CONDA_", "PYTHON")) or variable == "VIRTUAL_ENV":
            environment.pop(variable, None)
    return environment


def run_frozen_smoke(
    executable: Path,
    working_directory: Path,
    *,
    label: str,
    quit_after_ms: int = 3000,
    enable_tray: bool = False,
) -> dict[str, object]:
    """Launch the EXE directly, observe its real window, and wait for a clean exit."""
    executable = executable.resolve()
    working_directory = working_directory.resolve()
    working_directory.mkdir(parents=True, exist_ok=True)
    baseline_handles = visible_windows_with_title(PRODUCT_NAME)
    with tempfile.TemporaryDirectory(prefix=f"xiaorong_{label}_") as temporary:
        temporary_root = Path(temporary)
        result_path = temporary_root / "smoke_result.json"
        config_dir = temporary_root / "config"
        started_at = time.perf_counter()
        command = [
            str(executable),
            "--release-smoke-test",
            "--quit-after-ms",
            str(quit_after_ms),
            "--config-dir",
            str(config_dir),
        ]
        if not enable_tray:
            command.append("--no-tray")
        command.extend(("--smoke-result", str(result_path)))
        process = subprocess.Popen(
            command,
            cwd=working_directory,
            env=sanitized_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        visible_after_seconds: float | None = None
        observed_handles: set[int] = set()
        deadline = time.perf_counter() + 25
        while time.perf_counter() < deadline and process.poll() is None:
            observed_handles = visible_windows_with_title(PRODUCT_NAME) - baseline_handles
            if observed_handles:
                visible_after_seconds = time.perf_counter() - started_at
                break
            time.sleep(0.05)
        try:
            return_code = process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            raise RuntimeError(f"Frozen smoke test timed out: {label}") from None
        elapsed = time.perf_counter() - started_at
        if not result_path.is_file():
            raise RuntimeError(f"Frozen smoke test did not write a result: {label}; exit={return_code}")
        snapshot = json.loads(result_path.read_text(encoding="utf-8"))
        time.sleep(0.4)
        residual_handles = visible_windows_with_title(PRODUCT_NAME) - baseline_handles
        return {
            "label": label,
            "return_code": return_code,
            "visible_window_observed": bool(observed_handles),
            "visible_after_seconds": None if visible_after_seconds is None else round(visible_after_seconds, 3),
            "launch_and_exit_seconds": round(elapsed, 3),
            "residual_window_handles": sorted(residual_handles),
            "snapshot": snapshot,
            "config_isolated": Path(str(snapshot.get("settings_path", ""))).is_relative_to(config_dir),
        }


def verify_executable(
    executable: Path,
    *,
    kind: str,
    label: str,
    expected_name: str | None = None,
    require_tray: bool = False,
) -> dict[str, object]:
    executable = executable.resolve()
    if kind not in {"onedir", "onefile"}:
        raise ValueError(f"Unsupported frozen layout: {kind}")
    if not executable.is_file():
        raise FileNotFoundError(f"Frozen executable not found: {executable}")

    pe = read_pe_metadata(executable)
    version_info = read_windows_version_info(executable)
    strings = version_info["strings"]
    assert isinstance(strings, dict)
    runtime_asset = executable.parent / "_internal" / "assets" / "fullbody" / "final" / "fullbody_runtime_master.png"
    dialogue = executable.parent / "_internal" / "assets" / "actions" / "click_reply" / "dialogue.txt"
    bubble_frame = (
        executable.parent
        / "_internal"
        / "assets"
        / "actions"
        / "click_reply"
        / "dialogue_bubble_frame.png"
    )
    qwindows = list(executable.parent.rglob("qwindows.dll")) if kind == "onedir" else []

    with tempfile.TemporaryDirectory(prefix="xiaorong_clean_cwd_") as clean_working_directory:
        smoke = run_frozen_smoke(
            executable,
            Path(clean_working_directory),
            label=label,
            enable_tray=require_tray,
        )
    snapshot = smoke["snapshot"]
    assert isinstance(snapshot, dict)
    checks = {
        "executable_exists": executable.is_file(),
        "executable_filename": expected_name is None or executable.name == expected_name,
        "win64_machine": pe["machine"] == 0x8664 and pe["optional_magic"] == 0x20B,
        "gui_subsystem": pe["subsystem"] == 2,
        "windows_file_version": version_info["file_version"] == list(WINDOWS_FILE_VERSION),
        "windows_product_version": version_info["product_version"] == list(WINDOWS_FILE_VERSION),
        "product_name": strings.get("ProductName") == PRODUCT_NAME,
        "file_description": strings.get("FileDescription") == "小融桌宠",
        "original_filename": strings.get("OriginalFilename") == "小融.exe",
        "associated_icon": has_associated_icon(executable),
        "no_development_paths": not development_path_hits(executable),
        "window_title_observed": smoke["visible_window_observed"] is True,
        "clean_exit": smoke["return_code"] == 0,
        "no_residual_window": smoke["residual_window_handles"] == [],
        "isolated_config": smoke["config_isolated"] is True,
        "frozen_mode": snapshot.get("frozen") is True,
        "release_version": snapshot.get("version") == __version__,
        "application_name": snapshot.get("application_name") == PRODUCT_NAME,
        "application_display_name": snapshot.get("application_display_name") == PRODUCT_NAME,
        "application_version": snapshot.get("application_version") == __version__,
        "application_icon_loaded": snapshot.get("application_icon_available") is True,
        "single_pet_window": snapshot.get("window_count") == 1,
        "translucent_window": snapshot.get("translucent_background") is True,
        "always_on_top": snapshot.get("always_on_top") is True,
        "alpha_hit_region": snapshot.get("alpha_hit_region_nonempty") is True,
        "sole_high_frequency_timer": snapshot.get("high_frequency_timer_count") == 1,
        "runtime_asset_hash": snapshot.get("runtime_asset_sha256") == EXPECTED_RUNTIME_ASSET_SHA256,
        "runtime_actions_minimal": snapshot.get("runtime_action_ids")
        == ["blink_normal", "drowsy_sleep_cycle"],
        "dialogue_available": snapshot.get("dialogue_available") is True,
        "click_dialogue_displayed": snapshot.get("click_dialogue_displayed") is True,
        "dialogue_bubble_visible": snapshot.get("dialogue_bubble_visible") is True,
        "dialogue_text_nonempty": snapshot.get("dialogue_text_nonempty") is True,
        "drowsy_menu_actions": snapshot.get("drowsy_menu_actions") == ["开", "关", "演示"],
        "drowsy_setting_round_trip": snapshot.get("drowsy_disabled_persisted") is True
        and snapshot.get("drowsy_enabled_persisted") is True,
        "drowsy_demo_started": snapshot.get("drowsy_demo_started") is True,
        "drowsy_frame_count": snapshot.get("drowsy_frame_count") == EXPECTED_DROWSY_FRAME_COUNT,
        "drowsy_unique_assets": snapshot.get("drowsy_unique_asset_count")
        == EXPECTED_DROWSY_UNIQUE_ASSET_COUNT,
        "all_drowsy_frames_cached": snapshot.get("all_drowsy_frames_cached") is True,
        "drowsy_overlay_loaded": snapshot.get("drowsy_overlay_frame_loaded") is True,
        "sleep_bubble_rendered_and_cleared": snapshot.get("sleep_bubble_visible") is True
        and snapshot.get("sleep_bubble_cleared") is True,
        "three_sizes_work": snapshot.get("size_switch_results") == EXPECTED_SIZES,
        "position_saved": snapshot.get("position_saved") is True,
        "settings_created": snapshot.get("settings_file_created") is True,
        "normal_terminal_state": snapshot.get("terminal_state") == "STOPPED",
        "system_tray": snapshot.get("tray_available") is True if require_tray else True,
    }
    if kind == "onedir":
        checks.update(
            qt_platform_plugin_present=bool(qwindows),
            bundled_runtime_asset=runtime_asset.is_file()
            and sha256_file(runtime_asset) == EXPECTED_RUNTIME_ASSET_SHA256,
            bundled_dialogue=dialogue.is_file() and dialogue.stat().st_size > 0,
            bundled_dialogue_bubble_frame=bubble_frame.is_file() and bubble_frame.stat().st_size > 0,
        )
    report = {
        "passed": all(checks.values()),
        "kind": kind,
        "label": label,
        "executable": str(executable),
        "executable_size": executable.stat().st_size,
        "executable_sha256": sha256_file(executable),
        "pe": pe,
        "version_info": version_info,
        "development_path_hits": development_path_hits(executable),
        "tray_required": require_tray,
        "checks": checks,
        "smoke": smoke,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True, choices=("onedir", "onefile"))
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--label", default="manual")
    parser.add_argument("--expected-name")
    parser.add_argument("--require-tray", action="store_true")
    parser.add_argument("--report", required=True, type=Path)
    namespace = parser.parse_args(argv)
    report = verify_executable(
        namespace.executable,
        kind=namespace.kind,
        label=namespace.label,
        expected_name=namespace.expected_name,
        require_tray=namespace.require_tray,
    )
    namespace.report.parent.mkdir(parents=True, exist_ok=True)
    namespace.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen {namespace.kind} verification: {'passed' if report['passed'] else 'failed'}")
    print(f"Report: {namespace.report.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
