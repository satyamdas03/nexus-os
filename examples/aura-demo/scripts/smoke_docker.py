"""Smoke test for the ASSURE 2.0 Docker Compose pilot stack.

Verifies that nginx, kernel, backend, and frontend are reachable and return
expected health / content. Run after `docker compose up --build`:

    python scripts/smoke_docker.py

Exit code 0 on success, 1 on any failure.
"""
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"

CHECKS = [
    ("nginx edge", "/nginx-health", lambda b: b == b"healthy\n"),
    ("kernel health", "/v1/health", lambda b: b'"status"' in b or b'"ok"' in b),
    ("backend health", "/api/health", lambda b: b'"status":"ok"' in b.replace(b" ", b"").replace(b'"', b'"')),
    ("frontend root", "/", lambda b: b"<html" in b.lower()),
]


def fetch(path: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return r.read()


def main() -> int:
    failed = False
    for name, path, check in CHECKS:
        try:
            body = fetch(path)
            if not check(body):
                print(f"FAIL: {name} ({path}) — unexpected body: {body[:200]}")
                failed = True
            else:
                print(f"OK:   {name} ({path})")
        except urllib.error.HTTPError as e:
            print(f"FAIL: {name} ({path}) — HTTP {e.code}: {e.read()[:200]}")
            failed = True
        except Exception as e:
            print(f"FAIL: {name} ({path}) — {e}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
