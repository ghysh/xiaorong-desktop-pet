"""Audit the minimal XiaoRong 1.1.0 release directory and PyInstaller archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.version import __version__

EXECUTABLE_NAME = f"小融-{__version__}-win64.exe"
GUIDE_NAME = "使用说明.txt"
CHECKSUM_NAME = "checksums.sha256"
EXPECTED_RELEASE_FILES = frozenset({EXECUTABLE_NAME, GUIDE_NAME, CHECKSUM_NAME})
REQUIRED_ARCHIVE_ENTRIES = (
    "assets/fullbody/final/fullbody_runtime_master.png",
    "assets/actions/click_reply/dialogue.txt",
    "assets/icons/character_original.ico",
    "assets/actions/blink/manifest.json",
    "assets/actions/blink/frames/blink_open.png",
    "assets/actions/blink/frames/blink_half_closed.png",
    "assets/actions/blink/frames/blink_closed.png",
    "assets/actions/blink/frames/blink_half_open.png",
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
    "tests/",
    "docs/",
    "scripts/",
    ".pytest_cache",
    ".ruff_cache",
)
FORBIDDEN_ANALYSIS_MODULES = ("cv2", "numpy", "pytest", "ruff", "tkinter")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def archive_entries(executable: Path) -> tuple[str, ...]:
    archive = CArchiveReader(str(executable))
    return tuple(sorted(str(name).replace("\\", "/") for name in archive.toc))


def parse_checksums(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        digest, marker, relative = stripped.partition(" *")
        if not marker or len(digest) != 64:
            raise ValueError(f"Invalid checksum line: {line!r}")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts or relative in records:
            raise ValueError(f"Non-portable checksum entry: {relative}")
        records[relative] = digest.upper()
    return records


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
    guide = release_dir / GUIDE_NAME
    checksum_path = release_dir / CHECKSUM_NAME
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

    checksum_records = parse_checksums(checksum_path) if checksum_path.is_file() else {}
    checksum_targets = {EXECUTABLE_NAME, GUIDE_NAME}
    checksum_mismatches = [
        name
        for name, digest in checksum_records.items()
        if not (release_dir / name).is_file() or sha256_file(release_dir / name) != digest
    ]

    analysis_hits: list[str] = []
    if analysis_toc is not None:
        toc_text = analysis_toc.read_text(encoding="utf-8", errors="replace")
        analysis_hits = [module for module in FORBIDDEN_ANALYSIS_MODULES if f"('{module}'" in toc_text]

    checks = {
        "release_directory_exists": release_dir.is_dir(),
        "exact_three_files": actual_files == EXPECTED_RELEASE_FILES and not actual_directories,
        "executable_nonempty": executable.is_file() and executable.stat().st_size > 0,
        "guide_nonempty_utf8": guide.is_file() and bool(guide.read_text(encoding="utf-8-sig").strip()),
        "checksum_entries_exact": set(checksum_records) == checksum_targets,
        "checksum_values_match": not checksum_mismatches,
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
        "checksum_records": checksum_records,
        "checksum_mismatches": checksum_mismatches,
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
        default=PROJECT_ROOT / "build" / "reports" / "release_contents_audit_1_1_0.json",
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
