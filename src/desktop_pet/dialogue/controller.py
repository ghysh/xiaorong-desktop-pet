"""Application-owned click dialogue lifecycle and event-driven positioning."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil, floor
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QGuiApplication, QScreen

from desktop_pet.dialogue.repository import DialogueRepository
from desktop_pet.dialogue.selector import DialogueSelector
from desktop_pet.ui.dialogue_bubble import DialogueBubble

if TYPE_CHECKING:
    from desktop_pet.ui.pet_window import PetWindow


class DialogueController(QObject):
    """Coordinate cached text and the single bubble without changing behavior state."""

    dialogue_shown = Signal(str)
    dialogue_hidden = Signal()

    def __init__(
        self,
        repository: DialogueRepository,
        selector: DialogueSelector | None,
        bubble: DialogueBubble,
        pet_window: PetWindow,
        enabled_provider: Callable[[], bool],
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.selector = selector
        self.bubble = bubble
        self.pet_window = pet_window
        self._enabled_provider = enabled_provider
        self._stopping = False
        self._connected_screen_ids: set[int] = set()

        self.pet_window.geometry_changed.connect(self.reposition)
        self.pet_window.window_hidden.connect(self.hide)
        self.bubble.dialogue_hidden.connect(self.dialogue_hidden)
        application = QGuiApplication.instance()
        if application is not None:
            application.screenAdded.connect(self._connect_screen)
            application.screenRemoved.connect(self._screen_removed)
            for screen in application.screens():
                self._connect_screen(screen)

    @property
    def available(self) -> bool:
        return self.selector is not None

    def show_random_dialogue(self) -> bool:
        """Select only for an enabled effective click and update the existing bubble."""
        if self._stopping or self.selector is None or not self._enabled_provider():
            return False
        if not self.pet_window.isVisible():
            return False
        text = self.selector.choose()
        pet_rect = self._pet_alpha_rect()
        available = self._screen_for_pet(pet_rect).availableGeometry()
        self.bubble.show_dialogue(text, pet_rect, available)
        self.dialogue_shown.emit(text)
        return True

    def reposition(self) -> None:
        if self._stopping or not self.bubble.isVisible():
            return
        pet_rect = self._pet_alpha_rect()
        available = self._screen_for_pet(pet_rect).availableGeometry()
        self.bubble.reposition(pet_rect, available)

    def set_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Dialogue enabled state must be boolean.")
        if not enabled:
            self.hide()

    def set_always_on_top(self, enabled: bool) -> None:
        self.bubble.set_always_on_top(enabled)
        if self.bubble.isVisible():
            self.reposition()

    def hide(self) -> None:
        self.bubble.hide_dialogue()

    def shutdown(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.bubble.shutdown()

    def _pet_alpha_rect(self) -> QRect:
        local = self.pet_window.alpha_bounds_window
        top_left = self.pet_window.mapToGlobal(QPoint(floor(local.left()), floor(local.top())))
        return QRect(top_left, self._positive_size(ceil(local.width()), ceil(local.height())))

    @staticmethod
    def _positive_size(width: int, height: int):
        return QSize(max(1, width), max(1, height))

    @staticmethod
    def _screen_for_pet(pet_rect: QRect) -> QScreen:
        screen = QGuiApplication.screenAt(pet_rect.center())
        screens = QGuiApplication.screens()
        if screen is None and screens:
            def intersection_area(candidate: QScreen) -> int:
                intersection = candidate.availableGeometry().intersected(pet_rect)
                return intersection.width() * intersection.height()

            screen = max(screens, key=intersection_area)
        if screen is None:
            raise RuntimeError("No screen is available for dialogue bubble positioning.")
        return screen

    def _connect_screen(self, screen: QScreen) -> None:
        identity = id(screen)
        if identity in self._connected_screen_ids:
            return
        self._connected_screen_ids.add(identity)
        screen.availableGeometryChanged.connect(self._screen_geometry_changed)
        screen.geometryChanged.connect(self._screen_geometry_changed)

    def _screen_removed(self, screen: QScreen) -> None:
        self._connected_screen_ids.discard(id(screen))
        self.reposition()

    def _screen_geometry_changed(self, _geometry: QRect) -> None:
        self.reposition()
