"""Validated in-memory QImage/QPixmap cache for runtime-ready action frames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap

from desktop_pet.actions.model import APPROVED_CANVAS_SIZE, ActionClip, ActionFrame


@dataclass(frozen=True, slots=True)
class CachedActionFrame:
    action_id: str
    asset_path: str
    resolved_path: Path
    source_image: QImage
    alpha_bounds: tuple[int, int, int, int]
    file_size_bytes: int


class ActionAssetCache:
    """Load each approved source PNG once and derive size pixmaps only on demand."""

    def __init__(self, actions_root: Path | str) -> None:
        self._actions_root = Path(actions_root).resolve()
        self._sources: dict[tuple[str, str], CachedActionFrame] = {}
        self._pixmaps: dict[tuple[str, str, int, int], QPixmap] = {}
        self._registered_actions: set[str] = set()
        self._source_load_count = 0
        self._scale_count = 0

    @property
    def source_load_count(self) -> int:
        return self._source_load_count

    @property
    def scale_count(self) -> int:
        return self._scale_count

    @property
    def source_memory_estimate_bytes(self) -> int:
        return len(self._sources) * APPROVED_CANVAS_SIZE[0] * APPROVED_CANVAS_SIZE[1] * 4

    @property
    def scaled_memory_estimate_bytes(self) -> int:
        return sum(width * height * 4 for _action, _path, width, height in self._pixmaps)

    def register_action(self, clip: ActionClip, action_directory: Path | str) -> None:
        if clip.action_id in self._registered_actions:
            raise ValueError(f"Action assets are already cached: {clip.action_id}")
        directory = Path(action_directory).resolve()
        if not directory.is_relative_to(self._actions_root):
            raise ValueError("Action directory must remain inside the actions asset root.")
        unique_frames = {frame.asset_path: frame for frame in clip.frames}
        loaded_keys: list[tuple[str, str]] = []
        try:
            for frame in unique_frames.values():
                record = self._load_frame(clip.action_id, frame, directory)
                key = (clip.action_id, frame.asset_path)
                self._sources[key] = record
                loaded_keys.append(key)
        except Exception:
            for key in loaded_keys:
                self._sources.pop(key, None)
            raise
        self._registered_actions.add(clip.action_id)

    def source_record(self, action_id: str, asset_path: str) -> CachedActionFrame:
        try:
            return self._sources[(action_id, asset_path)]
        except KeyError as error:
            raise KeyError(f"Action frame is not cached: {action_id}/{asset_path}") from error

    def pixmap(self, action_id: str, asset_path: str, display_size: QSize | tuple[int, int]) -> QPixmap:
        size = QSize(*display_size) if isinstance(display_size, tuple) else QSize(display_size)
        if size.width() <= 0 or size.height() <= 0:
            raise ValueError("Action display size must be positive.")
        key = (action_id, asset_path, size.width(), size.height())
        cached = self._pixmaps.get(key)
        if cached is not None:
            return QPixmap(cached)
        record = self.source_record(action_id, asset_path)
        pixmap = QPixmap.fromImage(record.source_image).scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if pixmap.isNull() or pixmap.size() != size:
            raise ValueError(f"Action frame could not be scaled to {size.width()}x{size.height()}.")
        self._pixmaps[key] = pixmap
        self._scale_count += 1
        return QPixmap(pixmap)

    def clear_action(self, action_id: str) -> None:
        self._sources = {key: value for key, value in self._sources.items() if key[0] != action_id}
        self._pixmaps = {key: value for key, value in self._pixmaps.items() if key[0] != action_id}
        self._registered_actions.discard(action_id)

    def clear_all(self) -> None:
        self._sources.clear()
        self._pixmaps.clear()
        self._registered_actions.clear()

    def _load_frame(self, action_id: str, frame: ActionFrame, action_directory: Path) -> CachedActionFrame:
        resolved = (action_directory / Path(frame.asset_path)).resolve()
        frames_root = (action_directory / "frames").resolve()
        if not resolved.is_relative_to(frames_root):
            raise ValueError("Runtime action frames must resolve inside the action frames directory.")
        if not resolved.is_file():
            raise FileNotFoundError(f"Action frame is missing: {resolved}")
        try:
            with Image.open(resolved) as image:
                image.verify()
            with Image.open(resolved) as image:
                if image.format != "PNG" or image.size != APPROVED_CANVAS_SIZE or image.mode != "RGBA":
                    raise ValueError(f"Action frame must be a 1024x1536 RGBA PNG: {resolved}")
                alpha_bounds = image.getchannel("A").getbbox()
        except OSError as error:
            raise ValueError(f"Action frame cannot be decoded: {resolved}; {error}") from error
        if alpha_bounds is None:
            raise ValueError(f"Action frame cannot be fully transparent: {resolved}")
        source_image = QImage(str(resolved))
        if source_image.isNull() or source_image.size().toTuple() != APPROVED_CANVAS_SIZE:
            raise ValueError(f"QImage could not load the action frame: {resolved}")
        if not source_image.hasAlphaChannel():
            raise ValueError(f"Action frame QImage must retain Alpha: {resolved}")
        self._source_load_count += 1
        return CachedActionFrame(
            action_id=action_id,
            asset_path=frame.asset_path,
            resolved_path=resolved,
            source_image=source_image,
            alpha_bounds=alpha_bounds,
            file_size_bytes=resolved.stat().st_size,
        )
