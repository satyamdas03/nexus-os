"""Hermetic reflect tests: audit + preferences paths are redirected to tmp_path
via monkeypatch so the real runtime data files are never touched."""
import json

import agents.reflect as reflect
from agents.reflect import suggest, adopt, _seed_audit


def _redirect(monkeypatch, tmp_path, audit_text="", prefs_text=""):
    audit_file = tmp_path / "audit.jsonl"
    prefs_file = tmp_path / "preferences.jsonl"
    audit_file.write_text(audit_text)
    prefs_file.write_text(prefs_text)
    monkeypatch.setattr(reflect, "_AUDIT", audit_file)
    monkeypatch.setattr(reflect, "_PREFS", prefs_file)
    return audit_file, prefs_file


def test_no_suggestion_without_history(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    _seed_audit([])
    assert suggest("c999") is None


def test_suggestion_after_pattern(monkeypatch, tmp_path):
    audit_file, _ = _redirect(monkeypatch, tmp_path)
    _seed_audit([
        {"client_id": "c1", "action_type": "approve", "payload": {"breach_type": "max_sector_weight:Technology", "choice": "trim NVDA"}, "rationale": ""},
        {"client_id": "c2", "action_type": "approve", "payload": {"breach_type": "max_sector_weight:Technology", "choice": "trim NVDA"}, "rationale": ""},
        {"client_id": "c3", "action_type": "approve", "payload": {"breach_type": "max_sector_weight:Technology", "choice": "trim NVDA"}, "rationale": ""},
        {"client_id": "c4", "action_type": "approve", "payload": {"breach_type": "max_sector_weight:Technology", "choice": "trim NVDA"}, "rationale": ""},
        {"client_id": "c5", "action_type": "approve", "payload": {"breach_type": "max_sector_weight:Technology", "choice": "trim NVDA"}, "rationale": ""},
    ])
    s = suggest("c1")
    assert s is not None
    assert "NVDA" in s["suggestion"]
    assert s["count"] >= 5


def test_no_suggestion_below_threshold(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    _seed_audit([
        {"client_id": "c1", "action_type": "approve", "payload": {"breach_type": "x", "choice": "y"}, "rationale": ""},
        {"client_id": "c2", "action_type": "approve", "payload": {"breach_type": "x", "choice": "y"}, "rationale": ""},
    ])
    assert suggest("c1") is None


def test_adopt_writes_preferences(monkeypatch, tmp_path):
    _, prefs_file = _redirect(monkeypatch, tmp_path)
    adopt({"breach_type": "max_sector_weight:Technology", "preference": "trim NVDA",
           "rationale": "5 of 5 cases", "version": 1})
    rows = [json.loads(l) for l in prefs_file.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["preference"] == "trim NVDA"


def test_adopt_dedups_identical_preference(monkeypatch, tmp_path):
    """Repeated Adopt of the same {breach_type, preference} does not accumulate
    duplicate rows — rationale/version update in place."""
    _, prefs_file = _redirect(monkeypatch, tmp_path)
    adopt({"breach_type": "max_sector_weight:Technology", "preference": "trim NVDA",
           "rationale": "5 of 5 cases", "version": 1})
    adopt({"breach_type": "max_sector_weight:Technology", "preference": "trim NVDA",
           "rationale": "now 8 of 8 cases", "version": 2})
    rows = [json.loads(l) for l in prefs_file.read_text().splitlines() if l.strip()]
    assert len(rows) == 1, "identical preference must not accumulate duplicates"
    assert rows[0]["rationale"] == "now 8 of 8 cases"
    assert rows[0]["version"] == 2


def test_adopt_keeps_distinct_preferences(monkeypatch, tmp_path):
    """Different breach_type or preference values are appended as new rows."""
    _, prefs_file = _redirect(monkeypatch, tmp_path)
    adopt({"breach_type": "max_sector_weight:Technology", "preference": "trim NVDA",
           "rationale": "x", "version": 1})
    adopt({"breach_type": "max_single_holding", "preference": "trim AAPL",
           "rationale": "y", "version": 2})
    rows = [json.loads(l) for l in prefs_file.read_text().splitlines() if l.strip()]
    assert len(rows) == 2