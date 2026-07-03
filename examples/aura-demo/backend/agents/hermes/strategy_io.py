"""Strategy.yaml load + the ONE guarded writer reflection is allowed to use.

Reflection may only mutate strategy.yaml (+ archive to history/). It is
structurally forbidden from touching mandate rules or rules_engine.py — the
writer below refuses any path outside those two locations.
"""
import json
import shutil
from pathlib import Path

import yaml

from agents.hermes import STRATEGY_PATH, HISTORY_DIR

_ALLOWED_WRITE_PREFIXES = (STRATEGY_PATH.resolve(), HISTORY_DIR.resolve())


def load_strategy() -> dict:
    """Return the strategy dict {version, variables: {name: {value, rationale}}}."""
    return yaml.safe_load(STRATEGY_PATH.read_text()) or {"version": 0, "variables": {}}


def strategy_vars() -> dict:
    """Flatten to {name: value} for the proposer."""
    return {k: v["value"] for k, v in load_strategy().get("variables", {}).items()}


def _guard(path: Path) -> None:
    rp = path.resolve()
    if not any(str(rp).startswith(str(p)) for p in _ALLOWED_WRITE_PREFIXES):
        raise PermissionError(
            f"refuse to write {rp}: reflection may only touch strategy.yaml or history/. "
            f"mandate rules + rules_engine.py are law and are never writable here.")


def write_strategy(strategy: dict) -> None:
    """The single allowed writer for strategy.yaml. Atomic + guarded."""
    _guard(STRATEGY_PATH)
    STRATEGY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STRATEGY_PATH.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(strategy, sort_keys=False))
    shutil.move(str(tmp), str(STRATEGY_PATH))


def archive_version(version: int, snapshot: dict) -> Path:
    """Archive the pre-mutation strategy snapshot to history/vN.json. Guarded."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    target = HISTORY_DIR / f"v{version}.json"
    _guard(target)
    target.write_text(json.dumps(snapshot, indent=2))
    return target


def adopt_proposal(variable: str, to, rationale: str) -> dict:
    """The human-gated writer. Mutates ONE strategy variable, bumps version,
    archives the prior snapshot, writes atomically. Never touches mandate rules
    or rules_engine.py (the writer guard refuses anything outside strategy.yaml).

    Returns {version, variable, from, to, rationale, archive}.
    """
    strategy = load_strategy()
    if variable not in strategy.get("variables", {}):
        raise KeyError(f"unknown strategy variable: {variable}")
    current = strategy["variables"][variable]["value"]
    old_version = int(strategy.get("version", 0))
    # archive the pre-mutation snapshot under the OLD version number.
    archive_version(old_version, strategy)
    strategy["variables"][variable]["value"] = to
    strategy["variables"][variable]["rationale"] = rationale
    strategy["version"] = old_version + 1
    write_strategy(strategy)
    return {"version": strategy["version"], "variable": variable,
            "from": current, "to": to, "rationale": rationale}


def restore_version(version: int) -> dict:
    """Human-gated rollback. Restores the strategy snapshot archived at
    history/v{version}.json. Before overwriting, archives the CURRENT strategy
    under its current version number so the rollback itself is reversible.
    Bumps the restored strategy's version to old_version + 1 (forward motion).

    Raises FileNotFoundError if history/v{version}.json does not exist.

    Returns {from_version, to_version, restored}.
    """
    snapshot_path = HISTORY_DIR / f"v{version}.json"
    if not snapshot_path.exists():
        raise FileNotFoundError(f"no archived strategy for version {version}")
    current = load_strategy()
    old_version = int(current.get("version", 0))
    # Archive current so rollback is reversible.
    archive_version(old_version, current)
    restored = json.loads(snapshot_path.read_text())
    restored["version"] = old_version + 1
    write_strategy(restored)
    return {"from_version": old_version, "to_version": restored["version"],
            "restored": restored}


# A tiny self-test runs at import time only under `python -m` guard via tests;
# the guard itself is exercised by tests/test_hermes.py.