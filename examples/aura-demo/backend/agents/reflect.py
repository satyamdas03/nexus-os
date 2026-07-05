"""Hermes-style learning loop. Surfaces human-approved preference patterns.
Suggests ONE rule-of-thumb at a time. Never auto-applies — human must Adopt.
"""
import json
from pathlib import Path
from collections import Counter

_AUDIT = Path(__file__).parent.parent / "data" / "audit.jsonl"
_PREFS = Path(__file__).parent.parent / "data" / "preferences.jsonl"
_THRESHOLD = 5  # N decisions of a breach type before suggesting


def _seed_audit(entries: list[dict]) -> None:
    """Test helper — overwrite audit log with given entries."""
    _AUDIT.parent.mkdir(parents=True, exist_ok=True)
    _AUDIT.write_text("\n".join(json.dumps(e) for e in entries) + ("\n" if entries else ""))


def _history() -> list[dict]:
    if not _AUDIT.exists():
        return []
    return [json.loads(l) for l in _AUDIT.read_text().splitlines() if l.strip()]


def suggest(client_id: str) -> dict | None:
    """Detect a preference pattern from past approve decisions. Returns suggestion or None."""
    approves = [e for e in _history() if e.get("action_type") == "approve"]
    by_breach: dict[str, list[str]] = {}
    for e in approves:
        bt = e.get("payload", {}).get("breach_type")
        choice = e.get("payload", {}).get("choice")
        if bt and choice:
            by_breach.setdefault(bt, []).append(choice)
    for bt, choices in by_breach.items():
        if len(choices) >= _THRESHOLD:
            top, n = Counter(choices).most_common(1)[0]
            if n >= _THRESHOLD:
                return {
                    "breach_type": bt,
                    "pattern": f"{n} of {len(choices)} {bt} cases: {top}",
                    "suggestion": f"In {n} of last {len(choices)} {bt.split(':')[-1]} cases you {top} — default to that?",
                    "count": n,
                }
    return None


def adopt(preference: dict) -> None:
    """Human clicked Adopt — write preference + rationale, version bump.

    Dedup: if an identical {breach_type, preference} row already exists in
    preferences.jsonl, update its rationale/version in place instead of
    appending a duplicate row. Keeps the preference log from accumulating
    identical rows on repeated Adopt clicks.
    """
    _PREFS.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    replaced = False
    bt = preference.get("breach_type")
    pref = preference.get("preference")
    if _PREFS.exists():
        for line in _PREFS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if rec.get("breach_type") == bt and rec.get("preference") == pref:
                # Update rationale/version in place; do not duplicate.
                rec["rationale"] = preference.get("rationale", rec.get("rationale", ""))
                rec["version"] = preference.get("version", rec.get("version"))
                rows.append(json.dumps(rec))
                replaced = True
            else:
                rows.append(line)
    if not replaced:
        rows.append(json.dumps(preference))
    _PREFS.write_text("\n".join(rows) + ("\n" if rows else ""))