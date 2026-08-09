"""Optional system-tray integration that degrades safely when unavailable."""

from __future__ import annotations

import sys
import warnings
from collections.abc import Callable

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSystemTrayIcon

from desktop_pet.ui.action_registry import ActionRegistry
from desktop_pet.ui.pet_window import PetWindow

_TRAY_WARNING_EMITTED = False


class TrayController(QObject):
    """Own at most one tray icon and reuse the application ActionRegistry."""

    def __init__(
        self,
        window: PetWindow,
        action_registry: ActionRegistry,
        *,
        restore_callback: Callable[[], None],
        enabled: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._action_registry = action_registry
        self._restore_callback = restore_callback
        self._tray_icon: QSystemTrayIcon | None = None
        self._menu = None
        self._icon_creation_count = 0
        if not enabled:
            self._available = False
            return
        self._available = QSystemTrayIcon.isSystemTrayAvailable()
        if not self._available:
            global _TRAY_WARNING_EMITTED
            message = "System tray is unavailable; the desktop pet will continue with its window menu."
            if not _TRAY_WARNING_EMITTED:
                warnings.warn(message, RuntimeWarning, stacklevel=2)
                print(f"小融警告：{message}", file=sys.stderr)
                _TRAY_WARNING_EMITTED = True
            return

        self._tray_icon = QSystemTrayIcon(_create_cached_character_icon(window), self)
        self._icon_creation_count = 1
        self._tray_icon.setToolTip("小融")
        self._menu = action_registry.create_menu(window, tray_menu=True)
        self._tray_icon.setContextMenu(self._menu)
        self._tray_icon.activated.connect(self._on_activated)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def tray_icon(self) -> QSystemTrayIcon | None:
        return self._tray_icon

    @property
    def icon_creation_count(self) -> int:
        return self._icon_creation_count

    def show(self) -> None:
        if self._tray_icon is not None:
            self._tray_icon.show()

    def shutdown(self) -> None:
        if self._tray_icon is not None:
            self._tray_icon.hide()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_callback()


def _create_cached_character_icon(window: PetWindow) -> QIcon:
    """Crop cached alpha bounds into a square transparent in-memory icon canvas."""
    left, top, right, bottom = window.source_alpha_bounds
    cropped = window.source_pixmap.copy(QRect(left, top, right - left, bottom - top))
    side = max(cropped.width(), cropped.height())
    canvas = QPixmap(side, side)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap((side - cropped.width()) // 2, (side - cropped.height()) // 2, cropped)
    painter.end()
    return QIcon(canvas)
