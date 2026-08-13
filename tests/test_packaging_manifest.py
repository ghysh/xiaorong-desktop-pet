"""Windows privilege, DPI, and version-resource declaration tests."""

from __future__ import annotations

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.version import __version__


def test_windows_manifest_is_non_elevated_and_high_dpi_aware() -> None:
    text = (PROJECT_ROOT / "packaging/windows/xiaorong.manifest").read_text(encoding="utf-8")
    assert 'requestedExecutionLevel level="asInvoker" uiAccess="false"' in text
    assert "PerMonitorV2" in text
    assert "longPathAware" in text
    assert "8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a" in text
    assert "requireAdministrator" not in text


def test_windows_version_info_matches_release_without_fake_identity() -> None:
    text = (PROJECT_ROOT / "packaging/windows/version_info_1_2_0.txt").read_text(encoding="utf-8")
    assert f"FileVersion', u'{__version__}.0'" in text
    assert f"ProductVersion', u'{__version__}.0'" in text
    for value in ("小融桌宠", "小融", "小融.exe"):
        assert value in text
    for forbidden in ("CompanyName", "LegalCopyright", "LegalTrademarks"):
        assert forbidden not in text
