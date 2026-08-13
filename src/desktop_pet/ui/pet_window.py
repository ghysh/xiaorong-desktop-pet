"""Transparent pet window integrating Stage 8 state orchestration with paint-only motion."""

from __future__ import annotations

import hashlib
from itertools import product
from math import hypot
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QHideEvent,
    QImage,
    QMouseEvent,
    QMoveEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from desktop_pet.actions.cache import ActionAssetCache
from desktop_pet.actions.model import ActionCategory
from desktop_pet.actions.playback import PlaybackFrame
from desktop_pet.actions.registry import ActionRuntimeRegistry
from desktop_pet.actions.sleep import SleepBubbleState
from desktop_pet.actions.validation import load_runtime_registry
from desktop_pet.animation.controller import AnimationController
from desktop_pet.animation.transform import AnimationTransform, transformed_bounds
from desktop_pet.behavior.controller import BehaviorController
from desktop_pet.config import MIN_VISIBLE_HEIGHT, MIN_VISIBLE_WIDTH, WINDOW_TITLE, PetWindowConfig
from desktop_pet.interaction.controller import InteractionController
from desktop_pet.interaction.hit_test import is_character_pixel
from desktop_pet.paths import ACTIONS_DIR, FULLBODY_RUNTIME_MASTER
from desktop_pet.settings.model import PetSize
from desktop_pet.ui.geometry import ensure_window_visible

if TYPE_CHECKING:
    from desktop_pet.ui.action_registry import ActionRegistry

EXPECTED_RUNTIME_ASSET_SHA256 = "6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64"
EXPECTED_RUNTIME_ASSET_SIZE = (1024, 1536)
REPLACEMENT_CROSSFADE_EVENTS = frozenset({"sit_down_start", "return_default"})
REPLACEMENT_CROSSFADE_DURATION_MS = 140.0


class PetAssetError(RuntimeError):
    """Raised when the approved full-body runtime asset cannot safely be used."""


def runtime_asset_sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying the asset."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def runtime_asset_alpha_bounds(asset_path: Path = FULLBODY_RUNTIME_MASTER) -> tuple[int, int, int, int]:
    """Read the actual Pillow alpha bounding box without modifying the approved PNG."""
    try:
        with Image.open(asset_path) as image:
            if image.mode != "RGBA":
                raise PetAssetError(f"Runtime asset must be RGBA: {asset_path.resolve()}")
            alpha_bounds = image.getchannel("A").getbbox()
    except OSError as error:
        raise PetAssetError(f"Runtime asset alpha channel cannot be read: {asset_path.resolve()}; {error}") from error
    if alpha_bounds is None:
        raise PetAssetError(f"Runtime asset alpha channel is fully transparent: {asset_path.resolve()}")
    return alpha_bounds


