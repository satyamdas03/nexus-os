from collections import Counter

from fastapi import APIRouter, HTTPException, Query

from assure_kernel import describe_mandate, parse_mandate
from core.data_loader import list_portfolios, get_portfolio, summary, get_conn_cached, _mandate_full
from core.effective import get_effective
from core.rules_engine import check
from agents.summarize import summarize_book

router = APIRouter()

_SEV = {"red": 3, "orange": 2, "green": 0}


def _top_reason(rules_result: dict) -> str | None:
    if rules_result["breaches"]:
        return rules_result["breaches"][0]["plain"]
    if rules_result["watches"]:
        return rules_result["watches"][0]["plain"]
    return None


def _summarize(p: dict, eff: dict, rr: dict) -> dict:
    acw = {}
    tot = sum(h["market_value"] for h in eff["holdings"]) + eff["cash"]
    for h in eff["holdings"]:
        acw[h["asset_class"]] = acw.get(h["asset_class"], 0.0) + h["market_value"] / (tot or 1)
    top_ac = max(acw, key=acw.get) if acw else None
    return {"client_id": p["client_id"], "client_name": p["client_name"], "adviser": p["adviser"],
            "fum": p["fum"], "status": rr["status"], "top_reason": _top_reason(rr),
            "top_asset_class": top_ac}


@router.get("/portfolios")
def list_portfolios_endpoint(limit: int = Query(500, ge=1, le=2000), offset: int = Query(0, ge=0)):
    out = []
    for p in list_portfolios(limit=limit, offset=offset):
        eff = get_effective(p["client_id"], seed=p)
        rr = check(eff, p["mandate"])
        out.append(_summarize(p, eff, rr))
    return out


@router.get("/portfolio/{client_id}")
def portfolio_detail(client_id: str):
    p = get_portfolio(client_id)
    if not p:
        raise HTTPException(404, "portfolio not found")
    eff = get_effective(client_id, seed=p)
    return {**p, "holdings": eff["holdings"], "cash": eff["cash"],
            "rules_result": check(eff, p["mandate"])}


@router.get("/portfolio/{client_id}/check")
def portfolio_check(client_id: str):
    p = get_portfolio(client_id)
    if not p:
        raise HTTPException(404, "portfolio not found")
    return check(get_effective(client_id, seed=p), p["mandate"])


@router.get("/portfolios/summary")
def portfolio_summary():
    return summary()


@router.get("/portfolios/summary_ai")
def portfolio_summary_ai():
    """Claude prose grounded in a bounded sample + aggregate counts (no O(n)
    LLM). Narrative is advisory; the rules engine is the final word."""
    sample = list_portfolios(limit=200, offset=0)
    rrs = [check(get_effective(p["client_id"], seed=p), p["mandate"]) for p in sample]
    return summarize_book(sample, rrs)


@router.get("/portfolios/top")
def portfolios_top(limit: int = Query(200, ge=1, le=1000)):
    """Heatmap safeguard: top-N portfolios by FUM + aggregate-rest.

    Orders strictly by FUM (largest first) so the paginated heatmap shows a
    mixed red/orange/green view on every slide. Severity is NOT used as a
    multiplier — that would push all greens to the back and make every early
    page look entirely red/amber.

    The top-N statuses are recomputed live from the effective (shadow) state so
    that approved trades are immediately visible in the heatmap without waiting
    for the next drift-monitor tick.
    """
    conn = get_conn_cached()
    latest = conn.execute("SELECT MAX(day) AS d FROM status_history").fetchone()["d"]
    if latest is None:
        latest = 0
    rows = conn.execute(
        "SELECT client_id, client_name, adviser, fum FROM portfolios ORDER BY fum DESC LIMIT ?",
        (limit,),
    ).fetchall()
    top = []
    for r in rows:
        p = get_portfolio(r["client_id"])
        eff = get_effective(r["client_id"], seed=p)
        rr = check(eff, p["mandate"])
        top.append(_summarize(p, eff, rr))
    top_ids = {r["client_id"] for r in rows}
    rest_rows = conn.execute(
        "SELECT p.fum, s.status FROM portfolios p JOIN status_history s ON s.client_id=p.client_id AND s.day=? "
        "WHERE p.client_id NOT IN ({})".format(",".join("?" for _ in top_ids) or "''"),
        (latest, *list(top_ids)),
    ).fetchall()
    rest_count = len(rest_rows)
    rest_fum = sum(r["fum"] for r in rest_rows)
    dom = Counter(r["status"] for r in rest_rows).most_common(1)
    dominant = dom[0][0] if dom else "green"
    return {"top": top, "rest": {"count": rest_count, "fum": rest_fum, "dominant_status": dominant}}

@router.get("/portfolio/{client_id}/mandate")
def portfolio_mandate(client_id: str):
    """Return the portfolio's mandate as a versioned DSL document plus human-readable rule docs."""
    p = get_portfolio(client_id)
    if not p:
        raise HTTPException(404, "portfolio not found")
    conn = get_conn_cached()
    full = _mandate_full(conn, p["mandate_id"])
    if not full:
        raise HTTPException(404, "mandate not found")
    mandate = parse_mandate(full["spec"])
    return {
        "client_id": client_id,
        "mandate_id": mandate.id,
        "version": full["version"],
        "source_path": full["source_path"],
        "created_ts": full["created_ts"],
        "spec_hash": full["spec_hash"],
        "dsl": full["dsl"],
        "docs": describe_mandate(mandate),
    }
