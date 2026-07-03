"""File-backed memory store with optional git auto-commit."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from nexus_os.config import get_settings


class MemoryStore:
    """Manages `.nexus-os/` state, checkpoints, handoffs, and logs."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()
        self.nexus_dir = self.repo_path / ".nexus-os"
        self.state_path = self.nexus_dir / "state.json"
        self.checkpoints_dir = self.nexus_dir / "checkpoints"
        self.handoffs_dir = self.nexus_dir / "handoffs"
        self.memory_dir = self.nexus_dir / "memory"
        self.logs_dir = self.nexus_dir / "logs"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for directory in (
            self.nexus_dir,
            self.checkpoints_dir,
            self.handoffs_dir,
            self.memory_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def init_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create initial state.json for a project."""
        now = datetime.now(UTC).isoformat()
        base = {
            "version": "0.1.0",
            "project_path": str(self.repo_path),
            "created_at": now,
            "updated_at": now,
            "status": "idle",
            "mode": "micro",
            "phase": 0,
            "goal": "",
            "agents": [],
            "tasks": [],
            "current_task_id": None,
            "metadata": {},
        }
        base.update(state)
        self.write_state(base)
        return base

    def write_state(self, state: dict[str, Any]) -> None:
        """Persist state.json and update the timestamp."""
        state["updated_at"] = datetime.now(UTC).isoformat()
        self.state_path.write_text(
            json.dumps(state, indent=2, default=str), encoding="utf-8"
        )

    def read_state(self) -> dict[str, Any] | None:
        """Read current state.json if it exists."""
        if not self.state_path.exists():
            return None
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def checkpoint(self, name: str, state: dict[str, Any] | None = None) -> Path:
        """Write a named checkpoint of the current state."""
        if state is None:
            state = self.read_state() or {}
        now = datetime.now(UTC)
        filename = f"{now:%Y%m%d_%H%M%S}_{name}.json"
        path = self.checkpoints_dir / filename
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        return path

    def write_handoff(
        self,
        handoff_type: str,
        from_agent: str,
        to_agent: str,
        phase: int,
        task_id: str | None,
        content: str,
    ) -> Path:
        """Write a handoff markdown document."""
        now = datetime.now(UTC)
        filename = f"{now:%Y%m%d_%H%M%S}_{handoff_type}_{from_agent}_to_{to_agent}.md"
        path = self.handoffs_dir / filename
        header = f"""---
type: {handoff_type}
from: {from_agent}
to: {to_agent}
phase: {phase}
task_id: {task_id or "n/a"}
timestamp: {now.isoformat()}
---

"""
        path.write_text(header + content, encoding="utf-8")
        return path

    def write_memory(
        self, agent_slug: str, task_id: str | None, content: str, extension: str = "md"
    ) -> Path:
        """Write an agent output or memory artifact."""
        now = datetime.now(UTC)
        safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_slug)
        filename = f"{now:%Y%m%d_%H%M%S}_{safe_slug}_{task_id or 'general'}.{extension}"
        path = self.memory_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def log(self, message: str, level: str = "info") -> Path:
        """Append a line to the decision log."""
        now = datetime.now(UTC)
        log_file = self.logs_dir / f"{now:%Y-%m-%d}.log"
        line = f"{now.isoformat()} [{level.upper()}] {message}\n"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
        return log_file

    def write_config(self, config: dict[str, Any]) -> None:
        """Write project-local config if needed."""
        path = self.nexus_dir / "config.yaml"
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def auto_commit(self, message: str) -> bool:
        """Commit `.nexus-os/` changes when inside a git repo and enabled."""
        settings = get_settings()
        if not settings.auto_commit:
            return False
        if not (self.repo_path / ".git").exists():
            return False
        try:
            # Stage only .nexus-os to avoid capturing unrelated work.
            subprocess.run(
                ["git", "add", ".nexus-os/"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            # Check if there is anything to commit.
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True  # nothing to commit
            subprocess.run(
                ["git", "commit", "-m", message, "-m", "Co-Authored-By: Claude <noreply@anthropic.com>"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
