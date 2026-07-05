"""Synthetic 34k portfolio generator -> SQLite. Deterministic given seeds.
No real data.

Distribution target: ~5% red / 15% orange / 80% green. FUM is lognormal
(few huge, many small). Mandates are drawn from generators/mandates.py and
deduped by JSON spec (far fewer mandate rows than portfolios) — one mandate
per template is pre-built so the 34k book shares ~8 mandate rows. Holdings
carry region + liquidity_tier (copied from the universe) so all 10 rule dims
evaluate.

The green cohort is built cap-aware against the rules engine (check()) and
then repaired so the seed distribution holds on actual status, not just
intent. Red cohorts inject one deliberate, reliable single-name over-cap
breach; orange injects a drift watch (over target + tolerance, under the hard
cap) funded from cash headroom. Day-0 prices are written from
generators/market.prices_for_day(0).
"""
import hashlib
import json
import math
import random
import sqlite3

from assure_kernel import dumps_mandate, parse_mandate
from generators import universe as U
from generators import mandates as M
from generators import market as MK
from core import storage, rules_engine
from core.trades import apply_trades

ADVISERS = [
    "Pat Quinn", "Renee Cole", "Aaron Wright", "Mia Tan", "Grant Hale",
    "Sora Kim", "Dev Patel", "Lena Voss", "Marco Reyes", "Ingrid Olsen",
    "Toby Ng", "Priya Rao", "Felix Stone", "Hana Sato", "Omar Khalil",
    "Nina Brooks", "Eli Carr", "Maya Lin", "Jonas Berg", "Ruth Cohen",
    "Tariq Bello", "Greta Holt", "Vince Ito", "Cara Duffy", "Sam Rooney",
    "Iris Vale", "Bo Mercer", "Dana Pike", "Karl Webb", "Luz Marin",
]

_NAME_A = ["Acme", "Bluecrest", "Cedar", "Dover", "Eldon", "Fairhaven", "Greenleaf",
           "Hawthorn", "Iris", "Juniper", "Kestrel", "Linden", "Maple", "Northgate",
           "Orchid", "Pinegrove", "Quill", "Rosewood", "Silverstone", "Thistle",
           "Umber", "Verdant", "Westbrook", "Xanadu", "Yarrow", "Zephyr", "Aster",
           "Briar", "Cobalt", "Driftwood", "Elm", "Fjord", "Garnet", "Hazel", "Indigo",
           "Jade", "Knot", "Laurel", "Moss", "Nimbus"]
_NAME_B = ["Holdings", "Capital", "Wealth", "Trust", "Partners", "Advisory", "Asset Mgmt",
           "Securities", "Investments", "Group", "Family Office", "Endowment", "Pension",
           "Foundation", "Stewardship"]


def _name(rng, idx):
    a = rng.choice(_NAME_A); b = rng.choice(_NAME_B)
    return f"{a} {b} #{idx:05d}"


def _fum(rng):
    # lognormal: median ~$800k (exp(mu)), long right tail -> few huge, many small.
    # lognormvariate already returns exp(normal(mu, sigma)); do NOT wrap in exp.
    return round(rng.lognormvariate(math.log(800_000), 1.7), 2)


def _mandate_for(rng, mandate_rows, spec_to_id, template_idx):
    """Build a mandate instance and return its id + legacy dict.

    Mandates are deduplicated by a SHA-256 hash of the canonical JSON spec.
    Each unique mandate row stores the legacy spec, the DSL YAML, version,
    source template path, creation timestamp, and hash.
    """
    m = M.build_mandate(rng, template_idx)
    key = json.dumps(m, sort_keys=True)
    spec_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if spec_hash in spec_to_id:
        return spec_to_id[spec_hash], m

    mid = len(spec_to_id) + 1
    mandate = parse_mandate(m)
    dsl = dumps_mandate(mandate)
    source_path = f"data/mandates/t{template_idx % M.template_count()}.yaml"
    # Fixed synthetic creation timestamp so book generation stays deterministic.
    created_ts = "2026-07-03T00:00:00+00:00"
    mandate_rows.append((mid, key, mandate.version, dsl, source_path, created_ts, spec_hash))
    spec_to_id[spec_hash] = mid
    return mid, m


