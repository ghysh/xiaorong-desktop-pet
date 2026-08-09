"""Single-source release-version and Qt metadata checks."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop_pet import VERSION_TUPLE, WINDOWS_FILE_VERSION, __version__
from desktop_pet.app import APPLICATION_NAME, ORGANIZATION_NAME, create_application
from desktop_pet.config import WINDOW_TITLE


def test_version_has_one_canonical_value() -> None:
    assert __version__ == "1.1.0"
    assert VERSION_TUPLE == (1, 1, 0)
    assert WINDOWS_FILE_VERSION == (1, 1, 0, 0)


def test_qapplication_uses_release_metadata() -> None:
    application = create_application(["pytest-version"])
    assert application.applicationName() == APPLICATION_NAME == "小融"
    assert application.applicationDisplayName() == WINDOW_TITLE == "小融"
    assert application.applicationVersion() == __version__
    assert application.organizationName() == ORGANIZATION_NAME == "DesktopPetProject"
    assert application.organizationDomain() == ""
    assert not application.windowIcon().isNull()
