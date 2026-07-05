# ASSURE Backup & Restore

This document covers RPO/RTO targets and operational procedures for the
`aura-demo` backend state.

## Scope

The following files constitute the mutable runtime state of an ASSURE instance:

| File | Purpose |
|------|---------|
| `data/portfolios.db` | SQLite book (portfolios, mandates, holdings, prices, clock, state, Hermes queue, audit users) |
| `agents/hermes/strategy.yaml` | Live remediation strategy under human-in-the-loop control |
| `data/audit.jsonl` | Human-readable audit trail |

## Recovery objectives

- **RPO:** 24 hours (daily automated backup).
- **RTO:** 15 minutes (manual restore via `/admin/restore` + service restart for multi-worker deployments).

## Backup methods

### 1. HTTP endpoint (admin only)

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/admin/backup \
     -o assure-backup-$(date -u +%Y%m%dT%H%M%SZ).zip
```

Returns a zip containing `portfolios.db`, `strategy.yaml`, and `audit.jsonl`.

### 2. Local CLI script

```bash
cd backend
python scripts/backup.py --dest backups --keep 14
```

The script writes timestamped zips to `backups/` and prunes old ones.

## Restore procedure

1. Stop any autorun market loop.
2. POST the backup zip as `multipart/form-data`:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     -F "file=@assure-backup-20260101T000000Z.zip" \
     http://localhost:8000/admin/restore
```

3. **Single-worker** (local dev / Uvicorn single process): the service reopens
the new database automatically.
4. **Multi-worker** (Render / production): restart the service so every worker
loads the restored database and strategy file.

## Notes

- Restore requires an `admin` JWT role.
- The endpoint closes the cached SQLite connection before overwriting the DB
file and removes `-wal`/`-shm` sidecars.
- Mandate specs and seed configuration are stored in `portfolios.db`, so a
restore returns the exact same deterministic book plus any approved trades and
Hermes history captured at backup time.
- Backups do **not** include environment variables (JWT secret, admin secret).
Keep those in your secret manager / deployment platform.
