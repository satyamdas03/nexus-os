"""Voice router for ASSURE Conversational Assurance.

Generates LiveKit access tokens for voice rooms. The conversational brain stays
in `agents.conversational`; this endpoint only handles audio transport tokens.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user
from agents.voice import create_token, is_configured

router = APIRouter()


class VoiceTokenResponse(BaseModel):
    token: str
    url: str
    room: str
    identity: str
    configured: bool


class VoiceStatusResponse(BaseModel):
    configured: bool
    message: str


@router.get("/voice/status")
def voice_status(_user=Depends(get_current_user)):
    """Report whether LiveKit voice is configured on this deployment."""
    if is_configured():
        return VoiceStatusResponse(configured=True, message="LiveKit voice is configured.")
    return VoiceStatusResponse(
        configured=False,
        message="LiveKit voice is not configured. The frontend will fall back to browser speech APIs.",
    )


@router.post("/voice/token/{client_id}", response_model=VoiceTokenResponse)
def voice_token(client_id: str, _user=Depends(get_current_user)):
    """Create a LiveKit access token for a conversational assurance voice session."""
    try:
        token = create_token(client_id)
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc))
    return VoiceTokenResponse(
        token=token.token,
        url=token.url,
        room=token.room,
        identity=token.identity,
        configured=True,
    )
