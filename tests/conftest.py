"""Shared test fixtures."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_repo():
    """Create a temporary git repository."""
    path = Path(tempfile.mkdtemp(prefix="nexus-test-"))
    (path / ".git").mkdir()
    # Minimal git setup so commits work.
    import subprocess

    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@nexus.os"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Nexus Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    yield path
    shutil.rmtree(path, ignore_errors=True)
