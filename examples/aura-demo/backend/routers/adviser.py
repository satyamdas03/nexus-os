"""AI Investment Manager adviser router.

Provides:
  POST /adviser/whiteboard/{client_id}  — structured breach + proposed fix payload
  POST /adviser/chat                    — grounded chat answer (advisory only)
  POST /adviser/session                 — LiveKit voice-session token

All endpoints are read-only with respect to portfolio state. Chat cannot
execute trades.
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user, check_client_scope
from agents.adviser.whiteboard import build_whiteboard
from agents.adviser.prompts import _ADVISER_SYSTEM, chat_prompt
from agents.llm import get_llm
from agents.voice import create_token, is_configured

router = APIRouter()


class ChatRequest(BaseModel):
    client_id: str
    query: str


class SessionRequest(BaseModel):
    client_id: str


@router.post("/adviser/whiteboard/{client_id}")
def whiteboard(client_id: str, user=Depends(get_current_user)):
    check_client_scope(user, client_id)
    return build_whiteboard(client_id)


@router.post("/adviser/chat")
def chat(body: ChatRequest, user=Depends(get_current_user)):
    check_client_scope(user, body.client_id)
    wb = build_whiteboard(body.client_id)
    # Lightweight execution-refusal guard. The LLM is advisory only; even a
    # well-intentioned prompt asking to trade must be stopped at the API layer.
    lowered = body.query.lower()
    if any(k in lowered for k in ("execute", "place order", "buy now", "sell now", "do the trade")):
        answer = (
            "I can't execute trades. I'm an advisory layer only. "
            "Please use the Remediation Workbench to review and approve any proposed trades."
        )
    else:
        prompt = chat_prompt(wb, body.query)
        answer = get_llm().complete(_ADVISER_SYSTEM, prompt)
    return {"answer": answer, "whiteboard": wb}


@router.post("/adviser/session")
def session(body: SessionRequest, user=Depends(get_current_user)):
    check_client_scope(user, body.client_id)
    if not is_configured():
        raise HTTPException(status_code=503, detail="LiveKit not configured")
    token = create_token(
        body.client_id,
        room_name=f"adviser-{body.client_id}",
        identity="adviser-user",
    )
    return {
        "token": token.token,
        "url": token.url,
        "room": token.room,
        "identity": token.identity,
    }
