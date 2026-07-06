"""Round-trip tests for /admin/backup and /admin/restore."""
import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from core import data_loader, storage
from core.auth import create_user
from generators import generate_data
from routers import admin as admin_router


def _setup():
    import tempfile

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(db_path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=100, seed=42, market_seed=42)

    # Point both the file path and the cached connection at the temp DB.
    old_db_path = storage.DB_PATH
    storage.DB_PATH = db_path
    data_loader.set_conn(conn)

    # Create tiny companion files so backup/restore have all members.
    import tempfile as tf

    strategy_fd, strategy_path = tf.mkstemp(suffix=".yaml")
    os.close(strategy_fd)
    audit_fd, audit_path = tf.mkstemp(suffix=".jsonl")
    os.close(audit_fd)
    with open(strategy_path, "w") as f:
        f.write("version: 1\n")
    with open(audit_path, "w") as f:
        f.write('{"event":"test"}\n')

    # Patch the admin router to use these temp files for the test.
    from pathlib import Path

    old_strategy = admin_router.STRATEGY_PATH
    old_audit = admin_router.AUDIT_PATH
    admin_router.STRATEGY_PATH = Path(strategy_path)
    admin_router.AUDIT_PATH = Path(audit_path)

    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"

    from main import app

    c = TestClient(app)
    create_user(conn, "admin", "adminpass", "admin")
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    return c, db_path, strategy_path, audit_path, old_strategy, old_audit, old_enforce, old_secret, old_db_path


def _teardown(db_path, strategy_path, audit_path, old_strategy, old_audit, old_enforce, old_secret, old_db_path):
    data_loader.set_conn(None)
    storage.DB_PATH = old_db_path
    for p in (db_path, strategy_path, audit_path):
        try:
            os.unlink(p)
        except OSError:
            pass
        for suffix in ("-wal", "-shm"):
            try:
                os.unlink(p + suffix)
            except OSError:
                pass
    admin_router.STRATEGY_PATH = old_strategy
    admin_router.AUDIT_PATH = old_audit

    if old_enforce is None:
        os.environ.pop("AUTH_ENFORCE", None)
    else:
        os.environ["AUTH_ENFORCE"] = old_enforce
    if old_secret is None:
        os.environ.pop("AUTH_SECRET", None)
    else:
        os.environ["AUTH_SECRET"] = old_secret


@pytest.fixture
def admin_backup_client():
    c, db_path, strategy_path, audit_path, old_strategy, old_audit, old_enforce, old_secret, old_db_path = _setup()
    try:
        yield c, db_path, strategy_path, audit_path
    finally:
        _teardown(db_path, strategy_path, audit_path, old_strategy, old_audit, old_enforce, old_secret, old_db_path)


def test_backup_returns_zip(admin_backup_client):
    c, db_path, strategy_path, audit_path = admin_backup_client
    r = c.get("/admin/backup")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    db_name = os.path.basename(db_path)
    assert db_name in names
    assert os.path.basename(strategy_path) in names
    assert os.path.basename(audit_path) in names


def test_restore_roundtrip(admin_backup_client):
    c, db_path, strategy_path, audit_path = admin_backup_client

    # 1. Capture the original first portfolio name.
    r = c.get("/portfolios?limit=1&offset=0")
    assert r.status_code == 200
    original_name = r.json()[0]["client_name"]

    # 2. Backup.
    r = c.get("/admin/backup")
    assert r.status_code == 200
    backup_bytes = r.content

    # 3. Mutate: rename the first portfolio so we can prove restore reverts it.
    conn = data_loader.get_conn_cached()
    first_id = conn.execute("SELECT client_id FROM portfolios LIMIT 1").fetchone()["client_id"]
    conn.execute("UPDATE portfolios SET client_name = ? WHERE client_id = ?", ("MUTATED", first_id))
    conn.commit()

    r = c.get(f"/portfolio/{first_id}")
    assert r.status_code == 200
    assert r.json()["client_name"] == "MUTATED"

    # 4. Restore from backup.
    r = c.post(
        "/admin/restore",
        files={"file": ("backup.zip", io.BytesIO(backup_bytes), "application/zip")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # 5. Verify the mutation is gone.
    r = c.get(f"/portfolio/{first_id}")
    assert r.status_code == 200
    assert r.json()["client_name"] == original_name


def test_restore_rejects_non_zip(admin_backup_client):
    c, *_ = admin_backup_client
    r = c.post(
        "/admin/restore",
        files={"file": ("not-a-zip.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    assert ".zip" in r.json()["detail"]
