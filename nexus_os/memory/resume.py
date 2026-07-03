"""Resume logic for interrupted NEXUS runs."""

from __future__ import annotations

from pathlib import Path

from nexus_os.memory.store import MemoryStore


def detect_interruption(repo_path: Path) -> dict | None:
    """Return state if a previous run was interrupted (status == running)."""
    store = MemoryStore(repo_path)
    state = store.read_state()
    if not state:
        return None
    if state.get("status") == "running":
        return state
    return None


def can_resume(repo_path: Path) -> bool:
    """Return True if an interrupted run can be resumed."""
    return detect_interruption(repo_path) is not None
