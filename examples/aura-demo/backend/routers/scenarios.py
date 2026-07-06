"""Synthetic stress-scenario API for the ASSURE kernel.

Endpoints:
  GET  /scenarios                    — list built-in stress scenarios.
  POST /scenarios/apply              — apply a scenario to a real portfolio.
  POST /scenarios/sweep              — start an async adversarial sweep job.
  GET  /scenarios/sweep/{job_id}     — poll sweep status + JSON result.
  GET  /scenarios/sweep/{job_id}/report.html — deterministic HTML report.

All scenario logic lives in the reusable `assure_kernel.synthetic` package.
The backend only wires portfolio state, mandates, and persistence.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from assure_kernel import evaluate_portfolio
from assure_kernel.models import Portfolio
from assure_kernel.synthetic.adversary import Adversary
from assure_kernel.synthetic.report import StressReport
from assure_kernel.synthetic.scenarios import list_scenarios, stress_portfolio
from core.auth import require_mutation
from core.data_loader import get_conn_cached, get_portfolio
from core.storage import init_schema

router = APIRouter()


class _ScenarioJobStore:
    """Thin persistence layer for async scenario sweep jobs (SQLite-backed)."""

    def _conn(self):
        conn = get_conn_cached()
        init_schema(conn)
        return conn

    def insert(
        self,
        job_id: str,
        kind: str,
        started_ts: str,
    ) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT INTO scenario_jobs (job_id, kind, status, started_ts) VALUES (?, ?, ?, ?)",
            (job_id, kind, "running", started_ts),
        )
        conn.commit()

    def update_done(
        self,
        job_id: str,
        done_ts: str,
        result_json: Optional[str] = None,
        report_html: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        conn = self._conn()
        status = "failed" if error else "done"
        conn.execute(
            "UPDATE scenario_jobs SET status=?, done_ts=?, result_json=?, report_html=?, error=? WHERE job_id=?",
            (status, done_ts, result_json, report_html, error, job_id),
        )
        conn.commit()

    def get(self, job_id: str) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM scenario_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        return {
            "job_id": row["job_id"],
            "kind": row["kind"],
            "status": row["status"],
            "started_ts": row["started_ts"],
            "done_ts": row["done_ts"],
            "result_json": row["result_json"],
            "report_html": row["report_html"],
            "error": row["error"],
        }


_store = _ScenarioJobStore()


class ApplyBody(BaseModel):
    client_id: str
    scenario_id: str
    seed: Optional[int] = None


class SweepBody(BaseModel):
    client_id: str
    scenario_ids: list[str] = Field(default_factory=list)
    n: int = Field(default=200, ge=10, le=5000)
    seed: int = 42
    record_limit: int = Field(default=100, ge=0, le=1000)


class StressPortfolioBody(BaseModel):
    client_id: str
    scenario_ids: list[str] = Field(default_factory=list)


def _portfolio_total_value(portfolio: dict) -> float:
    holdings_value = sum(h.get("market_value", 0.0) for h in portfolio.get("holdings", []))
    return holdings_value + portfolio.get("cash", 0.0)


def _serialize_rules_result(result) -> dict:
    """Return the legacy aura-demo shape for a kernel RulesResult."""
    return result.to_legacy()


@router.get("/scenarios")
def scenarios_list():
    """Return metadata for every built-in stress scenario."""
    return {"scenarios": list_scenarios()}


@router.post("/scenarios/apply")
def scenarios_apply(body: ApplyBody, _user=Depends(require_mutation)):
    """Apply a single stress scenario to a real portfolio and compare
    the rules verdict before/after the shock.

    The live book is never mutated — this is a read-only what-if.
    """
    portfolio = get_portfolio(body.client_id)
    if portfolio is None:
        raise HTTPException(404, f"portfolio {body.client_id} not found")
    if not portfolio.get("mandate"):
        raise HTTPException(400, "portfolio has no mandate")

    try:
        portfolio_model = Portfolio.model_validate(portfolio)
        stressed = stress_portfolio(portfolio_model, body.scenario_id, seed=body.seed)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, f"invalid portfolio: {exc}") from exc

    baseline_result = evaluate_portfolio(portfolio_model, portfolio["mandate"])
    stressed_result = evaluate_portfolio(stressed, portfolio["mandate"])

    baseline_total = _portfolio_total_value(portfolio)
    stressed_total = stressed.total_value
    value_change_pct = (
        (stressed_total - baseline_total) / baseline_total if baseline_total else 0.0
    )

    return {
        "client_id": body.client_id,
        "scenario_id": body.scenario_id,
        "baseline_status": baseline_result.to_legacy()["status"],
        "stressed_status": stressed_result.to_legacy()["status"],
        "baseline_value": round(baseline_total, 2),
        "stressed_value": round(stressed_total, 2),
        "value_change_pct": round(value_change_pct, 4),
        "stressed_portfolio": stressed.model_dump(exclude_none=True),
        "baseline_rules_result": _serialize_rules_result(baseline_result),
        "stressed_rules_result": _serialize_rules_result(stressed_result),
    }


@router.post("/scenarios/stress-portfolio")
def scenarios_stress_portfolio(body: StressPortfolioBody, _user=Depends(require_mutation)):
    """Run every selected scenario (or all scenarios) against a real portfolio
    and return a compact status map for each shock.
    """
    portfolio = get_portfolio(body.client_id)
    if portfolio is None:
        raise HTTPException(404, f"portfolio {body.client_id} not found")
    if not portfolio.get("mandate"):
        raise HTTPException(400, "portfolio has no mandate")

    scenario_ids = body.scenario_ids or [s["id"] for s in list_scenarios()]
    baseline_total = _portfolio_total_value(portfolio)
    portfolio_model = Portfolio.model_validate(portfolio)
    baseline_result = evaluate_portfolio(portfolio_model, portfolio["mandate"]).to_legacy()
    results = []
    for sid in scenario_ids:
        try:
            stressed = stress_portfolio(portfolio_model, sid, seed=42)
        except KeyError:
            continue
        rr = evaluate_portfolio(stressed, portfolio["mandate"]).to_legacy()
        results.append({
            "scenario_id": sid,
            "stressed_status": rr["status"],
            "stressed_value": round(stressed.total_value, 2),
            "value_change_pct": round(
                (stressed.total_value - baseline_total) / baseline_total if baseline_total else 0.0, 4
            ),
            "breach_count": len(rr.get("breaches", [])),
            "watch_count": len(rr.get("watches", [])),
        })

    return {
        "client_id": body.client_id,
        "baseline_status": baseline_result["status"],
        "baseline_value": round(baseline_total, 2),
        "scenarios": results,
    }


@router.post("/scenarios/sweep")
def scenarios_sweep(background: BackgroundTasks, body: SweepBody, _user=Depends(require_mutation)):
    """Launch an async adversarial sweep using the portfolio's mandate.

    The adversary generates `n` synthetic portfolios per selected scenario,
    stresses each one, and counts rule breaches deterministically. Poll
    GET /scenarios/sweep/{job_id} for the JSON result, or open
    /scenarios/sweep/{job_id}/report.html for a print-ready report.
    """
    portfolio = get_portfolio(body.client_id)
    if portfolio is None:
        raise HTTPException(404, f"portfolio {body.client_id} not found")
    if not portfolio.get("mandate"):
        raise HTTPException(400, "portfolio has no mandate")

    scenario_ids = body.scenario_ids or [s["id"] for s in list_scenarios()]
    job_id = uuid.uuid4().hex
    started_ts = datetime.now(timezone.utc).isoformat()
    _store.insert(job_id, "sweep", started_ts)
    background.add_task(
        _run_sweep_job,
        job_id,
        portfolio["mandate"],
        scenario_ids,
        body.n,
        body.seed,
        body.record_limit,
    )
    return {"job_id": job_id}


def _run_sweep_job(
    job_id: str,
    mandate: dict,
    scenario_ids: list[str],
    n: int,
    seed: int,
    record_limit: int,
) -> None:
    try:
        result = Adversary(
            mandate=mandate,
            scenarios=scenario_ids,
            record_limit=record_limit,
        ).sweep(n=n, seed=seed)
        report = StressReport(result=result)
        _store.update_done(
            job_id,
            datetime.now(timezone.utc).isoformat(),
            result_json=json.dumps(report.json),
            report_html=report.to_html(),
        )
    except Exception as e:  # noqa: BLE001 — record failure on the job row
        _store.update_done(
            job_id,
            datetime.now(timezone.utc).isoformat(),
            error=str(e),
        )


@router.get("/scenarios/sweep/{job_id}")
def scenarios_sweep_status(job_id: str):
    """Poll an async sweep job; returns JSON result when done."""
    row = _store.get(job_id)
    if row is None:
        raise HTTPException(404, "sweep job not found")
    result = None
    if row.get("result_json"):
        try:
            result = json.loads(row["result_json"])
        except json.JSONDecodeError:
            pass
    return {
        "job_id": row["job_id"],
        "kind": row["kind"],
        "status": row["status"],
        "started_ts": row["started_ts"],
        "done_ts": row["done_ts"],
        "error": row["error"],
        "result": result,
    }


@router.get("/scenarios/sweep/{job_id}/report.html")
def scenarios_sweep_report_html(job_id: str):
    """Return the deterministic HTML report for a completed sweep job."""
    row = _store.get(job_id)
    if row is None:
        raise HTTPException(404, "sweep job not found")
    html = row.get("report_html")
    if not html:
        raise HTTPException(404, "report not ready")
    return Response(content=html, media_type="text/html")
