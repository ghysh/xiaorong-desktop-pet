"""Fail-fast Windows build pipeline for the minimal XiaoRong 1.1.0 release."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import PIL
import PyInstaller
import PySide6
from PIL import Image

from audit_release_contents import audit_release
from desktop_pet.paths import (
    APPLICATION_ICON,
    BLINK_FRAMES_DIR,
    BLINK_MANIFEST,
    CLICK_DIALOGUE_FILE,
    FULLBODY_RUNTIME_MASTER,
    PROJECT_ROOT,
)
from desktop_pet.ui.pet_window import EXPECTED_RUNTIME_ASSET_SHA256
from desktop_pet.version import WINDOWS_FILE_VERSION, __version__
from generate_release_checksums import generate_checksums, sha256_file
from verify_xiaorong_release import verify_executable

BUILD_ROOT = PROJECT_ROOT / "build" / "pyinstaller" / "xiaorong_1_1_0"
DIST_ROOT = PROJECT_ROOT / "dist" / "pyinstaller" / "xiaorong_1_1_0"
REPORTS_DIR = PROJECT_ROOT / "build" / "reports"
RELEASE_DIR = PROJECT_ROOT / "release"
SPEC_PATH = PROJECT_ROOT / "packaging" / "windows" / "xiaorong.spec"
FINAL_EXECUTABLE_NAME = "小融-1.1.0-win64.exe"
GUIDE_NAME = "使用说明.txt"
CHECKSUM_NAME = "checksums.sha256"
EXPECTED_PYTHON = (3, 11, 15)
RUNTIME_RESOURCES = (
    (FULLBODY_RUNTIME_MASTER, "正式角色主图"),
    (CLICK_DIALOGUE_FILE, "当前点击对白"),
    (APPLICATION_ICON, "应用与托盘图标"),
    (BLINK_MANIFEST, "已接入的自然眨眼清单"),
    (BLINK_FRAMES_DIR / "blink_open.png", "自然眨眼帧"),
    (BLINK_FRAMES_DIR / "blink_half_closed.png", "自然眨眼帧"),
    (BLINK_FRAMES_DIR / "blink_closed.png", "自然眨眼帧"),
    (BLINK_FRAMES_DIR / "blink_half_open.png", "自然眨眼帧"),
)
GUIDE_TEXT = """小融 1.1.0

使用方法：
双击“小融-1.1.0-win64.exe”即可运行，无需安装。

基本操作：
1. 左键单击角色：触发互动。
2. 左键拖动角色：移动位置。
3. 右键角色或托盘图标：打开功能菜单。
4. 完全退出请使用右键菜单或托盘菜单中的“退出桌宠”。

程序设置保存在当前 Windows 用户的本地应用配置目录中。
删除本程序不会自动删除个人设置。

