"""Trace Hermes propose step-by-step for specific client IDs."""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import data_loader, effective, rules_engine
from core.trades import apply_trades
from agents.hermes.proposer import propose
from agents.hermes.strategy_io import load_strategy


def trace(cid: str):
    p = data_loader.get_portfolio(cid)
    eff = effective.get_effective(cid, seed=p)
    rr = rules_engine.check(eff, p["mandate"])
    strategy = load_strategy()
    proposal = propose(eff, rr, strategy)
    prices = data_loader.current_prices()
    post = apply_trades(eff, proposal["trades"], price_lookup=lambda t: prices.get(t))
    post_rr = rules_engine.check(post, p["mandate"])

    out = {
        "client_id": cid,
        "mandate": p["mandate"],
        "effective_holdings": eff["holdings"],
        "effective_cash": eff["cash"],
        "rules_result": rr,
        "strategy": strategy,
        "proposal": proposal,
        "post_holdings": post["holdings"],
        "post_cash": post["cash"],
        "post_rules_result": post_rr,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    for cid in sys.argv[1:]:
        trace(cid)
        print("\n" + "="*80 + "\n")
