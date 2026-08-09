"""Fail-fast Stage 10 Windows onedir release pipeline."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from create_release_archive import create_archive
from desktop_pet.paths import FULLBODY_RUNTIME_MASTER, PROJECT_ROOT
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256
from desktop_pet.version import __version__
from generate_release_checksums import generate_checksums, sha256_file
from verify_frozen_release import verify_release

BUILD_DIR = PROJECT_ROOT / "build" / "pyinstaller"
DIST_ROOT = PROJECT_ROOT / "dist" / "pyinstaller"
DIST_DIR = DIST_ROOT / "DesktopPet"
RELEASE_DIR = PROJECT_ROOT / "release"
REPORTS_DIR = PROJECT_ROOT / "build" / "reports"
SPEC_PATH = PROJECT_ROOT / "packaging" / "windows" / "desktop_pet.spec"
ZIP_PATH = RELEASE_DIR / f"DesktopPet-{__version__}-win64-portable.zip"
MANIFEST_PATH = RELEASE_DIR / f"release_manifest_{__version__}.json"
NOTES_PATH = RELEASE_DIR / f"RELEASE_NOTES_{__version__}.txt"
CHECKSUMS_PATH = RELEASE_DIR / f"checksums_{__version__}.sha256"


def run_checked(command: list[str], *, label: str) -> str:
    print(f"[{label}] {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout.rstrip(), flush=True)
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}.")
    return completed.stdout


def validate_build_environment() -> dict[str, str]:
    if platform.system() != "Windows" or platform.architecture()[0] != "64bit":
        raise RuntimeError("Desktop Pet releases must be built on 64-bit Windows.")
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f"Python 3.11 is required; found {platform.python_version()}.")
    if os.environ.get("CONDA_DEFAULT_ENV") != "dp" or Path(sys.prefix).name.casefold() != "dp":
        raise RuntimeError(f"The release pipeline must run inside Conda environment dp; prefix={sys.prefix}")
    versions = {
        "python": platform.python_version(),
        "pyside": importlib.metadata.version("PySide6"),
        "pillow": importlib.metadata.version("Pillow"),
        "pyinstaller": importlib.metadata.version("PyInstaller"),
    }
    if versions["pyinstaller"] != "6.21.0":
        raise RuntimeError(f"Expected PyInstaller 6.21.0; found {versions['pyinstaller']}.")
    return versions


def validate_master() -> str:
    digest = sha256_file(FULLBODY_RUNTIME_MASTER)
    if digest != EXPECTED_RUNTIME_ASSET_SHA256:
        raise RuntimeError(f"Approved runtime master hash mismatch: {digest}")
    return digest


def validate_long_run_report() -> dict[str, object]:
    path = REPORTS_DIR / "long_run_stability.json"
    if not path.is_file():
        raise FileNotFoundError("Run the complete 600-second stability test before packaging.")
    report = json.loads(path.read_text(encoding="utf-8"))
    duration = float(report.get("actual_duration_seconds", 0))
    if not report.get("passed") or duration < 600:
        raise RuntimeError(f"A passing stability report of at least 600 seconds is required; found {duration:.2f}s.")
    return report


def safe_clean(path: Path, *, parent: Path) -> None:
    resolved = path.resolve()
    expected_parent = parent.resolve()
    if resolved.parent != expected_parent or resolved.name.casefold() != "pyinstaller":
        raise ValueError(f"Refusing to clean unexpected path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def run_source_regression() -> tuple[int, list[str]]:
    checks = [
        ([sys.executable, "scripts/check_environment.py"], "environment"),
        ([sys.executable, "scripts/render_animation_diagnostics.py"], "animation diagnostics"),
        ([sys.executable, "scripts/render_behavior_diagnostics.py"], "behavior diagnostics"),
        ([sys.executable, "scripts/render_interaction_diagnostics.py"], "interaction diagnostics"),
        ([sys.executable, "scripts/smoke_test_pet_window.py", "--offscreen"], "window smoke"),
        ([sys.executable, "scripts/smoke_test_animation.py", "--offscreen"], "animation smoke"),
        ([sys.executable, "scripts/smoke_test_behavior.py", "--offscreen"], "behavior smoke"),
        ([sys.executable, "scripts/smoke_test_interaction.py", "--offscreen"], "interaction smoke"),
        ([sys.executable, "scripts/smoke_test_settings.py", "--offscreen"], "settings smoke"),
        ([sys.executable, "scripts/smoke_test_tray.py", "--offscreen"], "tray smoke"),
        ([sys.executable, "scripts/audit_runtime_imports.py"], "runtime import audit"),
    ]
    labels: list[str] = []
    for command, label in checks:
        run_checked(command, label=label)
        labels.append(label)
    output = run_checked([sys.executable, "-m", "pytest", "tests", "-q"], label="pytest")
    match = re.search(r"(\d+) passed", output)
    if match is None:
        raise RuntimeError("Could not determine the passing pytest count.")
    run_checked([sys.executable, "-m", "ruff", "check", "."], label="ruff")
    return int(match.group(1)), labels


def copy_release_documents() -> None:
    guide = (PROJECT_ROOT / "docs" / "user_guide_zh-CN.md").read_text(encoding="utf-8")
    (DIST_DIR / "使用说明.txt").write_text(guide, encoding="utf-8", newline="\n")
    internal_notes = (
        f"Desktop Pet {__version__}\n\n"
        "This directory is the recommended Windows x64 portable onedir release.\n"
        "See 使用说明.txt for usage and known limitations.\n"
        f"Approved runtime asset SHA-256: {EXPECTED_RUNTIME_ASSET_SHA256}\n"
        "The ZIP checksum is published beside the archive in checksums_1.0.0.sha256.\n"
    )
    (DIST_DIR / "RELEASE_NOTES.txt").write_text(internal_notes, encoding="utf-8", newline="\n")
    internal_files = [
        DIST_DIR / "DesktopPet.exe",
        next(DIST_DIR.rglob("fullbody_runtime_master.png")),
        DIST_DIR / "使用说明.txt",
        DIST_DIR / "RELEASE_NOTES.txt",
    ]
    generate_checksums(internal_files, DIST_DIR / "checksums.sha256", relative_to=DIST_DIR)


def write_release_notes(zip_digest: str, pytest_count: int) -> None:
    content = f"""Desktop Pet {__version__}

