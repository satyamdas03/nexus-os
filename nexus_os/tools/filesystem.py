"""Safe filesystem helpers."""

from __future__ import annotations

from pathlib import Path


def safe_write(path: Path, content: str) -> None:
    """Write content to a file, creating parent directories safely."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
