"""Confidence / confirmation prediction card API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agents.hermes.loop import simulate_book
from core.auth import get_current_user
from core.confidence import score_confidence

router = APIRouter()


class ConfidenceRequest(BaseModel):
    trades: list[dict] = []


@router.post("/confidence/{client_id}")
def confidence(client_id: str, body: ConfidenceRequest, _user=Depends(get_current_user)):
    result = score_confidence(client_id, body.trades, simulate_fn=simulate_book)
    return result.__dict__
