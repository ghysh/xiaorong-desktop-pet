# ruff: noqa: F821, I001, UP009
# -*- mode: python ; coding: utf-8 -*-

import json
import os
from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
ENTRY_POINT = SRC_DIR / "desktop_pet" / "__main__.py"
ASSETS_DIR = PROJECT_ROOT / "assets"
DROWSY_SLEEP_DIR = ASSETS_DIR / "actions" / "drowsy_sleep"
DROWSY_SLEEP_MANIFEST = DROWSY_SLEEP_DIR / "manifest.json"
DROWSY_SLEEP_PAYLOAD = json.loads(DROWSY_SLEEP_MANIFEST.read_text(encoding="utf-8"))
DROWSY_SLEEP_FRAME_PATHS = tuple(
    sorted({Path(frame["asset_path"]) for frame in DROWSY_SLEEP_PAYLOAD["frames"]})
)
if any(path.parent != Path("frames") for path in DROWSY_SLEEP_FRAME_PATHS):
    raise ValueError("Drowsy sleep runtime frames must remain directly under frames/.")
BUILD_MODE = os.environ.get("XIAORONG_BUILD_MODE", "onedir").strip().casefold()
if BUILD_MODE not in {"onedir", "onefile"}:
    raise ValueError(f"Unsupported XIAORONG_BUILD_MODE: {BUILD_MODE}")

RUNTIME_DATAS = [
    (ASSETS_DIR / "fullbody" / "final" / "fullbody_runtime_master.png", "assets/fullbody/final"),
    (ASSETS_DIR / "actions" / "click_reply" / "dialogue.txt", "assets/actions/click_reply"),
    (ASSETS_DIR / "actions" / "click_reply" / "dialogue_bubble_frame.png", "assets/actions/click_reply"),
    (ASSETS_DIR / "icons" / "character_original.ico", "assets/icons"),
    (ASSETS_DIR / "actions" / "blink" / "manifest.json", "assets/actions/blink"),
    (ASSETS_DIR / "actions" / "blink" / "frames" / "blink_open.png", "assets/actions/blink/frames"),
    (ASSETS_DIR / "actions" / "blink" / "frames" / "blink_half_closed.png", "assets/actions/blink/frames"),
    (ASSETS_DIR / "actions" / "blink" / "frames" / "blink_closed.png", "assets/actions/blink/frames"),
    (ASSETS_DIR / "actions" / "blink" / "frames" / "blink_half_open.png", "assets/actions/blink/frames"),
    (DROWSY_SLEEP_MANIFEST, "assets/actions/drowsy_sleep"),
    *(
        (DROWSY_SLEEP_DIR / path, "assets/actions/drowsy_sleep/frames")
        for path in DROWSY_SLEEP_FRAME_PATHS
    ),
]

EXCLUDED_MODULES = [
    "PyInstaller",
    "PySide6.QtBluetooth",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "cv2",
    "doctest",
    "matplotlib",
    "numpy",
    "pydoc",
    "pytest",
    "ruff",
    "tkinter",
    "unittest",
]

analysis = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[(str(source), destination) for source, destination in RUNTIME_DATAS],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

common = {
    "name": "小融",
    "debug": False,
    "bootloader_ignore_signals": False,
    "strip": False,
    "upx": False,
    "console": False,
    "icon": str(ASSETS_DIR / "icons" / "character_original.ico"),
    "version": str(PROJECT_ROOT / "packaging" / "windows" / "version_info_1_2_0.txt"),
    "manifest": str(PROJECT_ROOT / "packaging" / "windows" / "xiaorong.manifest"),
}

if BUILD_MODE == "onefile":
    executable = EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        **common,
    )
else:
    executable = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        **common,
    )
    collection = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="小融",
    )