发布范围：Windows x64 PyInstaller onedir 便携版。

核心功能：完整人物透明桌宠、待机动画、基础状态机、单击反馈、拖拽、托盘、三档尺寸、置顶、设置和位置记忆。

已知限制：未数字签名；透明区域仍阻挡下层窗口鼠标；没有自动移动、行走、跳跃、表情帧、对话、音效、开机启动、网络功能或自动更新。

测试摘要：{pytest_count} 项 pytest 通过；ruff、源码烟雾测试、运行时导入审计、600 秒稳定性测试通过；
未压缩版和 ZIP 解压版冻结烟雾测试通过。

设置路径：Qt AppConfigLocation 下的 DesktopPet/settings.ini。
崩溃日志：Qt AppLocalDataLocation 下的 DesktopPet/logs/。

正式主图 SHA-256：{EXPECTED_RUNTIME_ASSET_SHA256}
发布包 SHA-256：{zip_digest}

未在独立 Windows Sandbox 中验证；已从临时解压目录直接运行 EXE，运行时未注入 Conda 或 PYTHONPATH。
"""
    NOTES_PATH.write_text(content, encoding="utf-8", newline="\n")


def write_release_manifest(
    *,
    versions: dict[str, str],
    pytest_count: int,
    zip_digest: str,
    long_run: dict[str, object],
) -> dict[str, object]:
    manifest = {
        "product": "Desktop Pet",
        "version": __version__,
        "platform": "Windows x64",
        "build_type": "PyInstaller onedir",
        "python_version": versions["python"],
        "pyside_version": versions["pyside"],
        "pyinstaller_version": versions["pyinstaller"],
        "entry_executable": "DesktopPet/DesktopPet.exe",
        "asset": {
            "relative_path": "DesktopPet/_internal/assets/fullbody/final/fullbody_runtime_master.png",
            "sha256": EXPECTED_RUNTIME_ASSET_SHA256,
        },
        "artifacts": [
            {
                "path": ZIP_PATH.name,
                "size": ZIP_PATH.stat().st_size,
                "sha256": zip_digest,
                "purpose": "Recommended portable onedir release",
                "recommended": True,
            }
        ],
        "tests": {
            "pytest_passed": pytest_count,
            "ruff": "passed",
            "source_smoke_tests": "passed",
            "frozen_smoke_test": "passed for onedir and extracted ZIP",
            "long_run_test": f"passed ({float(long_run.get('actual_duration_seconds', 0)):.2f} seconds)",
        },
        "known_limits": [
            "unsigned executable",
            "no true transparent-pixel pass-through",
            "no automatic movement or frame animation",
            "no startup registration or automatic update",
            "not verified in an independent Windows Sandbox",
        ],
        "build_machine_paths_included": False,
        "digital_signature": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_frozen_verification_reports(
    onedir: dict[str, object],
    extracted_zip: dict[str, object],
) -> None:
    combined = {
        "passed": bool(onedir["passed"] and extracted_zip["passed"]),
        "onedir": onedir,
        "extracted_zip": extracted_zip,
    }
    json_path = REPORTS_DIR / "frozen_release_verification.json"
    markdown_path = REPORTS_DIR / "frozen_release_verification.md"
    json_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Frozen release verification",
        "",
        f"Overall result: {'PASS' if combined['passed'] else 'FAIL'}",
        "",
        "| Release | Check | Result |",
        "|---|---|---|",
    ]
    for label, report in (("onedir", onedir), ("extracted ZIP", extracted_zip)):
        checks = report["checks"]
        assert isinstance(checks, dict)
        lines.extend(f"| {label} | {name} | {'PASS' if value else 'FAIL'} |" for name, value in checks.items())
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build_release() -> dict[str, object]:
    started = datetime.now(UTC)
    versions = validate_build_environment()
    hash_points: dict[str, str] = {"before_build_pipeline": validate_master()}
    long_run = validate_long_run_report()
    pytest_count, smoke_labels = run_source_regression()
    hash_points["after_source_regression"] = validate_master()
    run_checked([sys.executable, "scripts/build_app_icon.py"], label="application icon")
    safe_clean(BUILD_DIR, parent=PROJECT_ROOT / "build")
    safe_clean(DIST_ROOT, parent=PROJECT_ROOT / "dist")
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_PATH.unlink(missing_ok=True)
    CHECKSUMS_PATH.unlink(missing_ok=True)
    run_checked(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST_ROOT),
            "--workpath",
            str(BUILD_DIR),
            str(SPEC_PATH),
        ],
        label="PyInstaller onedir",
    )
    hash_points["after_pyinstaller"] = validate_master()
    copy_release_documents()
    uncompressed = verify_release(DIST_DIR, label="onedir")
    if not uncompressed["passed"]:
        raise RuntimeError("The uncompressed frozen release failed verification.")
    archived_files = create_archive(DIST_DIR, ZIP_PATH)
    hash_points["after_zip"] = validate_master()
    temporary_parent = PROJECT_ROOT / "build" / "temp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="desktop_pet_release_extract_", dir=temporary_parent) as temporary:
        shutil.unpack_archive(ZIP_PATH, temporary, "zip")
        extracted = verify_release(Path(temporary) / "DesktopPet", label="extracted-zip")
    if not extracted["passed"]:
        raise RuntimeError("The extracted portable ZIP failed frozen verification.")
    write_frozen_verification_reports(uncompressed, extracted)
    zip_digest = sha256_file(ZIP_PATH)
    write_release_notes(zip_digest, pytest_count)
    manifest = write_release_manifest(
        versions=versions,
        pytest_count=pytest_count,
        zip_digest=zip_digest,
        long_run=long_run,
    )
    generate_checksums([ZIP_PATH, MANIFEST_PATH, NOTES_PATH], CHECKSUMS_PATH, relative_to=RELEASE_DIR)
    hash_points["stage_end"] = validate_master()
    report = {
        "passed": True,
        "version": __version__,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "versions": versions,
        "pytest_passed": pytest_count,
        "source_smoke_tests": smoke_labels,
        "long_run": long_run,
        "hash_checkpoints": hash_points,
        "onedir_verification": uncompressed,
        "extracted_zip_verification": extracted,
        "archived_files": archived_files,
        "release_manifest": manifest,
        "onefile": "not built; onedir is the required and recommended low-risk release",
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "release_build_1.0.0.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Release complete: {ZIP_PATH}")
    print(f"SHA-256: {zip_digest}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    build_release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
