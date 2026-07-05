#!/usr/bin/env python3
"""Create a local ASSURE state backup zip.

Copies the SQLite book, Hermes strategy.yaml, and audit trail into a
timestamped zip under backups/. This is the cold-backup companion to the
/admin/backup HTTP endpoint; use it from cron or a lifecycle hook when the
backend is not running.

Example:
    python scripts/backup.py
    python scripts/backup.py --dest /var/backups/assure
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = ROOT / "backups"

MEMBERS = [
    ROOT / "data" / "portfolios.db",
    ROOT / "data" / "audit.jsonl",
    ROOT / "agents" / "hermes" / "strategy.yaml",
]


def create_backup(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = dest_dir / f"assure-backup-{ts}.zip"

    missing = [str(p) for p in MEMBERS if not p.exists()]
    if missing:
        print(f"WARNING: missing source files: {', '.join(missing)}", file=sys.stderr)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in MEMBERS:
            if path.exists():
                zf.write(path, arcname=path.name)

    return out


def prune_old(dest_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    files = sorted(
        (p for p in dest_dir.glob("assure-backup-*.zip") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[keep:]:
        old.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="ASSURE local state backup")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="backup directory")
    parser.add_argument("--keep", type=int, default=10, help="number of backups to retain")
    args = parser.parse_args()

    # Make paths relative to CWD if a relative path is given.
    dest = args.dest if args.dest.is_absolute() else Path.cwd() / args.dest
    out = create_backup(dest)
    prune_old(dest, args.keep)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