def _holding_rows(fum, plan, prices0):
    """plan: list[(ticker, frac_of_fum)]. Returns holding rows for SQLite +
    a portfolio-holdings list (with metadata + market_value) for check()."""
    rows = []; holdings = []
    for tk, frac in plan:
        meta = U.UNIVERSE_BY_TICKER[tk]
        price = prices0[tk]
        mv = round(fum * frac, 2)
        units = round(mv / price, 6)
        rows.append((None, tk, units))  # client_id filled by caller
        holdings.append({"ticker": tk, "name": meta["name"], "asset_class": meta["asset_class"],
                         "sector": meta["sector"], "region": meta["region"],
                         "liquidity_tier": meta["liquidity_tier"], "units": units,
                         "price": price, "market_value": mv})
    return rows, holdings


def _portfolio_dict(client_id, fum, holdings, cash):
    return {"client_id": client_id, "client_name": "", "adviser": "", "fum": fum,
            "holdings": holdings, "cash": cash}


def _ac_of(t):
    return U.UNIVERSE_BY_TICKER[t]["asset_class"]


def _compliant_plan(mandate, rng, drift_ac=None, drift_weight=None):
    """Greedy cap-aware plan that respects every rule dimension:
    single-name, asset-class, sector, region, top-N, drift (one-sided over),
    min_cash (floor), min_liquid_pct (tier-1 floor). Weights are fractions of
    the total portfolio (holdings + cash sum to 1.0). Cash absorbs any
    under-investment (high cash is never a breach; under-target is not a
    drift). Returns (plan list, cash_frac).

    ``drift_ac`` / ``drift_weight``: when set, phase 0 fills the drift ac
    first (up to drift_weight) so it grabs region/sector headroom before other
    asset classes consume it — used by the orange constructor to push one ac
    over target + tolerance (drift watch) without breaching any cap.
    """
    approved = [t for t in mandate["approved_universe"]
                if t not in set(mandate["excluded_tickers"]) and t != "CASH"]
    tier1 = [t for t in approved if U.UNIVERSE_BY_TICKER[t]["liquidity_tier"] == 1]
    pool = tier1 if len(tier1) >= 4 else approved
    pool = pool or approved

    cash_floor = max(mandate["min_cash"], 0.05)
    investable = 1.0 - cash_floor

    max_single = mandate["max_single_holding"]
    ac_caps = mandate["max_asset_class_weight"]
    sec_caps = mandate["max_sector_weight"]
    reg_caps = mandate["max_region_weight"]
    target = mandate["target_allocation"]
    tol = mandate["drift_tolerance"]
    topn = mandate["max_top_n_concentration"]
    min_liq = mandate["min_liquid_pct"]
    n_top = topn["n"]; limit_top = topn["limit"]

    # per-ticker cap guarantees top-N <= limit (regardless of how many tickers)
    per_ticker_cap = min(max_single * 0.9, limit_top * 0.95 / n_top)

    # per-asset-class ceiling: tighter of ac_cap and (target + drift tol).
    # The drift ac gets drift_weight as its ceiling (already under the hard
    # cap with margin — no extra 0.95 safety factor).
    ac_max = {}
    for ac, cap in ac_caps.items():
        if ac == drift_ac and drift_weight is not None:
            ac_max[ac] = drift_weight
        else:
            if ac in target:
                cap = min(cap, target[ac] + tol)
            ac_max[ac] = cap * 0.95  # safety margin

    liq_target = min_liq * 1.05  # clear the liquidity floor with margin

    plan: dict = {}
    ac_w: dict = {}
    sec_w: dict = {}
    reg_w: dict = {}
    liq_w = 0.0

    def _headroom(t):
        meta = U.UNIVERSE_BY_TICKER[t]
        ac, sec, reg = meta["asset_class"], meta["sector"], meta["region"]
        return (
            per_ticker_cap - plan.get(t, 0.0),
            ac_max.get(ac, 1.0) - ac_w.get(ac, 0.0),
            (sec_caps.get(sec, 1.0) * 0.95) - sec_w.get(sec, 0.0),
            (reg_caps.get(reg, 1.0) * 0.95) - reg_w.get(reg, 0.0),
        )

    def _add(t, w):
        if w <= 1e-9:
            return
        meta = U.UNIVERSE_BY_TICKER[t]
        ac, sec, reg = meta["asset_class"], meta["sector"], meta["region"]
        plan[t] = plan.get(t, 0.0) + w
        ac_w[ac] = ac_w.get(ac, 0.0) + w
        sec_w[sec] = sec_w.get(sec, 0.0) + w
        reg_w[reg] = reg_w.get(reg, 0.0) + w
        if meta["liquidity_tier"] == 1:
            nonlocal liq_w
            liq_w += w

    # phase 0: drift-ac first (grabs region/sector headroom before other acs)
    if drift_ac is not None and drift_weight is not None:
        drift_pool = [t for t in approved
                      if U.UNIVERSE_BY_TICKER[t]["asset_class"] == drift_ac]
        rng.shuffle(drift_pool)
        for _ in range(3):
            for t in drift_pool:
                if ac_w.get(drift_ac, 0.0) >= drift_weight - 1e-6:
                    break
                invested = sum(plan.values())
                if invested >= investable - 1e-6:
                    break
                hr = _headroom(t)
                add = min(hr[0], hr[1], hr[2], hr[3],
                          drift_weight - ac_w.get(drift_ac, 0.0),
                          investable - invested)
                _add(t, add)
            if ac_w.get(drift_ac, 0.0) >= drift_weight - 1e-6:
                break

    # phase 1: tier-1 first to clear the liquidity floor
    tier1_shuf = [t for t in pool if U.UNIVERSE_BY_TICKER[t]["liquidity_tier"] == 1]
    rng.shuffle(tier1_shuf)
    for t in tier1_shuf:
        if liq_w >= liq_target - 1e-6:
            break
        invested = sum(plan.values())
        if invested >= investable - 1e-6:
            break
        hr = _headroom(t)
        add = min(hr[0], hr[1], hr[2], hr[3],
                  liq_target - liq_w, investable - invested)
        _add(t, add)

    # phase 2: fill remaining investable from the full approved pool
    all_shuf = list(approved)
    rng.shuffle(all_shuf)
    for _ in range(4):
        for t in all_shuf:
            invested = sum(plan.values())
            if invested >= investable - 1e-6:
                break
            hr = _headroom(t)
            add = min(hr[0], hr[1], hr[2], hr[3], investable - invested)
            _add(t, add)
        if sum(plan.values()) >= investable - 1e-6:
            break

    invested = sum(plan.values())
    cash_frac = 1.0 - invested  # cash_frac >= cash_floor by construction
    plan_list = [(t, w) for t, w in plan.items() if w > 1e-9]
    return plan_list, round(cash_frac, 6)


