"""Release 1.1.0 scripts and runtime-boundary checks."""

from __future__ import annotations

from desktop_pet.actions.validation import BLINK_MANIFEST_RELATIVE_PATH, load_runtime_registry
from desktop_pet.paths import PROJECT_ROOT


def test_runtime_registry_loader_does_not_read_planned_manifests() -> None:
    source = (PROJECT_ROOT / "src/desktop_pet/actions/validation.py").read_text(encoding="utf-8")
    body = source[source.index("def load_runtime_registry"):]
    assert BLINK_MANIFEST_RELATIVE_PATH in source
    assert "PLANNED_MANIFEST_RELATIVE_PATHS" not in body
    assert load_runtime_registry is not None


def test_release_build_entry_is_fixed_to_dp_and_fail_fast() -> None:
    script = (PROJECT_ROOT / "packaging/windows/build_xiaorong_1_1_0.ps1").read_text(encoding="utf-8")
    assert 'D:\\anaconda3\\Scripts\\conda.exe' in script
    assert "run --no-capture-output -n dp" in script
    assert '$ErrorActionPreference = "Stop"' in script
    assert "build_xiaorong_release.py" in script


def test_release_verifier_checks_real_frozen_window_and_pe_headers() -> None:
    verifier = (PROJECT_ROOT / "scripts/verify_xiaorong_release.py").read_text(encoding="utf-8")
    for required in (
        "EnumWindows",
        "visible_window_observed",
        "gui_subsystem",
        "win64_machine",
        "runtime_asset_hash",
        "no_development_paths",
    ):
        assert required in verifier