def load_runtime_asset(asset_path: Path = FULLBODY_RUNTIME_MASTER) -> QImage:
    """Validate and load only the approved Stage 5 full-body PNG as a QImage."""
    resolved_path = asset_path.resolve()
    if not resolved_path.is_file():
        raise PetAssetError(f"Runtime asset is missing: {resolved_path}")
    if resolved_path.suffix.lower() != ".png":
        raise PetAssetError(f"Runtime asset must be a PNG: {resolved_path}")

    actual_hash = runtime_asset_sha256(resolved_path)
    if actual_hash != EXPECTED_RUNTIME_ASSET_SHA256:
        raise PetAssetError(
            "Runtime asset SHA-256 mismatch. "
            f"Path: {resolved_path}; actual: {actual_hash}; expected: {EXPECTED_RUNTIME_ASSET_SHA256}."
        )

    try:
        with Image.open(resolved_path) as image:
            image.verify()
        with Image.open(resolved_path) as image:
            if image.format != "PNG":
                raise PetAssetError(f"Runtime asset format must be PNG: {resolved_path}")
            if image.size != EXPECTED_RUNTIME_ASSET_SIZE:
                raise PetAssetError(
                    "Runtime asset dimensions are invalid. "
                    f"Path: {resolved_path}; actual: {image.size}; expected: {EXPECTED_RUNTIME_ASSET_SIZE}."
                )
            if image.mode != "RGBA":
                raise PetAssetError(
                    f"Runtime asset must be RGBA. Path: {resolved_path}; actual mode: {image.mode}."
                )
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            if alpha_bounds is None:
                raise PetAssetError(f"Runtime asset alpha channel is fully transparent: {resolved_path}")
            if alpha.getextrema() == (255, 255):
                raise PetAssetError(f"Runtime asset alpha channel is fully opaque: {resolved_path}")
            left, top, right, bottom = alpha_bounds
            if left <= 0 or top <= 0 or right >= image.width or bottom >= image.height:
                raise PetAssetError(
                    "Runtime asset alpha bounds must remain inside the canvas. "
                    f"Path: {resolved_path}; bounds: {alpha_bounds}."
                )
    except OSError as error:
        raise PetAssetError(f"Runtime asset cannot be decoded: {resolved_path}; {error}") from error

    qimage = QImage(str(resolved_path))
    if qimage.isNull():
        raise PetAssetError(f"QImage failed to load runtime asset: {resolved_path}")
    if qimage.size().toTuple() != EXPECTED_RUNTIME_ASSET_SIZE:
        raise PetAssetError(
            "QImage dimensions do not match the approved asset. "
            f"Path: {resolved_path}; actual: {qimage.size().toTuple()}; expected: {EXPECTED_RUNTIME_ASSET_SIZE}."
        )
    if not qimage.hasAlphaChannel():
        raise PetAssetError(f"QImage has no alpha channel: {resolved_path}")
    return qimage