def _build_green(mandate, fum, rng, prices0):
    plan, cash_frac = _compliant_plan(mandate, rng)
    _, holdings = _holding_rows(fum, plan, prices0)
    port = _portfolio_dict("c", fum, holdings, round(fum * cash_frac, 2))
    # repair loop: sell the worst offender entirely into cash until green.
    # selling raises cash (never a breach); tier-1 weight stays high because
    # the cap-aware plan already clears the liquidity floor with margin.
    for _ in range(12):
        res = rules_engine.check(port, mandate)
        if res["status"] == "green":
            return port["holdings"], port["cash"]
        if not res["breaches"]:
            # watches only -> orange; nudge by selling the drifted ticker
            w = res["watches"][0]
            off = w.get("offending_holdings") or []
            if off:
                tk = off[0]
                h = next((x for x in port["holdings"] if x["ticker"] == tk), None)
                if h and h["units"] > 1e-6:
                    port = apply_trades(
                        port, [{"ticker": tk, "action": "sell", "units": h["units"] * 0.5}],
                        price_lookup=lambda t: prices0.get(t),
                    )
                    continue
            break
        b = res["breaches"][0]
        off = b.get("offending_holdings") or []
        if off:
            tk = off[0]
            h = next((x for x in port["holdings"] if x["ticker"] == tk), None)
            if h and h["units"] > 1e-6:
                port = apply_trades(
                    port, [{"ticker": tk, "action": "sell", "units": h["units"]}],
                    price_lookup=lambda t: prices0.get(t),
                )
                continue
        break
    return port["holdings"], port["cash"]


def _build_red(mandate, fum, rng, prices0):
    """Inject one reliable red breach: single-name over-cap. Take a compliant
    plan, then push one approved ticker to max_single + 0.10 (always a breach),
    funding from cash and the other holdings."""
    plan, cash_frac = _compliant_plan(mandate, rng)
    approved = [t for t in mandate["approved_universe"]
                if t not in set(mandate["excluded_tickers"]) and t != "CASH"]
    max_single = mandate["max_single_holding"]
    t = rng.choice(approved) if approved else rng.choice(U.all_tickers())
    target_w = max_single + 0.10
    new_cash = max(0.01, mandate["min_cash"] * 0.5)
    other_total = 1.0 - target_w - new_cash
    if other_total < 0:
        target_w = max(0.05, 1.0 - new_cash - 0.01)
        other_total = 1.0 - target_w - new_cash
    other_plan = [(tk, w) for tk, w in plan if tk != t]
    if other_plan and other_total > 0:
        scale = other_total / sum(w for _, w in other_plan)
        other_plan = [(tk, w * scale) for tk, w in other_plan]
    elif other_total <= 0:
        other_plan = []
    new_plan = other_plan + [(t, target_w)]
    _, holdings = _holding_rows(fum, new_plan, prices0)
    return holdings, round(fum * new_cash, 2)


