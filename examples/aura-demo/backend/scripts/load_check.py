"""34k scale + market-sim load check.

Generates 34k, runs 20 ticks (timing monitor.run each), runs a delta scan,
times the hot endpoints, prints a report, and exits non-zero if any §11
target is missed. Run:  python scripts/load_check.py
"""
import os, sys, time, tempfile, sqlite3

# allow `from core...` when run from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import storage, data_loader, market
from generators import generate_data
from agents.hermes.monitor import run as monitor_run
from agents.hermes.loop import delta_scan

TARGETS = {
    "generation": 60.0,
    "tick_monitor": 10.0,
    "delta_scan": 5.0,
    "portfolio_lookup": 0.100,
    "summary": 0.050,
    "paged_portfolios": 0.200,
}


def t():
    return time.perf_counter()


def main():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)

    print("== 34k generation ==")
    t0 = t()
    counts = generate_data.build_book(conn, n=34000, seed=42, market_seed=42)
    g = t() - t0
    print(f"  generated {counts} portfolios in {g:.1f}s (target <{TARGETS['generation']}s)")

    data_loader.set_conn(conn)
    market.set_auto_fix(False)  # benchmark re-check only; delta scan is measured separately

    print("== 20 ticks (monitor.run each) ==")
    tick_times = []
    for i in range(20):
        t0 = t()
        market.tick(run_monitor=True)
        tick_times.append(t() - t0)
    avg_tick = sum(tick_times) / len(tick_times)
    max_tick = max(tick_times)
    print(f"  avg tick+monitor {avg_tick:.2f}s, max {max_tick:.2f}s (target <{TARGETS['tick_monitor']}s)")

    print("== delta scan (newly-non-green) ==")
    day = market.get_clock()["day"]
    rows = conn.execute(
        "SELECT client_id FROM status_history WHERE day=? AND status!='green' "
        "AND client_id IN (SELECT client_id FROM status_history WHERE day=? AND status='green')",
        (day, day - 1),
    ).fetchall()
    ids = [r["client_id"] for r in rows][:500]
    t0 = t()
    if ids:
        delta_scan(ids, day)
    ds = t() - t0
    print(f"  delta scan {len(ids)} ids in {ds:.2f}s (target <{TARGETS['delta_scan']}s)")

    print("== endpoint timing ==")
    t0 = t(); data_loader.get_portfolio("c00000"); pl = t() - t0
    t0 = t(); s = data_loader.summary(); sm = t() - t0
    t0 = t(); page = data_loader.list_portfolios(limit=500, offset=0); pp = t() - t0
    print(f"  /portfolio/c00000   {pl*1000:.0f}ms (target <{TARGETS['portfolio_lookup']*1000:.0f}ms)")
    print(f"  /portfolios/summary {sm*1000:.0f}ms (target <{TARGETS['summary']*1000:.0f}ms)  total={s['total']}")
    print(f"  /portfolios?500     {pp*1000:.0f}ms (target <{TARGETS['paged_portfolios']*1000:.0f}ms)  page={len(page)}")

    print("== book distribution @ day 0 ==")
    print(f"  counts={s['counts']}  breaches={s['breach_count']}")

    misses = []
    if g > TARGETS["generation"]: misses.append(("generation", g, TARGETS["generation"]))
    if max_tick > TARGETS["tick_monitor"]: misses.append(("tick_monitor", max_tick, TARGETS["tick_monitor"]))
    if ds > TARGETS["delta_scan"]: misses.append(("delta_scan", ds, TARGETS["delta_scan"]))
    if pl > TARGETS["portfolio_lookup"]: misses.append(("portfolio_lookup", pl, TARGETS["portfolio_lookup"]))
    if sm > TARGETS["summary"]: misses.append(("summary", sm, TARGETS["summary"]))
    if pp > TARGETS["paged_portfolios"]: misses.append(("paged_portfolios", pp, TARGETS["paged_portfolios"]))

    conn.close(); os.remove(path)
    if misses:
        print("\nFAIL — targets missed:")
        for name, val, tgt in misses:
            print(f"  {name}: {val:.3f}s > {tgt}s")
        sys.exit(1)
    print("\nPASS — all targets met.")
    sys.exit(0)


if __name__ == "__main__":
    main()