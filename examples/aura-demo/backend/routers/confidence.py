"""Confidence / confirmation prediction card API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth import get_current_user_or_dev
from core.confidence import score_confidence

router = APIRouter()


class ConfidenceRequest(BaseModel):
    trades: list[dict] = []


@router.post("/confidence/{client_id}")
def confidence(client_id: str, body: ConfidenceRequest, _user=Depends(get_current_user_or_dev)):
    result = score_confidence(client_id, body.trades)
    return result.__dict__
