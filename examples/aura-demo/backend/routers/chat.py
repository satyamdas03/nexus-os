"""Conversational Assurance router.

Provides a grounded, natural-language chat endpoint for individual portfolios.
Every answer is tied to deterministic rules-engine facts (breaches, watches, or
per_rule rows). The optional LLM only polishes prose; it may not change the
facts or introduce unsupported claims.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.conversational import chat
from core.data_loader import get_portfolio
from core.effective import effective_portfolio
from core.rules_engine import check

router = APIRouter()


class ChatBody(BaseModel):
    query: str


class GenericChatBody(ChatBody):
    portfolio: dict
    mandate: dict
    rules_result: dict


class ChatResponse(BaseModel):
    intent: str
    answer: str
    citations: list[dict]
    suggested_followups: list[str]
    grounded: bool = True


def _404(client_id: str):
    raise HTTPException(404, f"portfolio {client_id} not found")


@router.post("/portfolio/{client_id}/chat", response_model=ChatResponse)
def chat_endpoint(client_id: str, body: ChatBody):
    """Answer a natural-language question about a portfolio.

    The request must include a `query` string. The response contains the answer,
    the detected intent, and the exact engine facts (citations) that ground it.
    """
    p = get_portfolio(client_id)
    if not p:
        _404(client_id)
    eff = effective_portfolio(p)
    rr = check(eff, p["mandate"])
    result = chat(body.query, eff, p["mandate"], rr)
    return ChatResponse(
        intent=result.intent,
        answer=result.answer,
        citations=result.citations,
        suggested_followups=result.suggested_followups,
        grounded=result.grounded,
    )


@router.post("/chat", response_model=ChatResponse)
def chat_generic(body: GenericChatBody):
    """Generic chat endpoint for callers who supply portfolio + mandate + rules result.

    This is useful for the Synthetic Reality Engine, external services, or the
    Kernel-as-a-Service, which may already have the rules result and do not want
    to round-trip through SQLite.
    """
    result = chat(body.query, body.portfolio, body.mandate, body.rules_result)
    return ChatResponse(
        intent=result.intent,
        answer=result.answer,
        citations=result.citations,
        suggested_followups=result.suggested_followups,
        grounded=result.grounded,
    )
