"""Generate deterministic SHA-256 lists with portable relative paths."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Iterable
from pathlib import Path

from desktop_pet.paths import PROJECT_ROOT
from desktop_pet.version import __version__


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def generate_checksums(
    files: Iterable[Path],
    output_path: Path,
    *,
    relative_to: Path | None = None,
) -> list[tuple[str, str]]:
    """Hash existing files and write `HASH *relative/path` lines."""
    output_path = Path(output_path).resolve()
    base = output_path.parent if relative_to is None else Path(relative_to).resolve()
    records: list[tuple[str, str]] = []
    for raw_path in sorted((Path(path).resolve() for path in files), key=lambda path: path.as_posix().casefold()):
        if not raw_path.is_file():
            raise FileNotFoundError(f"Release artifact does not exist: {raw_path}")
        try:
            relative_name = raw_path.relative_to(base).as_posix()
        except ValueError as error:
            raise ValueError(f"Checksum input must be below {base}: {raw_path}") from error
        if Path(relative_name).is_absolute() or ".." in Path(relative_name).parts:
            raise ValueError(f"Checksum entry is not portable: {relative_name}")
        records.append((sha256_file(raw_path), relative_name))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(f"{digest} *{relative_name}\n" for digest, relative_name in records),
        encoding="utf-8",
        newline="\n",
    )
    return records


def default_release_files(release_dir: Path) -> list[Path]:
    names = [
        f"小融-{__version__}-win64.exe",
        "使用说明.txt",
    ]
    return [release_dir / name for name in names if (release_dir / name).is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--output", type=Path)
    namespace = parser.parse_args(argv)
    release_dir = PROJECT_ROOT / "release"
    output = namespace.output or release_dir / "checksums.sha256"
    files = namespace.files or default_release_files(release_dir)
    if not files:
        raise FileNotFoundError("No release artifacts are available for checksum generation.")
    records = generate_checksums(files, output, relative_to=release_dir)
    print(f"Release checksums: {output}")
    print(f"Entries: {len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
