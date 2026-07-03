"""Evidence Pack router — read-only compliance proof artifact endpoints.

Provides JSON and print-ready HTML evidence packs for individual portfolios.
This router does not mutate portfolio state, approve trades, or write to the
audit log.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from agents.evidence import build_portfolio_evidence

router = APIRouter()


@router.get("/evidence/portfolio/{client_id}")
def portfolio_evidence_json(client_id: str):
    """Return a structured evidence pack for a single portfolio."""
    try:
        evidence = build_portfolio_evidence(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"portfolio {client_id} not found")
    # The pre-rendered HTML key is internal; strip it from the JSON response
    # so consumers receive only the structured data contract.
    return {k: v for k, v in evidence.items() if k != "_html"}


@router.get("/evidence/portfolio/{client_id}/html")
def portfolio_evidence_html(client_id: str):
    """Return a print-ready HTML evidence pack for a single portfolio."""
    try:
        evidence = build_portfolio_evidence(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"portfolio {client_id} not found")
    return HTMLResponse(content=evidence["_html"], status_code=200)
