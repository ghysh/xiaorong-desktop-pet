# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
ENTRY_POINT = SRC_DIR / "desktop_pet" / "__main__.py"
RUNTIME_ASSET = PROJECT_ROOT / "assets" / "fullbody" / "final" / "fullbody_runtime_master.png"
ICON_PATH = PROJECT_ROOT / "assets" / "icons" / "desktop_pet.ico"
MANIFEST_PATH = PROJECT_ROOT / "packaging" / "windows" / "desktop_pet.manifest"
VERSION_PATH = PROJECT_ROOT / "packaging" / "windows" / "version_info.txt"


analysis = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[(str(RUNTIME_ASSET), "assets/fullbody/final")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyInstaller", "cv2", "matplotlib", "numpy", "pytest", "ruff"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="DesktopPet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_PATH),
    version=str(VERSION_PATH),
    manifest=str(MANIFEST_PATH),
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DesktopPet",
)
