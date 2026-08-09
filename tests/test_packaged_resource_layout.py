"""Spec data-minimization and generated icon checks."""

from __future__ import annotations

from PIL import Image

from desktop_pet.paths import PROJECT_ROOT


def test_spec_packages_only_the_proven_runtime_resources() -> None:
    text = (PROJECT_ROOT / "packaging/windows/xiaorong.spec").read_text(encoding="utf-8")
    for required in (
        "fullbody_runtime_master.png",
        "dialogue.txt",
        "character_original.ico",
        '"blink" / "manifest.json"',
        "blink_open.png",
        "blink_half_closed.png",
        "blink_closed.png",
        "blink_half_open.png",
    ):
        assert required in text
    for forbidden in (
        "ori_figure.png",
        "assets/original",
        "assets/animations",
        "diagnostics",
        "walk_left/manifest.json",
        "dance_wave_step",
    ):
        assert forbidden not in text
    for excluded in ("PyInstaller", "cv2", "matplotlib", "numpy", "pytest", "ruff"):
        assert f'"{excluded}"' in text
    assert "upx=False" in text
    assert '"console": False' in text
    assert "XIAORONG_BUILD_MODE" in text
    assert '"name": "小融"' in text


def test_application_icon_has_all_required_layers() -> None:
    path = PROJECT_ROOT / "assets/icons/character_original.ico"
    with Image.open(path) as icon:
        assert icon.format == "ICO"
        assert (256, 256) in icon.ico.sizes()
