from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel
from core.data_loader import get_portfolio
from core.market import get_clock
from core.rules_engine import check
from core.effective import effective_portfolio, record_trades
from core.trades import apply_trades
from core.auth import get_current_user, require_mutation
from agents.explain import explain
from agents.remediate import remediate
from agents.reflect import suggest, adopt
from routers.audit import append_audit

router = APIRouter()


class ApproveBody(BaseModel):
    trades: list[dict] = []
    rationale: str = ""
    breach_type: str | None = None
    choice: str | None = None


class ExplainBody(BaseModel):
    metric: str | None = None


class VerifyBody(BaseModel):
    trades: list[dict] = []


class AdoptBody(BaseModel):
    breach_type: str
    preference: str
    rationale: str


def _404(cid: str):
    raise HTTPException(404, f"portfolio {cid} not found")


def _log(client_id: str, action_type: str, actor: str, tier: str, payload: dict, rationale: str = ""):
    append_audit({"timestamp": datetime.now(timezone.utc).isoformat(),
                  "client_id": client_id, "action_type": action_type, "actor": actor,
                  "tier": tier, "payload": payload, "rationale": rationale,
                  "rules_check_result": None, "version": "0.1.0"})


@router.post("/portfolio/{client_id}/explain")
def explain_endpoint(client_id: str, body: ExplainBody | None = None, _user=Depends(get_current_user)):
    p = get_portfolio(client_id)
    if not p:
        _404(client_id)
    eff = effective_portfolio(p)
    rr = check(eff, p["mandate"])
    metric = body.metric if body else None
    out = explain(eff, rr, metric=metric)
    _log(client_id, "explain", "ai", "advisory", out, "Explainer agent")
    return out


@router.post("/portfolio/{client_id}/verify")
def verify_endpoint(client_id: str, body: VerifyBody, _user=Depends(get_current_user)):
    """Verify arbitrary trades against the mandate WITHOUT persisting.

    Enables: editable workbench live re-check, Hermes row expand, manual what-if.
    The rules engine — not this endpoint — is the final word.
    """
    p = get_portfolio(client_id)
    if not p:
        _404(client_id)
    eff = effective_portfolio(p)
    candidate = apply_trades(eff, body.trades)
    rr = check(candidate, p["mandate"])
    _log(client_id, "verify", "engine", "deterministic",
         {"trades": body.trades, "prior_status": check(eff, p["mandate"])["status"],
          "candidate_status": rr["status"]}, "rules_engine what-if verify")
    return rr


@router.post("/portfolio/{client_id}/remediate")
def remediate_endpoint(client_id: str, _user=Depends(require_mutation)):
    p = get_portfolio(client_id)
    if not p:
        _404(client_id)
    eff = effective_portfolio(p)
    rr = check(eff, p["mandate"])
    out = remediate(eff, rr, mandate=p["mandate"])
    _log(client_id, "remediate_propose", "ai", "advisory", {"trades": out["trades"]}, "Remediation agent")
    _log(client_id, "verify", "engine", "deterministic", {"status": out["verification"]["status"]}, "rules_engine")
    return out


@router.post("/portfolio/{client_id}/approve")
def approve_endpoint(client_id: str, body: ApproveBody, _user=Depends(require_mutation)):
    p = get_portfolio(client_id)
    if not p:
        _404(client_id)
    eff = effective_portfolio(p)
    prior = check(eff, p["mandate"])
    # Apply the human-approved trades to the shadow state. The rules engine —
    # not this endpoint — decides the new status by re-checking the effective
    # portfolio after the trades land.
    record_trades(client_id, body.trades, rationale=body.rationale or "approved by manager")
    from core.effective import get_effective
    new_eff = get_effective(client_id, seed=p)
    new_rr = check(new_eff, p["mandate"])
    _log(client_id, "approve", "human", "deterministic",
         {"trades": body.trades, "prior_status": prior["status"], "new_status": new_rr["status"],
          "breach_type": body.breach_type, "choice": body.choice, "day": get_clock()["day"]},
         body.rationale or "approved by manager")
    _log(client_id, "verify", "engine", "deterministic",
         {"status": new_rr["status"], "breaches": len(new_rr["breaches"]), "watches": len(new_rr["watches"])},
         "rules_engine re-check after approved trades")
    return {"ok": True, "client_id": client_id,
            "prior_status": prior["status"], "new_status": new_rr["status"],
            "rules_result": new_rr}


@router.post("/portfolio/{client_id}/reflect")
def reflect_endpoint(client_id: str, _user=Depends(require_mutation)):
    s = suggest(client_id)
    if s:
        _log(client_id, "reflect_suggest", "ai", "advisory", s, "learning loop")
    return {"suggestion": s}


@router.post("/preferences/adopt")
def adopt_endpoint(body: AdoptBody, _user=Depends(require_mutation)):
    pref_path = Path(__file__).parent.parent / "data" / "preferences.jsonl"
    existing = pref_path.read_text().splitlines() if pref_path.exists() else []
    version = len([l for l in existing if l.strip()]) + 1
    adopt({"breach_type": body.breach_type, "preference": body.preference,
           "rationale": body.rationale, "version": version})
    _log("global", "reflect_adopt", "human", "advisory", {"preference": body.preference}, body.rationale)
    return {"ok": True, "version": version}