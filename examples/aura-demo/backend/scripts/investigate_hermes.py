"""Investigate why Hermes skips/misses portfolios locally."""
import sys, os, json
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import data_loader, effective, rules_engine
from core.trades import apply_trades
from agents.hermes.proposer import propose
from agents.hermes.strategy_io import load_strategy


def main(sample=None):
    strategy = load_strategy()
    prices = data_loader.current_prices()
    conn = data_loader.get_conn_cached()
    rows = conn.execute("SELECT client_id FROM portfolios ORDER BY client_id").fetchall()
    ids = [r["client_id"] for r in rows]
    if sample:
        ids = ids[:sample]

    counts = {"scanned": 0, "green": 0, "skipped": 0, "missed": 0, "remediated": 0}
    skipped_breach_types = Counter()
    missed_breach_types = Counter()
    missed_examples = []
    skipped_examples = []

    for cid in ids:
        p = data_loader.get_portfolio(cid)
        if p is None:
            continue
        eff = effective.get_effective(cid, seed=p)
        if eff is None:
            continue
        rr = rules_engine.check(eff, p["mandate"])
        counts["scanned"] += 1
        if rr["status"] == "green":
            counts["green"] += 1
            continue
        proposal = propose(eff, rr, strategy)
        trades = proposal["trades"]
        if not trades:
            counts["skipped"] += 1
            bt = ",".join(sorted({b["rule"].split(":")[0] for b in rr["breaches"]}))
            skipped_breach_types[bt] += 1
            if len(skipped_examples) < 5:
                skipped_examples.append({"cid": cid, "status": rr["status"], "breaches": rr["breaches"], "rationale": proposal["rationale"]})
            continue
        post = apply_trades(eff, trades, price_lookup=lambda t: prices.get(t))
        post_rr = rules_engine.check(post, p["mandate"])
        if post_rr["breaches"]:
            counts["missed"] += 1
            bt = ",".join(sorted({b["rule"].split(":")[0] for b in post_rr["breaches"]}))
            missed_breach_types[bt] += 1
            if len(missed_examples) < 5:
                missed_examples.append({"cid": cid, "status": rr["status"], "post_breaches": post_rr["breaches"], "trades": trades, "rationale": proposal["rationale"]})
        else:
            counts["remediated"] += 1

    print(json.dumps({
        "counts": counts,
        "skipped_breach_types": dict(skipped_breach_types.most_common(10)),
        "missed_breach_types": dict(missed_breach_types.most_common(10)),
        "skipped_examples": skipped_examples,
        "missed_examples": missed_examples,
    }, indent=2, default=str))


if __name__ == "__main__":
    sample = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(sample)
