"""Create the portable onedir ZIP with an exact DesktopPet root."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.version import __version__

FORBIDDEN_PARTS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "scripts", "tests"}
FORBIDDEN_NAMES = {"ori_figure.png", "settings.ini"}


def archive_members(source_dir: Path) -> list[Path]:
    source_dir = Path(source_dir).resolve()
    if source_dir.name != "DesktopPet" or not (source_dir / "DesktopPet.exe").is_file():
        raise ValueError("Portable source must be a DesktopPet directory containing DesktopPet.exe.")
    members: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        folded_parts = {part.casefold() for part in relative.parts}
        if folded_parts & {part.casefold() for part in FORBIDDEN_PARTS}:
            continue
        if path.name.casefold() in {name.casefold() for name in FORBIDDEN_NAMES}:
            continue
        members.append(path)
    return members


def create_archive(source_dir: Path, archive_path: Path) -> int:
    source_dir = Path(source_dir).resolve()
    archive_path = Path(archive_path).resolve()
    members = archive_members(source_dir)
    if not members:
        raise ValueError("Portable release directory has no files to archive.")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in members:
            archive.write(path, (Path("DesktopPet") / path.relative_to(source_dir)).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if not names or any(not name.startswith("DesktopPet/") for name in names):
            raise RuntimeError("Release ZIP does not have the required DesktopPet root.")
        if "DesktopPet/DesktopPet.exe" not in names:
            raise RuntimeError("Release ZIP is missing DesktopPet/DesktopPet.exe.")
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"Release ZIP failed CRC verification: {bad}")
    return len(members)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "dist" / "pyinstaller" / "DesktopPet")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "release" / f"DesktopPet-{__version__}-win64-portable.zip",
    )
    namespace = parser.parse_args(argv)
    count = create_archive(namespace.source, namespace.output)
    print(f"Portable ZIP: {namespace.output.resolve()}")
    print(f"Files archived: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
