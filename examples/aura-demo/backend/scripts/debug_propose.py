"""Debug Hermes proposer step-by-step for c00137."""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import data_loader, effective, rules_engine
from agents.hermes.strategy_io import load_strategy
from agents.hermes.proposer import _total, _holding, _trim_to_cap, strategy_vars, DEFAULT_BREACH_PRIORITY


def debug(cid: str):
    p = data_loader.get_portfolio(cid)
    eff = effective.get_effective(cid, seed=p)
    rr = rules_engine.check(eff, p["mandate"])
    strategy = load_strategy()
    vars_ = strategy_vars(strategy)
    priority = vars_.get("breach_priority_order") or []
    seen = set(priority)
    priority = list(priority) + [r for r in DEFAULT_BREACH_PRIORITY if r not in seen]
    method = vars_.get("preferred_trim_method", "proportional")
    max_trades = int(vars_.get("max_trades_per_portfolio", 4))

    breaches = rr.get("breaches", [])
    by_type = {}
    for b in breaches:
        by_type.setdefault(b["rule"].split(":")[0], []).append(b)

    total = _total(eff)
    post_mv = {h["ticker"]: h["market_value"] for h in eff["holdings"]}
    trades = []

    for breach_type in priority:
        if len(trades) >= max_trades:
            print(f"BREAK due to max_trades ({max_trades})")
            break
        bs = by_type.get(breach_type, [])
        if not bs:
            continue
        print(f"\n=== {breach_type} ===  trades_so_far={len(trades)}")
        if breach_type == "max_region_weight":
            for b in bs:
                region = b["rule"].split(":")[1]
                offenders = [h for h in eff["holdings"] if h.get("region") == region]
                current = sum(post_mv.get(h["ticker"], 0.0) for h in offenders) / total
                print(f"  region={region} current={current:.6f} limit={b['limit']} target={b['limit']-0.005}")
                t = _trim_to_cap(eff, current, b["limit"], offenders, method, remaining_mv=post_mv)
                print(f"  generated {len(t)} trades: {t}")
                for tr in t:
                    if len(trades) >= max_trades:
                        break
                    post_mv[tr["ticker"]] = max(0.0, post_mv.get(tr["ticker"], 0.0) - tr["value"])
                    trades.append(tr)
        elif breach_type == "max_single_holding":
            limit = bs[0]["limit"]
            weights = {h["ticker"]: post_mv.get(h["ticker"], 0.0) / total for h in eff["holdings"]}
            print(f"  limit={limit} target={limit-0.005}")
            for b in bs:
                for tk in b.get("offending_holdings", []):
                    h = _holding(eff, tk)
                    print(f"  tk={tk} weight={weights.get(tk,0):.6f} post_mv={post_mv.get(tk,0):.2f}")
                    if not h or len(trades) >= max_trades:
                        print(f"    skip: no holding or max_trades")
                        continue
                    over_value = (weights[tk] - (limit - 0.005)) * total
                    print(f"    over_value={over_value:.2f}")
                    if over_value <= 1e-9:
                        print(f"    skip: over_value <= eps")
                        continue
                    units = min(post_mv.get(tk, 0.0) / h["price"], over_value / h["price"])
                    print(f"    sell units={units:.4f}")
                    post_mv[tk] = max(0.0, post_mv.get(tk, 0.0) - units * h["price"])
                    trades.append({"ticker": tk, "action": "sell", "units": round(units, 6),
                                   "value": round(units * h["price"], 2)})
        elif breach_type == "max_top_n_concentration":
            tn = bs[0]
            offenders = [_holding(eff, tk) for tk in tn.get("offending_holdings", [])]
            offenders = [o for o in offenders if o]
            current = sum(post_mv.get(o["ticker"], 0.0) for o in offenders) / total
            print(f"  current={current:.6f} limit={tn['limit']} target={tn['limit']-0.005}")
            t = _trim_to_cap(eff, current, tn["limit"], offenders, method, remaining_mv=post_mv)
            print(f"  generated {len(t)} trades: {t}")
            for tr in t:
                if len(trades) >= max_trades:
                    break
                post_mv[tr["ticker"]] = max(0.0, post_mv.get(tr["ticker"], 0.0) - tr["value"])
                trades.append(tr)
        elif breach_type == "min_cash":
            print(f"  cash current={eff['cash']/total:.6f} limit={bs[0]['limit']}")
        elif breach_type == "min_liquid_pct":
            tier1_w = sum(post_mv.get(h["ticker"], 0.0) for h in eff["holdings"] if h.get("liquidity_tier") == 1) / total
            print(f"  tier1={tier1_w:.6f} limit={bs[0]['limit']}")

    print(f"\nFINAL trades ({len(trades)}):")
    for t in trades:
        print(t)


if __name__ == "__main__":
    debug(sys.argv[1])
