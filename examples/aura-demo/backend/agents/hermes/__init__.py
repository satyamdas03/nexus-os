"""Assure Hermes — autonomous self-improving book-wide remediation engine.

Cage (enforced in code):
    HERMES proposes (strategy.yaml) -> RULES ENGINE verifies (mandate = law)
    -> HUMAN approves -> feeds HERMES reflection

This package holds the judgment layer only. Mandate rules + rules_engine.py
are the law and are never touched by anything in here.
"""
from pathlib import Path

HERMES_DIR = Path(__file__).parent
STRATEGY_PATH = HERMES_DIR / "strategy.yaml"
HISTORY_DIR = HERMES_DIR / "history"
HEARTBEAT_PATH = HERMES_DIR / "heartbeat.json"