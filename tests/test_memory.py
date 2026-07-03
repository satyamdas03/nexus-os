"""Tests for the reboot-proof memory store."""

from __future__ import annotations

import json

from nexus_os.memory.store import MemoryStore


def test_memory_store_init(temp_repo):
    store = MemoryStore(temp_repo)
    state = store.init_state({"goal": "test", "mode": "micro"})
    assert store.state_path.exists()
    assert state["goal"] == "test"
    assert state["status"] == "idle"


def test_write_and_read_state(temp_repo):
    store = MemoryStore(temp_repo)
    store.init_state({})
    store.write_state({"status": "running", "phase": 3})
    read = store.read_state()
    assert read["status"] == "running"
    assert read["phase"] == 3


def test_checkpoint(temp_repo):
    store = MemoryStore(temp_repo)
    store.init_state({"tasks": []})
    path = store.checkpoint("test", {"tasks": [1, 2]})
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tasks"] == [1, 2]


def test_handoff_and_memory(temp_repo):
    store = MemoryStore(temp_repo)
    store.init_state({})
    handoff = store.write_handoff("standard", "dev", "qa", 3, "T001", "context")
    assert handoff.exists()
    memory = store.write_memory("frontend-developer", "T001", "output")
    assert memory.exists()


def test_auto_commit(temp_repo):
    store = MemoryStore(temp_repo)
    store.init_state({})
    result = store.auto_commit("nexus: test commit")
    assert result is True