已知限制：
透明窗口的完全透明区域仍可能阻挡下层窗口的鼠标操作。
本程序未进行数字签名，Windows 可能显示未知发布者提示。
"""


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def announce(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def run_command(command: list[str], *, capture: bool = True, environment: dict[str, str] | None = None) -> str:
    announce("运行：" + subprocess.list2cmdline(command))
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
        check=False,
    )
    output = ""
    if capture:
        output = (completed.stdout or "") + (completed.stderr or "")
        print(output.rstrip(), flush=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {subprocess.list2cmdline(command)}")
    return output


def assert_build_environment() -> dict[str, str]:
    if platform.system() != "Windows" or platform.machine().casefold() not in {"amd64", "x86_64"}:
        raise RuntimeError("小融 1.1.0 只能在 Windows x64 构建。")
    if os.environ.get("CONDA_DEFAULT_ENV") != "dp" or Path(sys.prefix).name.casefold() != "dp":
        raise RuntimeError(f"构建必须在 dp 环境中运行；当前 prefix={sys.prefix!r}。")
    if sys.version_info[:3] != EXPECTED_PYTHON:
        raise RuntimeError(f"构建需要 Python {'.'.join(map(str, EXPECTED_PYTHON))}；当前={platform.python_version()}。")
    if __version__ != "1.1.0" or WINDOWS_FILE_VERSION != (1, 1, 0, 0):
        raise RuntimeError("应用版本元数据不是 1.1.0。")
    return {
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "conda_environment": os.environ.get("CONDA_DEFAULT_ENV", ""),
        "PySide6": PySide6.__version__,
        "Pillow": PIL.__version__,
        "PyInstaller": PyInstaller.__version__,
    }


def inspect_protected_inputs() -> dict[str, object]:
    for path, _purpose in RUNTIME_RESOURCES:
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"运行资源不存在或为空：{path}")
    with Image.open(FULLBODY_RUNTIME_MASTER) as image:
        image.verify()
    with Image.open(APPLICATION_ICON) as icon:
        if icon.format != "ICO":
            raise ValueError(f"指定图标不是 ICO：{APPLICATION_ICON}")
        icon_sizes = sorted([list(size) for size in icon.ico.sizes()])
    with Image.open(BLINK_FRAMES_DIR / "blink_open.png") as frame:
        frame.verify()
    dialogue = CLICK_DIALOGUE_FILE.read_text(encoding="utf-8-sig")
    if not dialogue.strip():
        raise ValueError("点击对白文件为空。")
    master_hash = sha256_file(FULLBODY_RUNTIME_MASTER)
    if master_hash != EXPECTED_RUNTIME_ASSET_SHA256:
        raise RuntimeError(f"正式主图 SHA-256 不匹配：{master_hash}")
    return {
        "master": {
            "path": str(FULLBODY_RUNTIME_MASTER),
            "sha256": master_hash,
            "size": FULLBODY_RUNTIME_MASTER.stat().st_size,
            "modified_ns": FULLBODY_RUNTIME_MASTER.stat().st_mtime_ns,
        },
        "dialogue": {
            "path": str(CLICK_DIALOGUE_FILE),
            "sha256": sha256_file(CLICK_DIALOGUE_FILE),
            "size": CLICK_DIALOGUE_FILE.stat().st_size,
            "modified_ns": CLICK_DIALOGUE_FILE.stat().st_mtime_ns,
        },
        "icon": {
            "path": str(APPLICATION_ICON),
            "sha256": sha256_file(APPLICATION_ICON),
            "size": APPLICATION_ICON.stat().st_size,
            "modified_ns": APPLICATION_ICON.stat().st_mtime_ns,
            "ico_sizes": icon_sizes,
        },
    }


def write_runtime_resource_manifest() -> dict[str, object]:
    records = []
    for path, purpose in RUNTIME_RESOURCES:
        records.append(
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "purpose": purpose,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "product": "小融",
        "version": __version__,
        "generated_at_utc": timestamp(),
        "resource_count": len(records),
        "resources": records,
        "planned_actions_included": False,
        "original_character_images_included": False,
        "development_assets_included": False,
    }
    path = REPORTS_DIR / "runtime_resource_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def safe_clean_version_directory(path: Path, allowed_parent: Path) -> None:
    resolved_path = path.resolve()
    resolved_parent = allowed_parent.resolve()
    if resolved_path.parent != resolved_parent or resolved_path.name != "xiaorong_1_1_0":
        raise RuntimeError(f"拒绝清理未经验证的构建目录：{resolved_path}")
    if resolved_path.exists():
        announce(f"清理本版本专用构建目录：{resolved_path}")
        shutil.rmtree(resolved_path)


def pyinstaller_build(mode: str) -> tuple[Path, Path]:
    work_path = BUILD_ROOT / mode
    dist_path = DIST_ROOT / mode
    environment = os.environ.copy()
    environment["XIAORONG_BUILD_MODE"] = mode
    run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--workpath",
            str(work_path),
            "--distpath",
            str(dist_path),
            str(SPEC_PATH),
        ],
        capture=False,
        environment=environment,
    )
    executable = dist_path / "小融" / "小融.exe" if mode == "onedir" else dist_path / "小融.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller 未生成预期 {mode} 程序：{executable}")
    pyz_tocs = list(work_path.rglob("PYZ-00.toc"))
    if len(pyz_tocs) != 1:
        raise RuntimeError(f"{mode} 构建应有一个 PYZ-00.toc，实际为 {len(pyz_tocs)}。")
    return executable, pyz_tocs[0]


def verify_clean_onedir(executable: Path) -> dict[str, object]:
    source_directory = executable.parent
    with tempfile.TemporaryDirectory(prefix="XiaoRongOnedirTest_") as temporary:
        copied_directory = Path(temporary) / "小融便携目录"
        shutil.copytree(source_directory, copied_directory)
        return verify_executable(
            copied_directory / "小融.exe",
            kind="onedir",
            label="clean-onedir",
            expected_name="小融.exe",
        )


def verify_clean_onefile(executable: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="XiaoRongReleaseTest_") as temporary:
        copied = Path(temporary) / "中文发布测试" / FINAL_EXECUTABLE_NAME
        copied.parent.mkdir()
        shutil.copy2(executable, copied)
        return verify_executable(
            copied,
            kind="onefile",
            label="clean-onefile-chinese-path",
            expected_name=FINAL_EXECUTABLE_NAME,
        )


def verify_double_launch(executable: Path) -> dict[str, object]:
    """Document the existing no-single-instance behavior without changing release scope."""
    with tempfile.TemporaryDirectory(prefix="XiaoRongDoubleLaunch_") as temporary:
        root = Path(temporary)
        processes: list[subprocess.Popen[bytes]] = []
        result_paths: list[Path] = []
        environment = os.environ.copy()
        for variable in tuple(environment):
            if variable.startswith(("CONDA_", "PYTHON")) or variable == "VIRTUAL_ENV":
                environment.pop(variable, None)
        for index in range(2):
            result = root / f"result-{index}.json"
            result_paths.append(result)
            processes.append(
                subprocess.Popen(
                    [
                        str(executable),
                        "--release-smoke-test",
                        "--quit-after-ms",
                        "3000",
                        "--config-dir",
                        str(root / f"config-{index}"),
                        "--no-tray",
                        "--smoke-result",
                        str(result),
                    ],
                    cwd=root,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            time.sleep(0.2)
        return_codes = [process.wait(timeout=50) for process in processes]
        snapshots = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths if path.is_file()]
    passed = return_codes == [0, 0] and len(snapshots) == 2
    return {
        "passed": passed,
        "single_instance_protection": False,
        "observed_instances": len(snapshots),
        "return_codes": return_codes,
        "known_limitation": "连续启动会创建两个独立实例；1.1.0 未新增单实例机制。",
    }


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    build_started = timestamp()
    started = time.perf_counter()
    announce("验证 dp 构建环境、版本和固定输入")
    versions = assert_build_environment()
    protected_before = inspect_protected_inputs()
    runtime_manifest = write_runtime_resource_manifest()

    announce("执行环境检查、完整 pytest、Ruff 和运行依赖审计")
    environment_output = run_command([sys.executable, "scripts/check_environment.py"])
    pytest_output = run_command([sys.executable, "-m", "pytest", "tests", "-q"])
    pytest_match = re.search(r"(\d+) passed", pytest_output)
    if pytest_match is None:
        raise RuntimeError("无法从 pytest 输出确认通过数量。")
    pytest_passed = int(pytest_match.group(1))
    ruff_output = run_command([sys.executable, "-m", "ruff", "check", "."])
    run_command([sys.executable, "scripts/audit_runtime_imports.py"])
    import_audit_path = REPORTS_DIR / "runtime_import_audit_1_1_0.json"
    import_audit = json.loads(import_audit_path.read_text(encoding="utf-8"))
    if import_audit.get("passed") is not True:
        raise RuntimeError("运行依赖审计失败。")

    announce("执行源码入口烟雾测试")
    with tempfile.TemporaryDirectory(prefix="XiaoRongSourceSmoke_") as temporary:
        root = Path(temporary)
        source_result = root / "source_smoke.json"
        run_command(
            [
                sys.executable,
                "-m",
                "desktop_pet",
                "--release-smoke-test",
                "--quit-after-ms",
                "1200",
                "--config-dir",
                str(root / "config"),
                "--no-tray",
                "--smoke-result",
                str(source_result),
            ]
        )
        source_smoke = json.loads(source_result.read_text(encoding="utf-8"))
        if source_smoke.get("version") != __version__ or source_smoke.get("status") != "passed":
            raise RuntimeError("源码入口烟雾测试结果无效。")

    safe_clean_version_directory(BUILD_ROOT, PROJECT_ROOT / "build" / "pyinstaller")
    safe_clean_version_directory(DIST_ROOT, PROJECT_ROOT / "dist" / "pyinstaller")

    announce("构建并验证 PyInstaller onedir")
    onedir_executable, _onedir_pyz_toc = pyinstaller_build("onedir")
    onedir_report = verify_executable(
        onedir_executable,
        kind="onedir",
        label="build-onedir",
        expected_name="小融.exe",
    )
    write_report(REPORTS_DIR / "xiaorong_onedir_verification_1_1_0.json", onedir_report)
    if not onedir_report["passed"]:
        raise RuntimeError("onedir 本地验证失败。")
    clean_onedir_report = verify_clean_onedir(onedir_executable)
    write_report(REPORTS_DIR / "xiaorong_onedir_clean_path_1_1_0.json", clean_onedir_report)
    if not clean_onedir_report["passed"]:
        raise RuntimeError("onedir 清洁路径验证失败。")

    announce("onedir 通过，开始构建并验证 PyInstaller onefile")
    onefile_executable, onefile_pyz_toc = pyinstaller_build("onefile")
    onefile_report = verify_executable(
        onefile_executable,
        kind="onefile",
        label="build-onefile",
        expected_name="小融.exe",
    )
    write_report(REPORTS_DIR / "xiaorong_onefile_verification_1_1_0.json", onefile_report)
    if not onefile_report["passed"]:
        raise RuntimeError("onefile 本地验证失败。")
    clean_onefile_report = verify_clean_onefile(onefile_executable)
    write_report(REPORTS_DIR / "xiaorong_onefile_clean_path_1_1_0.json", clean_onefile_report)
    if not clean_onefile_report["passed"]:
        raise RuntimeError("onefile 清洁中文路径验证失败。")
    double_launch = verify_double_launch(onefile_executable)
    if not double_launch["passed"]:
        raise RuntimeError("双启动行为验证未能正常结束。")

    announce("生成临时发布目录、说明和校验和")
    staging = BUILD_ROOT / "release_staging"
    staging.mkdir(parents=True, exist_ok=False)
    staged_executable = staging / FINAL_EXECUTABLE_NAME
    shutil.copy2(onefile_executable, staged_executable)
    guide = staging / GUIDE_NAME
    guide.write_text(GUIDE_TEXT, encoding="utf-8", newline="\n")
    generate_checksums(
        [staged_executable, guide],
        staging / CHECKSUM_NAME,
        relative_to=staging,
    )
    staging_audit = audit_release(staging, analysis_toc=onefile_pyz_toc)
    if not staging_audit["passed"]:
        raise RuntimeError(f"临时发布内容审计失败：{staging_audit}")

    if RELEASE_DIR.exists() and any(RELEASE_DIR.iterdir()):
        raise FileExistsError(f"release 目录非空，为避免覆盖现有发布物而停止：{RELEASE_DIR}")
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for path in staging.iterdir():
        shutil.copy2(path, RELEASE_DIR / path.name)

    announce("验证最终中文文件名发布物")
    final_executable = RELEASE_DIR / FINAL_EXECUTABLE_NAME
    final_report = verify_executable(
        final_executable,
        kind="onefile",
        label="final-release",
        expected_name=FINAL_EXECUTABLE_NAME,
    )
    write_report(REPORTS_DIR / "xiaorong_final_release_verification_1_1_0.json", final_report)
    if not final_report["passed"]:
        raise RuntimeError("最终发布 EXE 验证失败。")
    final_audit = audit_release(RELEASE_DIR, analysis_toc=onefile_pyz_toc)
    write_report(REPORTS_DIR / "release_contents_audit_1_1_0.json", final_audit)
    if not final_audit["passed"]:
        raise RuntimeError("最终 release 目录审计失败。")

    protected_after = inspect_protected_inputs()
    if protected_after != protected_before:
        raise RuntimeError("正式主图、对白或指定 ICO 在构建期间发生变化。")

    artifacts = {
        path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(RELEASE_DIR.iterdir())
        if path.is_file()
    }
    report = {
        "passed": True,
        "product": "小融",
        "version": __version__,
        "platform": "Windows x64",
        "layout": "PyInstaller onefile",
        "build_started_utc": build_started,
        "build_finished_utc": timestamp(),
        "build_duration_seconds": round(time.perf_counter() - started, 3),
        "versions": versions,
        "protected_inputs_before": protected_before,
        "protected_inputs_after": protected_after,
        "runtime_resource_manifest": runtime_manifest,
        "environment_check_output": environment_output,
        "pytest_passed": pytest_passed,
        "ruff_passed": "All checks passed" in ruff_output,
        "runtime_import_audit": import_audit,
        "source_smoke": source_smoke,
        "onedir": onedir_report,
        "onedir_clean_path": clean_onedir_report,
        "onefile": onefile_report,
        "onefile_clean_path": clean_onefile_report,
        "final_release": final_report,
        "double_launch": double_launch,
        "release_contents_audit": final_audit,
        "release_artifacts": artifacts,
        "windows_sandbox_tested": False,
        "digital_signature": False,
        "git_commit_created": False,
        "release_uploaded": False,
    }
    report_path = REPORTS_DIR / "release_build_1.1.0.json"
    write_report(report_path, report)
    announce(f"小融 1.1.0 发布构建与验证完成：{final_executable}")
    announce(f"构建报告：{report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"小融 1.1.0 构建失败（{type(error).__name__}）：{error}", file=sys.stderr, flush=True)
        raise SystemExit(1) from error
