"""Bounded, local-only crash report tests."""

from __future__ import annotations

from pathlib import Path

from desktop_pet.error_reporting import MAX_CRASH_LOGS, write_crash_report


def test_crash_report_contains_required_runtime_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DESKTOP_PET_TEST_SECRET", "must-not-be-logged")
    error = RuntimeError("controlled failure")
    report_path = write_crash_report(
        RuntimeError,
        error,
        None,
        resource_status="asset verified",
        log_directory=tmp_path,
    )
    report = report_path.read_text(encoding="utf-8")
    for field in (
        "小融版本：",
        "Time UTC:",
        "Python:",
        "Frozen:",
        "Windows:",
        "Resource status: asset verified",
        "Exception type: RuntimeError",
        "Exception message: controlled failure",
        "Traceback:",
    ):
        assert field in report
    assert "DESKTOP_PET_TEST_SECRET" not in report
    assert "must-not-be-logged" not in report


def test_crash_reports_are_bounded_to_ten(tmp_path: Path) -> None:
    for index in range(MAX_CRASH_LOGS + 3):
        write_crash_report(ValueError, ValueError(f"failure-{index}"), None, log_directory=tmp_path)
    assert len(list(tmp_path.glob("crash_*.log"))) == MAX_CRASH_LOGS
