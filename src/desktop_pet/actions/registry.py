"""Strict planning and runtime registries with no UI or timer ownership."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from desktop_pet.actions.manifest import ActionManifest
from desktop_pet.actions.model import ActionClip

if TYPE_CHECKING:
    from desktop_pet.actions.cache import ActionAssetCache


class ActionPlanRegistry:
    """Collect unique planned manifests while refusing anything runnable."""

    def __init__(self, manifests: Iterable[ActionManifest] = ()) -> None:
        self._manifests: dict[str, ActionManifest] = {}
        for manifest in manifests:
            self.register(manifest)

    def register(self, manifest: ActionManifest) -> None:
        if not isinstance(manifest, ActionManifest):
            raise ValueError("ActionPlanRegistry accepts only ActionManifest values.")
        if manifest.status != "planned" or manifest.runtime_enabled or manifest.assets_complete:
            raise ValueError("ActionPlanRegistry accepts only disabled, incomplete planned actions.")
        if manifest.action_id in self._manifests:
            raise ValueError(f"Duplicate planned action_id: {manifest.action_id}")
        self._manifests[manifest.action_id] = manifest

    def get(self, action_id: str) -> ActionManifest:
        try:
            return self._manifests[action_id]
        except KeyError as error:
            raise KeyError(f"Unknown planned action_id: {action_id}") from error

    @property
    def action_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._manifests))

    def __len__(self) -> int:
        return len(self._manifests)

    def __iter__(self) -> Iterator[ActionManifest]:
        return iter(self._manifests.values())


@dataclass(frozen=True, slots=True)
class RegisteredAction:
    """A ready clip and the directory against which its frame paths resolve."""

    clip: ActionClip
    action_directory: Path


class ActionRuntimeRegistry:
    """Register only ready, enabled, complete actions whose frames pass cache validation."""

    def __init__(self) -> None:
        self._actions: dict[str, RegisteredAction] = {}

    def register_manifest(
        self,
        manifest: ActionManifest,
        manifest_path: Path | str,
        cache: ActionAssetCache,
    ) -> ActionClip:
        if not isinstance(manifest, ActionManifest):
            raise ValueError("ActionRuntimeRegistry accepts only ActionManifest values.")
        if manifest.status != "ready" or not manifest.runtime_enabled or not manifest.assets_complete:
            raise ValueError("Runtime actions must be ready, enabled, and asset-complete.")
        if manifest.action_id in self._actions:
            raise ValueError(f"Duplicate runtime action_id: {manifest.action_id}")
        path = Path(manifest_path).resolve()
        clip = manifest.to_clip()
        cache.register_action(clip, path.parent)
        self._actions[clip.action_id] = RegisteredAction(clip=clip, action_directory=path.parent)
        return clip

    def get(self, action_id: str) -> ActionClip:
        try:
            return self._actions[action_id].clip
        except KeyError as error:
            raise KeyError(f"Unknown runtime action_id: {action_id}") from error

    @property
    def action_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._actions))

    def __len__(self) -> int:
        return len(self._actions)

    def __iter__(self) -> Iterator[ActionClip]:
        return (registered.clip for registered in self._actions.values())
