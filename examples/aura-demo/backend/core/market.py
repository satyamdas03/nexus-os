"""Virtual clock + market tick layer.

day lives in the clock singleton. tick() advances the day, precomputes that
day's prices for every ticker (seeded GBM, deterministic), then hands off to
the drift monitor (agents.hermes.monitor.run) to batched-re-check the book and
refresh status_history + book_summary. advance() loops tick; the router's
auto-run loop calls tick on an interval.

Two INDEPENDENT toggles live on the clock row:
  running      — clock auto-ticking on/off
  auto_fix     — Hermes auto-propose on newly-non-green on/off
Applying trades always stays behind the human gate (approve-batch), regardless.
"""
import sqlite3
from typing import Optional

from generators import universe as U
from generators import market as MK
from core import data_loader


def get_clock() -> dict:
    row = data_loader.get_conn_cached().execute("SELECT * FROM clock WHERE id=1").fetchone()
    if row is None:
        return {"day": 0, "running": 0, "auto_interval_sec": 5, "auto_fix": 0, "seed": 42}
    return {"day": row["day"], "running": row["running"], "auto_interval_sec": row["auto_interval_sec"],
            "auto_fix": row["auto_fix"], "seed": row["seed"]}


def set_running(on: bool, interval_sec: Optional[int] = None) -> dict:
    conn = data_loader.get_conn_cached()
    flag = 1 if on else 0
    if interval_sec is not None:
        conn.execute("UPDATE clock SET running=?, auto_interval_sec=? WHERE id=1",
                     (flag, interval_sec))
    else:
        conn.execute("UPDATE clock SET running=? WHERE id=1", (flag,))
    conn.commit()
    return get_clock()


def set_auto_fix(on: bool) -> dict:
    conn = data_loader.get_conn_cached()
    conn.execute("UPDATE clock SET auto_fix=? WHERE id=1", (1 if on else 0,))
    conn.commit()
    return get_clock()


def precompute_prices(day: int) -> None:
    conn = data_loader.get_conn_cached()
    seed = get_clock()["seed"]
    rows = [(t, day, MK.price_for(t, day, seed)) for t in U.all_tickers()]
    conn.executemany("INSERT OR REPLACE INTO prices (ticker, day, price) VALUES (?,?,?)", rows)
    conn.commit()


def _run_monitor(day: int) -> None:
    try:
        from agents.hermes.monitor import run as monitor_run  # Task 6b
    except ImportError:
        # monitor module not importable in this environment (test isolation) —
        # prices still advance. Real monitor runtime errors propagate.
        return
    monitor_run(day)


def tick(run_monitor: bool = True) -> dict:
    conn = data_loader.get_conn_cached()
    day = get_clock()["day"] + 1
    conn.execute("UPDATE clock SET day=? WHERE id=1", (day,))
    conn.commit()
    precompute_prices(day)
    if run_monitor:
        _run_monitor(day)
    return get_clock()


def advance(days: int, run_monitor: bool = True) -> dict:
    for _ in range(max(0, days)):
        # one monitor pass at the end — advance prices without per-step monitor
        tick(run_monitor=False)
    if run_monitor and days > 0:
        _run_monitor(get_clock()["day"])
    return get_clock()


def history(from_day: int, to_day: int) -> list[dict]:
    conn = data_loader.get_conn_cached()
    rows = conn.execute(
        "SELECT day, SUM(CASE status WHEN 'green' THEN 1 ELSE 0 END) AS green, "
        "SUM(CASE status WHEN 'orange' THEN 1 ELSE 0 END) AS orange, "
        "SUM(CASE status WHEN 'red' THEN 1 ELSE 0 END) AS red "
        "FROM status_history WHERE day BETWEEN ? AND ? GROUP BY day ORDER BY day",
        (from_day, to_day),
    ).fetchall()
    return [{"day": r["day"], "green": r["green"], "orange": r["orange"], "red": r["red"]} for r in rows]


def status() -> dict:
    conn = data_loader.get_conn_cached()
    s = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    summary = {"total": s["total"], "green": s["green"], "orange": s["orange"],
               "red": s["red"], "breach_count": s["breach_count"]} if s else {}
    return {"clock": get_clock(), "summary": summary}