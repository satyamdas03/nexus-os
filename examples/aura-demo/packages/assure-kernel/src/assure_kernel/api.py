"""FastAPI router for Kernel-as-a-Service.

The ASSURE kernel is exposed as a stateless, read-only HTTP service.
Every endpoint is deterministic and versioned so that external systems can
treat it as an assurance oracle.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from assure_kernel.service import check_portfolio, verify_trades, explain_mandate
from assure_kernel import __version__ as kernel_version

router = APIRouter(prefix="/v1")


class HealthResponse(BaseModel):
    status: str = "ok"
    kernel_version: str
    service: str = "assure-kernel"


class EvaluateRequest(BaseModel):
    portfolio: dict
    mandate: dict


class EvaluateResponse(BaseModel):
    status: str
    breaches: list[dict]
    watches: list[dict]
    per_rule: list[dict]


class VerifyRequest(BaseModel):
    portfolio: dict
    mandate: dict
    trades: list[dict] = Field(default_factory=list)


class ExplainRequest(BaseModel):
    mandate: dict


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok", "kernel_version": kernel_version, "service": "assure-kernel"}


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest) -> dict:
    """Run a full deterministic rules check on a portfolio + mandate."""
    try:
        result = check_portfolio(req.portfolio, req.mandate)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Evaluation failed: {exc}") from exc
    return result.to_legacy()


@router.post("/verify", response_model=EvaluateResponse)
def verify(req: VerifyRequest) -> dict:
    """What-if trade gate: apply trades and return the post-trade verdict."""
    try:
        result = verify_trades(req.portfolio, req.mandate, req.trades)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Verification failed: {exc}") from exc
    return result.to_legacy()


@router.post("/explain")
def explain(req: ExplainRequest) -> dict:
    """Return deterministic, grounded documentation for a mandate."""
    try:
        return explain_mandate(req.mandate)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Explain failed: {exc}") from exc