class PetWindow(QWidget):
    """A fixed-size transparent pet window whose motion is confined to QPainter transforms."""

    position_commit_requested = Signal(object)
    close_requested = Signal()
    geometry_changed = Signal()
    window_hidden = Signal()
    window_shown = Signal()

    def __init__(self, config: PetWindowConfig | None = None) -> None:
        if QApplication.instance() is None:
            raise PetAssetError("PetWindow requires an active QApplication before QPixmap creation.")
        super().__init__()
        self.config = config or PetWindowConfig()
        self.asset_path = FULLBODY_RUNTIME_MASTER
        self._drag_offset: QPoint | None = None
        self._press_global_position: QPoint | None = None
        self._press_local_position: QPointF | None = None
        self._press_hit_character = False
        self._press_timer = QElapsedTimer()
        self._drag_started = False
        self._context_menu_open = False
        self._suppress_lifecycle_events = False
        self._action_registry: ActionRegistry | None = None
        self._paint_count = 0
        self._runtime_asset_load_count = 1
        self._current_overlay_frame: PlaybackFrame | None = None
        self._current_overlay_pixmap: QPixmap | None = None
        self._current_overlay_replaces_base = False
        self._previous_replacement_pixmap: QPixmap | None = None
        self._sleep_bubble_state = SleepBubbleState.hidden()

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(WINDOW_TITLE)
        self.setFixedSize(self.config.width, self.config.height)

        self._source_image = load_runtime_asset(self.asset_path)
        self._source_pixmap = QPixmap.fromImage(self._source_image)
        if self._source_pixmap.isNull():
            raise PetAssetError(f"QPixmap conversion failed: {self.asset_path}")
        self._scaled_pixmap = self._source_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self._scaled_pixmap.isNull() or self._scaled_pixmap.size() != self.size():
            raise PetAssetError("Runtime asset could not be scaled to the approved 280x420 window size.")

        self._source_alpha_bounds = runtime_asset_alpha_bounds(self.asset_path)
        self._alpha_bounds_window = self._project_alpha_bounds_to_window(self._source_alpha_bounds)
        self._animation_anchor = QPointF(
            self._alpha_bounds_window.center().x(),
            self._alpha_bounds_window.bottom(),
        )
        self._effective_drag_tilt_max_degrees = self._calculate_safe_drag_tilt_limit()
        self._action_asset_cache = ActionAssetCache(ACTIONS_DIR)
        self._runtime_action_registry = load_runtime_registry(ACTIONS_DIR, self._action_asset_cache)
        self._animation_controller = AnimationController(
            self.config.animation,
            behavior_config=self.config.behavior,
            blink_config=self.config.blink,
            drowsy_sleep_config=self.config.drowsy_sleep,
            action_registry=self._runtime_action_registry,
            effective_drag_tilt_max_degrees=self._effective_drag_tilt_max_degrees,
            parent=self,
        )
        self._current_transform = AnimationTransform.identity()
        self._animation_controller.transform_changed.connect(self._on_transform_changed)
        self._animation_controller.overlay_frame_changed.connect(self._on_overlay_frame_changed)
        self._animation_controller.sleep_bubble_changed.connect(self._on_sleep_bubble_changed)

    @property
    def animation_controller(self) -> AnimationController:
        """Return the window-owned controller; it only changes internal draw transforms."""
        return self._animation_controller

    @property
    def behavior_controller(self) -> BehaviorController:
        """Return the timer-free state controller driven by the animation controller's tick."""
        return self._animation_controller.behavior_controller

    @property
    def interaction_controller(self) -> InteractionController:
        """Return the timer-free click controller driven by the sole animation timer."""
        return self._animation_controller.interaction_controller

    @property
    def action_asset_cache(self) -> ActionAssetCache:
        return self._action_asset_cache

    @property
    def runtime_action_registry(self) -> ActionRuntimeRegistry:
        return self._runtime_action_registry

    @property
    def current_overlay_frame(self) -> PlaybackFrame | None:
        return self._current_overlay_frame

    @property
    def animation_anchor(self) -> QPointF:
        """Return the calculated feet-near alpha-bound bottom-centre pivot in window pixels."""
        return QPointF(self._animation_anchor)

    @property
    def alpha_bounds_window(self) -> QRectF:
        """Return the actual image alpha bounding rectangle projected into the fixed window."""
        return QRectF(self._alpha_bounds_window)

    @property
    def effective_drag_tilt_max_degrees(self) -> float:
        """Return the clipping-safe drag rotation limit used at runtime."""
        return self._effective_drag_tilt_max_degrees

    @property
    def pet_size(self) -> PetSize:
        return PetSize.from_dimensions(self.width(), self.height())

    @property
    def source_pixmap(self) -> QPixmap:
        """Return the already-cached source pixmap without disk access."""
        return QPixmap(self._source_pixmap)

    @property
    def source_alpha_bounds(self) -> tuple[int, int, int, int]:
        return self._source_alpha_bounds

    @property
    def paint_count(self) -> int:
        return self._paint_count

    @property
    def runtime_asset_load_count(self) -> int:
        return self._runtime_asset_load_count

    def transformed_alpha_bounds(self, transform: AnimationTransform) -> QRectF:
        """Calculate transformed bounds for diagnostics and clipping checks, never per paint frame."""
        return transformed_bounds(self._alpha_bounds_window, self._animation_anchor, transform)

    def is_transform_safe(self, transform: AnimationTransform) -> bool:
        """Check that an alpha-bound transform remains inside the unchanged 280 by 420 canvas."""
        bounds = self.transformed_alpha_bounds(transform)
        epsilon = 0.001
        return (
            bounds.left() >= -epsilon
            and bounds.top() >= -epsilon
            and bounds.right() <= self.width() + epsilon
            and bounds.bottom() <= self.height() + epsilon
        )

    def clipping_checks(self) -> dict[str, bool]:
        """Report conservative extrema used to choose the drag limit during initialization."""
        animation = self.config.animation
        transforms = {
            "maximum_breathing": AnimationTransform(
                scale_x=1.0 + animation.breathing_scale_x,
                scale_y=1.002 + animation.breathing_scale_y,
            ),
            "maximum_float": AnimationTransform(offset_y=-animation.floating_amplitude_pixels),
            "maximum_idle_sway": AnimationTransform(
                rotation_degrees=animation.sway_amplitude_degrees * self.config.behavior.sway_rotation_multiplier
            ),
            "maximum_drag_tilt": AnimationTransform(rotation_degrees=self._effective_drag_tilt_max_degrees),
            "extreme_combined": AnimationTransform(
                offset_y=-animation.floating_amplitude_pixels,
                scale_x=1.0 + animation.breathing_scale_x,
                scale_y=1.002 + animation.breathing_scale_y,
                rotation_degrees=(
                    animation.sway_amplitude_degrees * self.config.behavior.sway_rotation_multiplier
                    + self._effective_drag_tilt_max_degrees
                ),
            ),
        }
        return {name: self.is_transform_safe(transform) for name, transform in transforms.items()}

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the cached character and independent effects under one safe transform."""
        del event
        self._paint_count += 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.save()
        self._current_transform.apply_to_painter(painter, self._animation_anchor)
        self._paint_character_layer(painter)
        self._paint_sleep_bubble(painter)
        painter.restore()

    def showEvent(self, event: QShowEvent) -> None:
        """Start the sole animation timer only after the transparent window becomes visible."""
        super().showEvent(event)
        if not self._suppress_lifecycle_events:
            self._animation_controller.start()
            self.window_shown.emit()

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop periodic animation work while this window is hidden."""
        if not self._suppress_lifecycle_events:
            self._animation_controller.pause()
            self.window_hidden.emit()
        super().hideEvent(event)

    def moveEvent(self, event: QMoveEvent) -> None:
        """Notify low-frequency companions after an explicit window position change."""
        super().moveEvent(event)
        self.geometry_changed.emit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Notify low-frequency companions after one of the three size changes."""
        super().resizeEvent(event)
        self.geometry_changed.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ensure no animation timer continues after the window is closed."""
        self.close_requested.emit()
        self._animation_controller.shutdown()
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record a potential click; actual QWidget dragging starts at the system threshold."""
        if event.button() == Qt.MouseButton.LeftButton:
            global_position = event.globalPosition().toPoint()
            self._drag_offset = global_position - self.frameGeometry().topLeft()
            self._press_global_position = QPoint(global_position)
            self._press_local_position = QPointF(event.position())
            self._press_hit_character = is_character_pixel(event.position(), self.size(), self._source_image)
            self._press_timer.start()
            self._drag_started = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Move the QWidget for an actual drag while only tilting its internal paint content."""
        if (
            self._drag_offset is not None
            and self._press_global_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            global_position = event.globalPosition().toPoint()
            distance = hypot(
                global_position.x() - self._press_global_position.x(),
                global_position.y() - self._press_global_position.y(),
            )
            if not self._drag_started and distance < QApplication.startDragDistance():
                event.accept()
                return
            if not self._drag_started:
                self._drag_started = True
                self._animation_controller.begin_drag(self._press_global_position)
            self.move(global_position - self._drag_offset)
            self._animation_controller.update_drag(global_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Retain the released widget position, correct visibility, then ease only its tilt to zero."""
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            if self._drag_started:
                screen_geometries = [screen.availableGeometry() for screen in QApplication.screens()]
                corrected_position = ensure_window_visible(
                    self.frameGeometry(),
                    screen_geometries,
                    self._minimum_visible_size(),
                )
                self.move(corrected_position)
                self._animation_controller.end_drag()
                self.position_commit_requested.emit(QPoint(self.pos()))
            elif self._press_global_position is not None:
                release_global = event.globalPosition().toPoint()
                movement_distance = hypot(
                    release_global.x() - self._press_global_position.x(),
                    release_global.y() - self._press_global_position.y(),
                )
                held_ms = self._press_timer.elapsed() if self._press_timer.isValid() else 0
                self._animation_controller.try_start_click(
                    elapsed_seconds=self._animation_controller.elapsed_seconds,
                    button=event.button(),
                    press_hit=self._press_hit_character,
                    release_hit=is_character_pixel(event.position(), self.size(), self._source_image),
                    movement_distance=movement_distance,
                    drag_threshold=QApplication.startDragDistance(),
                    held_ms=held_ms,
                    context_menu_open=self._context_menu_open,
                )
            self._clear_pointer_gesture()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Show the retained minimal right-click menu with only an exit action."""
        menu = self.create_context_menu()
        self._context_menu_open = True
        try:
            menu.exec(event.globalPos())
        finally:
            self._context_menu_open = False
            menu.deleteLater()

    def create_context_menu(self) -> QMenu:
        """Build the shared Stage 9 menu, retaining a safe exit fallback during isolated tests."""
        if self._action_registry is not None:
            return self._action_registry.create_menu(self)
        menu = QMenu(self)
        exit_action = QAction("退出桌宠", menu)
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(exit_action)
        return menu

    def set_action_registry(self, registry: ActionRegistry) -> None:
        """Inject the application-owned shared action set exactly once."""
        if self._action_registry is not None and self._action_registry is not registry:
            raise RuntimeError("PetWindow already has a different ActionRegistry.")
        self._action_registry = registry

    def set_pet_size(self, size: PetSize, *, keep_feet_global: bool = True) -> None:
        """Resize from the cached source while preserving the global feet centre where possible."""
        if not isinstance(size, PetSize):
            raise ValueError("Pet window size must be a defined PetSize.")
        if self.size().toTuple() == size.value:
            return
        old_anchor_global = self.mapToGlobal(self._animation_anchor.toPoint())
        self.setFixedSize(size.width, size.height)
        self._rebuild_scaled_cache()
        if keep_feet_global:
            self.move(old_anchor_global - self._animation_anchor.toPoint())
        screens = [screen.availableGeometry() for screen in QApplication.screens()]
        if screens:
            corrected = ensure_window_visible(
                QRect(self.pos(), self.size()),
                screens,
                self._minimum_visible_size(),
            )
            self.move(corrected)
        if not all(self.clipping_checks().values()):
            raise PetAssetError(f"Cached runtime asset is not clipping-safe at {size.width}x{size.height}.")
        self.update()

    def set_always_on_top(self, enabled: bool) -> None:
        """Change only the topmost flag while retaining position, visibility, and controllers."""
        if not isinstance(enabled, bool):
            raise ValueError("Always-on-top state must be boolean.")
        desired = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if desired is enabled:
            return
        position = self.pos()
        was_visible = self.isVisible()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self._suppress_lifecycle_events = True
        try:
            self.setWindowFlags(flags)
            self.move(position)
            if was_visible:
                self.show()
                self.raise_()
        finally:
            self._suppress_lifecycle_events = False

    def set_animation_enabled(self, enabled: bool) -> None:
        self._animation_controller.set_animation_enabled(enabled)
        if enabled and self.isVisible():
            self._animation_controller.start()

    def set_behavior_enabled(self, enabled: bool) -> None:
        self._animation_controller.set_behavior_enabled(enabled)

    def set_drowsy_sleep_enabled(self, enabled: bool) -> None:
        self._animation_controller.set_drowsy_sleep_enabled(enabled)

    def set_click_reaction_enabled(self, enabled: bool) -> None:
        self._animation_controller.set_click_reaction_enabled(enabled)

    def _on_transform_changed(self, transform: AnimationTransform) -> None:
        """Store a transform and request repaint; no image, size, or desktop position changes occur."""
        self._current_transform = transform
        self.update()

    def _on_overlay_frame_changed(self, playback_frame: PlaybackFrame | None) -> None:
        """Swap a cached keyframe, retaining a fade source only at approved clip boundaries."""
        previous_frame = self._current_overlay_frame
        previous_pixmap = self._current_overlay_pixmap
        previous_replaced_base = self._current_overlay_replaces_base
        self._current_overlay_frame = playback_frame
        if playback_frame is None:
            self._current_overlay_pixmap = None
            self._current_overlay_replaces_base = False
            self._previous_replacement_pixmap = None
        else:
            clip = self._animation_controller.action_player.current_clip
            if clip is None:
                raise RuntimeError("An overlay frame changed without an active ActionClip.")
            self._current_overlay_pixmap = self._action_asset_cache.pixmap(
                clip.action_id,
                playback_frame.frame.asset_path,
                self.size(),
            )
            self._current_overlay_replaces_base = clip.category in {
                ActionCategory.FRAME_SEQUENCE,
                ActionCategory.USER_SELECTED,
            }
            changed_asset = (
                previous_frame is None
                or previous_frame.frame.asset_path != playback_frame.frame.asset_path
            )
            crossfade_allowed = playback_frame.frame.event in REPLACEMENT_CROSSFADE_EVENTS
            if self._current_overlay_replaces_base and changed_asset and crossfade_allowed:
                self._previous_replacement_pixmap = (
                    previous_pixmap if previous_replaced_base and previous_pixmap is not None else self._scaled_pixmap
                )
            else:
                self._previous_replacement_pixmap = None
        self.update()

    def _on_sleep_bubble_changed(self, state: SleepBubbleState) -> None:
        """Update only the independent nasal-bubble render state."""
        self._sleep_bubble_state = state
        self.update()

    def _paint_character_layer(self, painter: QPainter) -> None:
        if self._current_overlay_pixmap is not None and self._current_overlay_replaces_base:
            frame_elapsed = self._animation_controller.action_player.current_frame_elapsed_ms
            blend = min(1.0, frame_elapsed / REPLACEMENT_CROSSFADE_DURATION_MS)
            if self._previous_replacement_pixmap is not None and blend < 1.0:
                painter.setOpacity(1.0 - blend)
                painter.drawPixmap(0, 0, self._previous_replacement_pixmap)
            painter.setOpacity(blend if self._previous_replacement_pixmap is not None else 1.0)
            painter.drawPixmap(0, 0, self._current_overlay_pixmap)
            painter.setOpacity(1.0)
            return
        painter.drawPixmap(0, 0, self._scaled_pixmap)
        if self._current_overlay_pixmap is not None:
            painter.drawPixmap(0, 0, self._current_overlay_pixmap)

    def _paint_sleep_bubble(self, painter: QPainter) -> None:
        state = self._sleep_bubble_state
        if not state.visible:
            return
        width = max(9.0, self.width() * 0.036)
        height = width * 0.82
        nose_anchor = QPointF(state.anchor_x * self.width(), state.anchor_y * self.height())
        path = QPainterPath()
        path.moveTo(-0.60 * width, 0.10 * height)
        path.cubicTo(-0.78 * width, 0.13 * height, -0.84 * width, 0.04 * height, -0.91 * width, 0.0)
        path.cubicTo(-0.75 * width, -0.06 * height, -0.67 * width, -0.34 * height, -0.42 * width, -0.46 * height)
        path.cubicTo(-0.08 * width, -0.64 * height, 0.44 * width, -0.48 * height, 0.59 * width, -0.12 * height)
        path.cubicTo(0.76 * width, 0.28 * height, 0.45 * width, 0.58 * height, 0.04 * width, 0.60 * height)
        path.cubicTo(-0.27 * width, 0.62 * height, -0.52 * width, 0.43 * height, -0.60 * width, 0.10 * height)
        path.closeSubpath()

        painter.save()
        painter.setOpacity(state.opacity)
        painter.translate(nose_anchor)
        painter.rotate(state.rotation_degrees)
        painter.translate(2.0 + 0.72 * width, -0.18 * height)
        painter.scale(state.scale, state.scale)
        gradient = QRadialGradient(QPointF(-0.15 * width, -0.22 * height), 0.90 * width)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 235))
        gradient.setColorAt(0.55, QColor(218, 244, 255, 205))
        gradient.setColorAt(1.0, QColor(154, 214, 239, 165))
        pen = QPen(QColor(118, 183, 213, 205))
        pen.setWidthF(max(0.8, self.width() / 280.0))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(gradient)
        painter.drawPath(path)
        painter.restore()

    def _rebuild_scaled_cache(self) -> None:
        """Regenerate size-dependent data from memory without reopening the protected PNG."""
        self._scaled_pixmap = self._source_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self._scaled_pixmap.isNull() or self._scaled_pixmap.size() != self.size():
            raise PetAssetError(
                f"Runtime asset could not be scaled to {self.width()}x{self.height()} from cache."
            )
        self._alpha_bounds_window = self._project_alpha_bounds_to_window(self._source_alpha_bounds)
        self._animation_anchor = QPointF(
            self._alpha_bounds_window.center().x(),
            self._alpha_bounds_window.bottom(),
        )
        self._effective_drag_tilt_max_degrees = self._calculate_safe_drag_tilt_limit()
        if self._current_overlay_frame is not None:
            clip = self._animation_controller.action_player.current_clip
            if clip is None:
                raise RuntimeError("An overlay frame remained without an active ActionClip.")
            self._current_overlay_pixmap = self._action_asset_cache.pixmap(
                clip.action_id,
                self._current_overlay_frame.frame.asset_path,
                self.size(),
            )
        self._previous_replacement_pixmap = None

    def _clear_pointer_gesture(self) -> None:
        self._drag_offset = None
        self._press_global_position = None
        self._press_local_position = None
        self._press_hit_character = False
        self._drag_started = False

    def _project_alpha_bounds_to_window(self, source_bounds: tuple[int, int, int, int]) -> QRectF:
        """Project Pillow's actual source alpha bounds into this fixed logical-pixel canvas."""
        left, top, right, bottom = source_bounds
        scale_x = self.width() / self._source_image.width()
        scale_y = self.height() / self._source_image.height()
        return QRectF(
            left * scale_x,
            top * scale_y,
            (right - left) * scale_x,
            (bottom - top) * scale_y,
        )

    def _calculate_safe_drag_tilt_limit(self) -> float:
        """Lower the configured drag limit only if conservative alpha-bound extrema would clip."""
        animation = self.config.animation
        desired_limit = animation.drag_tilt_max_degrees
        for tenths in range(round(desired_limit * 10), -1, -1):
            candidate = tenths / 10.0
            if all(self.is_transform_safe(transform) for transform in self._extreme_transforms(candidate)):
                return candidate
        return 0.0

    def _extreme_transforms(self, drag_tilt_degrees: float) -> tuple[AnimationTransform, ...]:
        """Enumerate conservative transform sign combinations once during initialization."""
        animation = self.config.animation
        scale_x_values = (1.0 - animation.breathing_scale_x, 1.0 + animation.breathing_scale_x)
        scale_y_values = (1.002 - animation.breathing_scale_y, 1.002 + animation.breathing_scale_y)
        transforms = []
        for float_sign, scale_x, scale_y, rotation_sign in product(
            (-1.0, 1.0),
            scale_x_values,
            scale_y_values,
            (-1.0, 1.0),
        ):
            maximum_behavior_sway = (
                animation.sway_amplitude_degrees * self.config.behavior.sway_rotation_multiplier
            )
            rotation = rotation_sign * (maximum_behavior_sway + drag_tilt_degrees)
            transforms.append(
                AnimationTransform(
                    offset_y=float_sign * animation.floating_amplitude_pixels,
                    scale_x=scale_x,
                    scale_y=scale_y,
                    rotation_degrees=rotation,
                )
            )
        return tuple(transforms)

    @staticmethod
    def _minimum_visible_size() -> QSize:
        """Return the approved visibility safeguard in logical pixels."""
        return QSize(MIN_VISIBLE_WIDTH, MIN_VISIBLE_HEIGHT)