def _build_orange(mandate, fum, rng, prices0):
    """Drift watch: rebuild the plan with one target asset class prioritized
    (phase 0 fills it first, grabbing region/sector headroom) and its ceiling
    raised to target + tolerance + 0.04 (over the drift tolerance, under the
    hard ac cap). The greedy cap-aware filler keeps every other cap satisfied,
    so the only rule that fires is the one-sided drift watch. Verified against
    check(); falls back to the green plan if no clean orange can be
    constructed."""
    target = mandate["target_allocation"]
    tol = mandate["drift_tolerance"]
    ac_caps = mandate["max_asset_class_weight"]

    cands = [ac for ac, tgt in target.items()
             if ac_caps.get(ac, 1.0) - (tgt + tol) > 0.03]
    if not cands:
        cands = list(target)
    rng.shuffle(cands)

    for drift_ac in cands:
        tgt = target[drift_ac]
        cap = ac_caps.get(drift_ac, 1.0)
        desired = min(tgt + tol + 0.04, cap - 0.01)
        if desired <= tgt + tol + 0.005:
            continue
        plan, cash_frac = _compliant_plan(mandate, rng,
                                          drift_ac=drift_ac, drift_weight=desired)
        _, holdings = _holding_rows(fum, plan, prices0)
        port = _portfolio_dict("c", fum, holdings, round(fum * cash_frac, 2))
        res = rules_engine.check(port, mandate)
        if res["status"] == "orange":
            return holdings, port["cash"]
        # breached or stayed green -> try the next drift ac

    # fallback: cannot cleanly construct a drift watch -> return green plan
    plan, cash_frac = _compliant_plan(mandate, rng)
    _, holdings = _holding_rows(fum, plan, prices0)
    return holdings, round(fum * cash_frac, 2)


