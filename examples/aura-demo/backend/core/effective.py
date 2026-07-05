# backend/core/effective.py
"""Shadow-state layer over SQLite. The immutable seed (holdings in portfolios.db)
plus approved trades (rows in the `state` table) = the effective portfolio.

Every read path (heatmap, diagnosis, triage, rules engine, Hermes scan) consumes
effective_portfolio(p) so a human-approved remediation flips red -> green and
STAYS green on reload. record_trades is called only by the human gate
(approve-batch). reset_state is called by /admin/reset before each demo run.

34k update: state lives in the SQLite `state` table (schema in core/storage.py)
rather than a runtime JSON file, so it survives process restarts and is isolated
per client_id. Revalue uses data_loader.current_prices() (live market day) via
apply_trades' price_lookup, so buys of new tickers reflect current prices.
"""
from datetime import datetime, timezone
import sqlite3
from typing import Optional

from core.trades import apply_trades
from core import data_loader

# Whether the `state` table currently holds any rows. The drift monitor hot loop
# calls applied_trades() per portfolio (34k/tick); when nothing has been approved
# yet (the common demo path) we skip the per-portfolio query entirely. Invalidated
# by record_trades / reset_state / set_conn.
_state_has_rows: Optional[bool] = None
_state_flag_conn: Optional[sqlite3.Connection] = None


def _refresh_state_flag() -> None:
    global _state_has_rows, _state_flag_conn
    conn = data_loader.get_conn_cached()
    _state_flag_conn = conn
    _state_has_rows = conn.execute("SELECT EXISTS(SELECT 1 FROM state LIMIT 1)").fetchone()[0] == 1


def applied_trades(client_id: str) -> list[dict]:
    """Read this client's approved trades from `state`, oldest first (rowid order
    preserves insertion/ts order)."""
    global _state_has_rows
    conn = data_loader.get_conn_cached()
    # Re-evaluate the flag if the cached connection changed (e.g. set_conn in tests).
    if _state_has_rows is None or _state_flag_conn is not conn:
        _refresh_state_flag()
    if not _state_has_rows:
        return []
    rows = conn.execute(
        "SELECT ticker, action, units, value, rationale, ts FROM state WHERE client_id=? ORDER BY rowid",
        (client_id,),
    ).fetchall()
    return [{"ticker": r["ticker"], "action": r["action"], "units": r["units"],
             "value": r["value"], "rationale": r["rationale"], "ts": r["ts"]} for r in rows]


def effective_portfolio(portfolio: dict) -> dict:
    """Seed holdings + this client's approved trades, revalued at current prices.

    Lazy revalue: market_value = units * price(current_day) happens inside
    apply_trades via the price_lookup. No eager writes to the base holdings.
    Returns the seed unchanged when no trades are recorded.
    """
    trades = applied_trades(portfolio["client_id"])
    if not trades:
        return portfolio
    payload = [{"ticker": t["ticker"], "action": t["action"], "units": t["units"]} for t in trades]
    return apply_trades(portfolio, payload, price_lookup=lambda t: data_loader.current_prices().get(t))


def get_effective(client_id: str, seed: Optional[dict] = None) -> Optional[dict]:
    p = seed if seed is not None else data_loader.get_portfolio(client_id)
    if p is None:
        return None
    return effective_portfolio(p)


def record_trades(client_id: str, trades: list[dict], rationale: str = "") -> None:
    """Append approved trades to the `state` table. Each row shares a UTC ts so
    the log is ordered by insertion. Called by the human approve-batch gate."""
    global _state_has_rows
    conn = data_loader.get_conn_cached()
    ts = datetime.now(timezone.utc).isoformat()
    rows = []
    for t in trades:
        rows.append((client_id, ts, t.get("ticker"), t.get("action"),
                     float(t.get("units", 0)), float(t.get("value", 0) or 0), rationale))
    conn.executemany(
        "INSERT INTO state (client_id, ts, ticker, action, units, value, rationale) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    if rows:
        _state_has_rows = True


def reset_state() -> list[str]:
    """DELETE all rows from `state`; return the client_ids that had state.
    Called by /admin/reset before each demo run."""
    global _state_has_rows
    conn = data_loader.get_conn_cached()
    cleared = [r["client_id"] for r in conn.execute("SELECT DISTINCT client_id FROM state").fetchall()]
    conn.execute("DELETE FROM state")
    conn.commit()
    _state_has_rows = False
    return cleared