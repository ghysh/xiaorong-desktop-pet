"""Cached three-size switching, feet anchoring, clipping, and state preservation."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet.app import create_application
from desktop_pet.behavior.state import PetState
from desktop_pet.settings.model import PetSize
from desktop_pet.ui.pet_window import PetWindow


def test_all_sizes_use_cached_source_keep_feet_and_do_not_reset_state(monkeypatch) -> None:
    application = create_application(["pytest-size-switch"])
    window = PetWindow()
    window.move(300, 200)
    window.show()
    application.processEvents()
    source_key = window._source_pixmap.cacheKey()
    state = window.behavior_controller.current_state
    assert state is PetState.STARTING

    monkeypatch.setattr(
        "desktop_pet.ui.pet_window.load_runtime_asset",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("disk reload")),
    )
    for size in (PetSize.SMALL, PetSize.LARGE, PetSize.DEFAULT):
        old_feet = window.mapToGlobal(window.animation_anchor.toPoint())
        window.set_pet_size(size)
        new_feet = window.mapToGlobal(window.animation_anchor.toPoint())
        assert window.size().toTuple() == size.value
        assert abs(old_feet.x() - new_feet.x()) <= 1
        assert abs(old_feet.y() - new_feet.y()) <= 1
        assert all(window.clipping_checks().values())
        assert window.behavior_controller.current_state is state
        assert window._source_pixmap.cacheKey() == source_key
    window.close()
