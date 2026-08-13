"""Read and cache one-dialogue-per-line text without modifying its source."""

from __future__ import annotations

from pathlib import Path


class DialogueFileError(RuntimeError):
    """Raised when the configured dialogue file cannot provide safe text."""


class DialogueRepository:
    """A one-read, immutable dialogue repository with explicit encoding fallback."""

    _ENCODINGS = ("utf-8-sig", "gb18030")

    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve()
        self._dialogues: tuple[str, ...] | None = None
        self._encoding: str | None = None
        self._read_count = 0
        self._blank_line_count = 0

    @property
    def encoding(self) -> str | None:
        return self._encoding

    @property
    def read_count(self) -> int:
        return self._read_count

    @property
    def blank_line_count(self) -> int:
        return self._blank_line_count

    def load(self) -> tuple[str, ...]:
        """Read once, preserve nonblank lines verbatim, and return a cached tuple."""
        if self._dialogues is not None:
            return self._dialogues
        try:
            content = self.path.read_bytes()
        except OSError as error:
            raise DialogueFileError(f"Dialogue file cannot be read: {self.path}; {error}") from error
        self._read_count += 1

        decoded: str | None = None
        failures: list[str] = []
        for encoding in self._ENCODINGS:
            try:
                decoded = content.decode(encoding)
            except UnicodeDecodeError as error:
                failures.append(f"{encoding}: {error}")
                continue
            self._encoding = encoding
            break
        if decoded is None:
            details = "; ".join(failures)
            raise DialogueFileError(f"Dialogue file encoding is invalid: {self.path}; {details}")

        lines = decoded.splitlines()
        self._blank_line_count = sum(not line.strip() for line in lines)
        dialogues = tuple(line for line in lines if line.strip())
        if not dialogues:
            raise DialogueFileError(f"Dialogue file contains no non-empty dialogue: {self.path}")
        self._dialogues = dialogues
        return dialogues
