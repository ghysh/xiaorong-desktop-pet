"""Explicit release-smoke command-line behavior tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.app import parse_runtime_options, run


def test_release_switches_require_explicit_smoke_mode(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_runtime_options(["--quit-after-ms", "100"])
    with pytest.raises(SystemExit):
        parse_runtime_options(["--release-smoke-test"])
    options = parse_runtime_options(
        [
            "--release-smoke-test",
            "--quit-after-ms",
            "100",
            "--config-dir",
            str(tmp_path / "config"),
            "--no-tray",
            "--smoke-result",
            str(tmp_path / "result.json"),
        ]
    )
    assert options.release_smoke_test and options.no_tray
    assert options.quit_after_ms == 100


def test_source_release_smoke_uses_only_temporary_settings(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    config_dir = tmp_path / "config"
    exit_code = run(
        [
            "--release-smoke-test",
            "--quit-after-ms",
            "100",
            "--config-dir",
            str(config_dir),
            "--no-tray",
            "--smoke-result",
            str(result_path),
        ]
    )
    report = json.loads(result_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["frozen"] is False
    assert report["size_switch_results"] == [[240, 360], [280, 420], [320, 480]]
    assert report["position_saved"] is True
    assert Path(report["settings_path"]).is_relative_to(config_dir)
