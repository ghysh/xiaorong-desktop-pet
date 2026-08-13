"""XiaoRong minimal release-contract checks."""

from __future__ import annotations

from scripts.audit_release_contents import EXPECTED_RELEASE_FILES

from desktop_pet.version import __version__


def test_release_contract_is_minimal_and_versioned() -> None:
    assert __version__ == "1.2.0"
    assert EXPECTED_RELEASE_FILES == {"小融-1.2.0-win64.exe"}
