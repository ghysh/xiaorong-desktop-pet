"""Verify an unpacked PyInstaller onedir release by launching its EXE directly."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256

REPORT_JSON = PROJECT_ROOT / "build" / "reports" / "frozen_release_verification.json"
REPORT_MD = PROJECT_ROOT / "build" / "reports" / "frozen_release_verification.md"
FORBIDDEN_NAME_FRAGMENTS = (
    "ori_figure",
    "analysis",
    "diagnostic",
    "pytest",
    "ruff",
    "__pycache__",
    "test_",
    "cv2",
    "numpy",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def pe_subsystem(path: Path) -> int:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("DesktopPet.exe is not a PE executable.")
        stream.seek(0x3C)
        pe_offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError("DesktopPet.exe has an invalid PE signature.")
        stream.seek(20, 1)
        optional_header = stream.tell()
        magic = struct.unpack("<H", stream.read(2))[0]
        if magic not in {0x10B, 0x20B}:
            raise ValueError("DesktopPet.exe has an unknown PE optional header.")
        stream.seek(optional_header + 68)
        return struct.unpack("<H", stream.read(2))[0]


def _scan_release(release_dir: Path) -> tuple[list[str], list[str]]:
    forbidden_files: list[str] = []
    development_path_hits: list[str] = []
    needles = (b"D:\\DesktopPet\\desktop_pet", "D:\\DesktopPet\\desktop_pet".encode("utf-16-le"))
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(release_dir).as_posix()
        folded = relative.casefold()
        if path.suffix.casefold() == ".py" or any(fragment in folded for fragment in FORBIDDEN_NAME_FRAGMENTS):
            forbidden_files.append(relative)
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if any(needle in payload for needle in needles):
            development_path_hits.append(relative)
    return forbidden_files, development_path_hits


def _find_runtime_asset(release_dir: Path) -> Path:
    matches = list(release_dir.rglob("fullbody_runtime_master.png"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one packaged runtime asset; found {len(matches)}.")
    return matches[0]


def _find_qwindows(release_dir: Path) -> list[Path]:
    return [path for path in release_dir.rglob("qwindows.dll") if path.is_file()]


def _desktop_pet_processes() -> set[int]:
    command = ["tasklist", "/FI", "IMAGENAME eq DesktopPet.exe", "/FO", "CSV", "/NH"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        if not line.lstrip().startswith('"DesktopPet.exe"'):
            continue
        fields = [field.strip('"') for field in line.split('","')]
        if len(fields) > 1 and fields[1].isdigit():
            pids.add(int(fields[1]))
    return pids


def verify_release(release_dir: Path, *, label: str = "onedir") -> dict[str, object]:
    release_dir = Path(release_dir).resolve()
    executable = release_dir / "DesktopPet.exe"
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    checks["executable_exists"] = executable.is_file()
    if not checks["executable_exists"]:
        raise FileNotFoundError(f"Frozen executable not found: {executable}")
    checks["gui_subsystem"] = pe_subsystem(executable) == 2
    qwindows = _find_qwindows(release_dir)
    checks["qt_platform_plugin_present"] = bool(qwindows)
    asset = _find_runtime_asset(release_dir)
    asset_hash = sha256_file(asset)
    checks["runtime_asset_hash"] = asset_hash == EXPECTED_RUNTIME_ASSET_SHA256
    forbidden, path_hits = _scan_release(release_dir)
    checks["forbidden_files_absent"] = not forbidden
    checks["development_paths_absent"] = not path_hits

    before_pids = _desktop_pet_processes()
    started_at = time.perf_counter()
    temporary_parent = PROJECT_ROOT / "build" / "temp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="desktop_pet_frozen_verify_", dir=temporary_parent) as temporary:
        temp_root = Path(temporary)
        result_path = temp_root / "result.json"
        config_dir = temp_root / "config"
        unrelated_cwd = temp_root / "unrelated-working-directory"
        unrelated_cwd.mkdir()
        environment = os.environ.copy()
        for variable in ("CONDA_DEFAULT_ENV", "CONDA_PREFIX", "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
            environment.pop(variable, None)
        completed = subprocess.run(
            [
                str(executable),
                "--release-smoke-test",
                "--quit-after-ms",
                "1800",
                "--config-dir",
                str(config_dir),
                "--no-tray",
                "--smoke-result",
                str(result_path),
            ],
            cwd=unrelated_cwd,
            env=environment,
            capture_output=True,
            timeout=30,
            check=False,
        )
        launch_seconds = time.perf_counter() - started_at
        checks["clean_direct_launch"] = completed.returncode == 0 and result_path.is_file()
        smoke = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
        expected_sizes = [[240, 360], [280, 420], [320, 480]]
        checks.update(
            frozen_mode=smoke.get("frozen") is True,
            single_pet_window=smoke.get("window_count") == 1,
            translucent_window=smoke.get("translucent_background") is True,
            animation_controller=smoke.get("animation_controller") is True,
            one_high_frequency_timer=smoke.get("high_frequency_timer_count") == 1,
            asset_loaded_once=smoke.get("asset_load_count") == 1,
            three_sizes_work=smoke.get("size_switch_results") == expected_sizes,
            position_saved=smoke.get("position_saved") is True,
            temporary_settings=smoke.get("settings_file_created") is True,
            no_tray_degradation=smoke.get("tray_available") is False,
            normal_terminal_state=smoke.get("terminal_state") == "STOPPED",
            smoke_asset_hash=smoke.get("runtime_asset_sha256") == EXPECTED_RUNTIME_ASSET_SHA256,
        )
        runtime_path = Path(str(smoke.get("runtime_asset_path", ""))).resolve()
        checks["frozen_asset_path"] = runtime_path == asset.resolve() and runtime_path.is_relative_to(release_dir)
        checks["temporary_config_path"] = Path(str(smoke.get("settings_path", ""))).is_relative_to(config_dir)
        details["smoke_result"] = smoke
        details["return_code"] = completed.returncode
        details["launch_and_exit_seconds"] = round(launch_seconds, 3)
    time.sleep(0.5)
    after_pids = _desktop_pet_processes()
    checks["no_residual_process"] = not (after_pids - before_pids)

    details.update(
        label=label,
        release_dir=str(release_dir),
        executable=str(executable),
        executable_size=executable.stat().st_size,
        pe_subsystem=pe_subsystem(executable),
        runtime_asset=str(asset.relative_to(release_dir)),
        runtime_asset_sha256=asset_hash,
        qwindows=[str(path.relative_to(release_dir)) for path in qwindows],
        forbidden_files=forbidden,
        development_path_hits=path_hits,
    )
    passed = all(checks.values())
    return {"passed": passed, "checks": checks, "details": details}


def write_report(report: dict[str, object]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checks = report["checks"]
    assert isinstance(checks, dict)
    lines = [
        "# Frozen release verification",
        "",
        f"Result: {'PASSED' if report['passed'] else 'FAILED'}",
        "",
        "| Check | Result |",
        "|---|---|",
        *(f"| {name} | {'PASS' if value else 'FAIL'} |" for name, value in checks.items()),
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "release_dir",
        nargs="?",
        type=Path,
        default=PROJECT_ROOT / "dist" / "pyinstaller" / "DesktopPet",
    )
    parser.add_argument("--label", default="onedir")
    namespace = parser.parse_args(argv)
    report = verify_release(namespace.release_dir, label=namespace.label)
    write_report(report)
    print(f"Frozen release verification: {'passed' if report['passed'] else 'failed'}")
    print(f"Report: {REPORT_JSON}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
