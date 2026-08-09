"""Local-only bounded crash reports and startup error dialogs."""

from __future__ import annotations

import platform
import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from desktop_pet.paths import is_frozen
from desktop_pet.settings.repository import CONFIG_ORGANIZATION_NAME, SETTINGS_DIRECTORY_NAME
from desktop_pet.version import __version__

MAX_CRASH_LOGS = 10


def default_log_directory() -> Path:
    """Resolve the historical local log path independently from the display name."""
    raw = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    if not raw:
        raise OSError("Qt could not resolve the local application data directory.")
    return Path(raw) / CONFIG_ORGANIZATION_NAME / SETTINGS_DIRECTORY_NAME / "logs"


def write_crash_report(
    exception_type: type[BaseException],
    exception: BaseException,
    traceback_object: TracebackType | None,
    *,
    resource_status: str = "not checked",
    log_directory: Path | None = None,
) -> Path:
    """Write one bounded UTF-8 report without environment variables or user-file data."""
    directory = default_log_directory() if log_directory is None else Path(log_directory)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC)
    path = directory / f"crash_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.log"
    formatted_traceback = "".join(traceback.format_exception(exception_type, exception, traceback_object))
    report = (
        f"小融版本：{__version__}\n"
        f"Time UTC: {timestamp.isoformat()}\n"
        f"Python: {platform.python_version()}\n"
        f"Frozen: {is_frozen()}\n"
        f"Windows: {platform.platform()}\n"
        f"Resource status: {resource_status}\n"
        f"Exception type: {exception_type.__name__}\n"
        f"Exception message: {exception}\n"
        "Traceback:\n"
        f"{formatted_traceback}"
    )
    path.write_text(report, encoding="utf-8")
    _trim_old_logs(directory)
    return path


def install_exception_hook(
    *,
    resource_status_provider: Callable[[], str] | None = None,
) -> Callable[[type[BaseException], BaseException, TracebackType | None], None]:
    """Install a main-thread hook that logs and shows a concise local error dialog."""
    def exception_hook(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback_object: TracebackType | None,
    ) -> None:
        status = resource_status_provider() if resource_status_provider is not None else "not checked"
        try:
            log_path = write_crash_report(
                exception_type,
                exception,
                traceback_object,
                resource_status=status,
            )
            detail = f"错误报告已保存到：\n{log_path}"
        except OSError as log_error:
            detail = f"错误报告无法写入：{log_error}"
        if isinstance(QApplication.instance(), QApplication):
            QMessageBox.critical(None, "小融遇到错误", f"程序发生未处理错误。\n\n{detail}")

    sys.excepthook = exception_hook
    return exception_hook


def report_startup_failure(error: BaseException, *, resource_status: str) -> Path | None:
    """Log a startup failure and show a windowed-mode message when Qt is available."""
    try:
        log_path = write_crash_report(
            type(error),
            error,
            error.__traceback__,
            resource_status=resource_status,
        )
        log_detail = f"\n\n错误报告：{log_path}"
    except OSError:
        log_path = None
        log_detail = "\n\n错误报告目录不可写。"
    if isinstance(QApplication.instance(), QApplication):
        QMessageBox.critical(None, "小融启动失败", f"无法启动桌宠：{error}{log_detail}")
    return log_path


def _trim_old_logs(directory: Path) -> None:
    logs = sorted(directory.glob("crash_*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    for obsolete in logs[MAX_CRASH_LOGS:]:
        obsolete.unlink(missing_ok=True)