def build_book(conn: sqlite3.Connection, n: int = 34000, seed: int = 42, market_seed: int = 42) -> dict:
    rng = random.Random(seed)
    # wipe book tables (keep schema)
    for tbl in ("holdings", "portfolios", "mandates", "state", "status_history",
                "hermes_queue", "drift_events", "scan_jobs"):
        conn.execute(f"DELETE FROM {tbl}")
    conn.execute("DELETE FROM book_summary WHERE id=1")
    conn.execute("UPDATE clock SET day=0, running=0, auto_fix=0, seed=? WHERE id=1", (market_seed,))

    # tickers reference table
    conn.execute("DELETE FROM tickers")
    for u in U.UNIVERSE:
        conn.execute("INSERT OR REPLACE INTO tickers VALUES (?,?,?,?,?,?,?,?,?)",
                     (u["ticker"], u["name"], u["asset_class"], u["sector"], u["region"],
                      u["liquidity_tier"], u["base_price"], u["mu"], u["sigma"]))

    # prices at day 0
    prices0 = MK.prices_for_day(0, market_seed)
    conn.execute("DELETE FROM prices WHERE day=0")
    for tk, pr in prices0.items():
        conn.execute("INSERT OR REPLACE INTO prices (ticker, day, price) VALUES (?,0,?)", (tk, pr))

    # pre-build one mandate per template so 34k portfolios share ~8 mandate rows
    # (build_mandate jitters every call, so dedup-by-spec only fires when each
    # template is built exactly once).
    mandate_rows: list = []
    spec_to_id: dict = {}
    mandates_by_idx: dict = {}
    for tidx in range(M.template_count()):
        mid, m = _mandate_for(rng, mandate_rows, spec_to_id, tidx)
        mandates_by_idx[tidx] = (mid, m)

    # pre-check which templates can actually produce a green portfolio given
    # their (randomized) approved universe + min_liquid_pct. Some templates
    # (e.g. liquid_floored with min_liq ~0.75) may draw an approved set with
    # too few tier-1 tickers to ever clear the liquidity floor — those are
    # only ever assigned to the red/orange cohorts (the breach is the point).
    green_feasible: list = []
    for tidx in range(M.template_count()):
        mid, m = mandates_by_idx[tidx]
        probe_holdings, probe_cash = _build_green(m, 1_000_000, rng, prices0)
        probe_port = _portfolio_dict("c", 1_000_000, probe_holdings, probe_cash)
        if rules_engine.check(probe_port, m)["status"] == "green":
            green_feasible.append(tidx)
    if not green_feasible:
        green_feasible = list(range(M.template_count()))

    # pre-check which green-feasible templates can also produce a clean orange
    # (drift watch, no breach). Uses a separate probe rng so the main rng state
    # is unaffected. Templates whose target+tol >= ac_cap, or whose approved
    # universe is too small to reach the drift weight, are excluded — the
    # orange cohort only picks from templates that can actually drift.
    probe_rng = random.Random(seed + 999)
    orange_feasible: list = []
    for tidx in green_feasible:
        mid, m = mandates_by_idx[tidx]
        probe_holdings, probe_cash = _build_orange(m, 1_000_000, probe_rng, prices0)
        probe_port = _portfolio_dict("c", 1_000_000, probe_holdings, probe_cash)
        if rules_engine.check(probe_port, m)["status"] == "orange":
            orange_feasible.append(tidx)

    counts = {"green": 0, "orange": 0, "red": 0}
    breach_count_total = 0
    hist_rows = []  # day-0 status_history (so /portfolios/top works before any tick)

    # cohort assignment: shuffle a bag of intended statuses
    n_red = round(n * 0.05); n_orange = round(n * 0.15); n_green = n - n_red - n_orange
    bag = ["red"] * n_red + ["orange"] * n_orange + ["green"] * n_green
    rng.shuffle(bag)

    port_rows = []; holding_rows = []
    for i in range(n):
        client_id = f"c{i:05d}"
        fum = _fum(rng)
        cohort = bag[i]
        if cohort == "red":
            template_idx = rng.randrange(M.template_count())
        elif cohort == "orange" and orange_feasible:
            template_idx = rng.choice(orange_feasible)
        else:
            # green (or orange with no feasible drift template -> green)
            template_idx = rng.choice(green_feasible)
        mid, mandate = mandates_by_idx[template_idx]
        if cohort == "green":
            holdings, cash = _build_green(mandate, fum, rng, prices0)
        elif cohort == "orange":
            holdings, cash = _build_orange(mandate, fum, rng, prices0)
            # retry: the probe passed but this rng shuffle may not drift
            port = _portfolio_dict(client_id, fum, holdings, cash)
            if rules_engine.check(port, mandate)["status"] != "orange":
                for _ in range(3):
                    holdings, cash = _build_orange(mandate, fum, rng, prices0)
                    port = _portfolio_dict(client_id, fum, holdings, cash)
                    if rules_engine.check(port, mandate)["status"] == "orange":
                        break
        else:
            holdings, cash = _build_red(mandate, fum, rng, prices0)
        # actual status from the engine (truth) — counts reflect reality
        port = _portfolio_dict(client_id, fum, holdings, cash)
        res = rules_engine.check(port, mandate)
        status = res["status"]
        counts[status] += 1
        breach_count_total += len(res["breaches"])
        hist_rows.append((0, client_id, status, len(res["breaches"]), len(res["watches"])))
        port_rows.append((client_id, _name(rng, i), rng.choice(ADVISERS), fum, mid, cash))
        for h in holdings:
            if h["units"] > 0:
                holding_rows.append((client_id, h["ticker"], h["units"]))

    conn.executemany(
        "INSERT INTO mandates (mandate_id, spec, version, dsl, source_path, created_ts, spec_hash) "
        "VALUES (?,?,?,?,?,?,?)",
        mandate_rows,
    )
    conn.executemany("INSERT INTO portfolios (client_id, client_name, adviser, fum, mandate_id, cash) VALUES (?,?,?,?,?,?)", port_rows)
    conn.executemany("INSERT INTO holdings (client_id, ticker, units) VALUES (?,?,?)", holding_rows)
    conn.executemany(
        "INSERT OR REPLACE INTO status_history (day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        hist_rows,
    )
    # precomputed day-0 book summary (so /portfolios/summary is O(1) before any tick)
    conn.execute(
        "INSERT OR REPLACE INTO book_summary (id, day, total, green, orange, red, breach_count, updated_ts) "
        "VALUES (1, 0, ?, ?, ?, ?, ?, '')",
        (n, counts["green"], counts["orange"], counts["red"], breach_count_total),
    )
    conn.commit()
    counts["total"] = n
    return counts


def main():
    conn = storage.get_conn()
    storage.init_schema(conn); storage.migrate(conn)
    seed = int(__import__("os").environ.get("DATA_SEED", "42"))
    mseed = int(__import__("os").environ.get("MARKET_SEED", "42"))
    counts = build_book(conn, n=34000, seed=seed, market_seed=mseed)
    print(f"wrote {counts['total']} portfolios (green={counts['green']} orange={counts['orange']} red={counts['red']}) to {storage.DB_PATH}")


if __name__ == "__main__":
    main()