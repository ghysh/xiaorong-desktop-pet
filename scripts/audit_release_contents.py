"""Audit the minimal XiaoRong 1.2.0 release directory and PyInstaller archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.version import __version__

EXECUTABLE_NAME = f"小融-{__version__}-win64.exe"
EXPECTED_RELEASE_FILES = frozenset({EXECUTABLE_NAME})
DROWSY_SLEEP_MANIFEST = PROJECT_ROOT / "assets" / "actions" / "drowsy_sleep" / "manifest.json"
DROWSY_SLEEP_FRAME_ENTRIES = tuple(
    f"assets/actions/drowsy_sleep/{path.as_posix()}"
    for path in sorted(
        {
            Path(frame["asset_path"])
            for frame in json.loads(DROWSY_SLEEP_MANIFEST.read_text(encoding="utf-8"))["frames"]
        }
    )
)
REQUIRED_ARCHIVE_ENTRIES = (
    "assets/fullbody/final/fullbody_runtime_master.png",
    "assets/actions/click_reply/dialogue.txt",
    "assets/actions/click_reply/dialogue_bubble_frame.png",
    "assets/icons/character_original.ico",
    "assets/actions/blink/manifest.json",
    "assets/actions/blink/frames/blink_open.png",
    "assets/actions/blink/frames/blink_half_closed.png",
    "assets/actions/blink/frames/blink_closed.png",
    "assets/actions/blink/frames/blink_half_open.png",
    "assets/actions/drowsy_sleep/manifest.json",
    *DROWSY_SLEEP_FRAME_ENTRIES,
)
FORBIDDEN_ARCHIVE_FRAGMENTS = (
    "ori_figure",
    "assets/original",
    "assets/analysis",
    "assets/fullbody/concepts",
    "assets/fullbody/diagnostics",
    "assets/fullbody/intermediate",
    "assets/fullbody/previews",
    "assets/fullbody/reports",
    "assets/fullbody/selected",
    "assets/actions/walk_left",
    "assets/actions/walk_right",
    "assets/actions/sit_cross_legged",
    "assets/actions/sleep_cross_legged",
    "assets/actions/wake_up",
    "assets/actions/dances",
    "source_notes.md",
    "tests/",
    "docs/",
    "scripts/",
    "release_archive",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
)
FORBIDDEN_ANALYSIS_MODULES = ("cv2", "numpy", "pytest", "ruff", "tkinter")


def archive_entries(executable: Path) -> tuple[str, ...]:
    archive = CArchiveReader(str(executable))
    return tuple(sorted(str(name).replace("\\", "/") for name in archive.toc))


def audit_release(
    release_dir: Path,
    *,
    analysis_toc: Path | None = None,
) -> dict[str, object]:
    release_dir = release_dir.resolve()
    actual_files = {
        path.relative_to(release_dir).as_posix()
        for path in release_dir.rglob("*")
        if path.is_file()
    }
    actual_directories = {
        path.relative_to(release_dir).as_posix()
        for path in release_dir.rglob("*")
        if path.is_dir()
    }
    executable = release_dir / EXECUTABLE_NAME
    entries = archive_entries(executable) if executable.is_file() else ()
    folded_entries = tuple(entry.casefold() for entry in entries)
    missing_archive_entries = [
        required for required in REQUIRED_ARCHIVE_ENTRIES if required.casefold() not in folded_entries
    ]
    forbidden_archive_entries = [
        entry
        for entry in entries
        if any(fragment.casefold() in entry.casefold() for fragment in FORBIDDEN_ARCHIVE_FRAGMENTS)
    ]
    qt_platform_plugins = [
        entry for entry in entries if entry.casefold().endswith("pyside6/plugins/platforms/qwindows.dll")
    ]

    analysis_hits: list[str] = []
    if analysis_toc is not None:
        toc_text = analysis_toc.read_text(encoding="utf-8", errors="replace")
        analysis_hits = [module for module in FORBIDDEN_ANALYSIS_MODULES if f"('{module}'" in toc_text]

    checks = {
        "release_directory_exists": release_dir.is_dir(),
        "exact_one_file": actual_files == EXPECTED_RELEASE_FILES and not actual_directories,
        "executable_nonempty": executable.is_file() and executable.stat().st_size > 0,
        "required_runtime_resources": not missing_archive_entries,
        "development_resources_absent": not forbidden_archive_entries,
        "qt_windows_platform_plugin": len(qt_platform_plugins) == 1,
        "development_modules_excluded": not analysis_hits,
    }
    return {
        "passed": all(checks.values()),
        "release_dir": str(release_dir),
        "actual_files": sorted(actual_files),
        "actual_directories": sorted(actual_directories),
        "checks": checks,
        "archive_entry_count": len(entries),
        "required_archive_entries": list(REQUIRED_ARCHIVE_ENTRIES),
        "missing_archive_entries": missing_archive_entries,
        "forbidden_archive_entries": forbidden_archive_entries,
        "qt_windows_platform_plugins": qt_platform_plugins,
        "analysis_toc": None if analysis_toc is None else str(analysis_toc.resolve()),
        "forbidden_analysis_modules": analysis_hits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=PROJECT_ROOT / "release")
    parser.add_argument("--analysis-toc", type=Path)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "build" / "reports" / "release_contents_audit_1_2_0.json",
    )
    namespace = parser.parse_args(argv)
    report = audit_release(namespace.release_dir, analysis_toc=namespace.analysis_toc)
    namespace.report.parent.mkdir(parents=True, exist_ok=True)
    namespace.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Release contents audit: {'passed' if report['passed'] else 'failed'}")
    print(f"Report: {namespace.report.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
