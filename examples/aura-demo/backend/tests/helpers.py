"""Test helpers for backend tests.

Centralised here so individual test modules can import them without relying
on pytest conftest auto-discovery.
"""
import os
import tempfile

from fastapi.testclient import TestClient


def build_db(n=400, with_hermes_store: bool = False):
    """Create a temporary SQLite book and wire it into data_loader."""
    from core import data_loader, storage
    from generators import generate_data

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    if with_hermes_store:
        from agents.hermes import loop
        from core.hermes_store import SQLiteHermesStore, set_hermes_store

        set_hermes_store(SQLiteHermesStore(conn))
        loop._set_store(None)
    return conn


def auth_client(conn, username="admin", password="adminpass", role="admin"):
    """Return a TestClient authenticated with a JWT bearer token."""
    from core.auth import create_access_token, create_user
    from main import app

    create_user(conn, username, password, role)
    token = create_access_token({"sub": username, "role": role})
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {token}"
    return c
