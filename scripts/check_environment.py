"""输出第一阶段开发环境的关键检查结果。"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import sys

from desktop_pet.paths import (
    ORIGINAL_ASSETS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_CONDA_ENVIRONMENT = "dp"


def get_conda_environment_name() -> str:
    """读取 Conda 注入的当前环境名称。"""
    return os.environ.get("CONDA_DEFAULT_ENV", "")


def main() -> int:
    """检查环境；未通过 ``conda run -n dp`` 运行时返回非零状态码。"""
    environment_name = get_conda_environment_name()
    if environment_name != EXPECTED_CONDA_ENVIRONMENT:
        print(
            "Error: current Conda environment is not dp. Run: "
            "conda run -n dp python desktop_pet/scripts/check_environment.py",
            file=sys.stderr,
        )
        return 1

    print(f"Python version: {platform.python_version()}")
    print(f"Python executable: {sys.executable}")
    print(f"Conda environment: {environment_name}")
    print(f"Operating system: {platform.platform()}")
    print(f"PySide6 version: {importlib.metadata.version('PySide6')}")
    print(f"Pillow version: {importlib.metadata.version('Pillow')}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Original assets directory exists: {ORIGINAL_ASSETS_DIR.is_dir()}")
    print(f"Original character image found: {ORIGINAL_CHARACTER_IMAGE.is_file()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
