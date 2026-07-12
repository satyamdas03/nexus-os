"""Shared test defaults and helpers for the ASSURE backend test suite.

Most tests run with AUTH_ENFORCE=0 so they don't need production secrets.
Strict-auth tests override these values explicitly in their fixtures.
"""
import os

import pytest

from tests.helpers import auth_client, build_db


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: tests that are slow or environment-sensitive")


# Dev fallback defaults for local/CI test runs. Strict-auth tests override.
os.environ.setdefault("AUTH_SECRET", "test-secret-32-bytes-long-ok")
os.environ.setdefault("AUTH_ADMIN_PASSWORD", "adminpass")
os.environ.setdefault("AUTH_ENFORCE", "0")


@pytest.fixture(autouse=True)
def _deterministic_llm(monkeypatch):
    """Force all LLM paths onto a deterministic offline mock.

    Even if a test or environment variable sets ANTHROPIC_API_KEY, the
    ClaudeProvider.complete method is replaced with MockLLM output so the
    suite never makes network calls and never depends on live Anthropic
    behavior."""
    from agents.llm import ClaudeProvider, MockLLM

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-offline")
    _mock = MockLLM()
    monkeypatch.setattr(ClaudeProvider, "complete", lambda self, system, user: _mock.complete(system, user))


@pytest.fixture
def client():
    """Authenticated admin client backed by a 400-portfolio temp book."""
    conn = build_db(n=400)
    c = auth_client(conn)
    try:
        yield c
    finally:
        from core import data_loader

        data_loader.set_conn(None)
        try:
            conn.close()
        except Exception:
            pass


@pytest.fixture
def client_db(client):
    """Yield the SQLite connection backing the current `client` fixture."""
    from core import data_loader

    yield data_loader.get_conn_cached()
