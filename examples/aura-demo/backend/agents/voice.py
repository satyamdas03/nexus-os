"""LiveKit voice adapter for ASSURE Conversational Assurance.

This module generates LiveKit access tokens so a frontend can join a voice room
where the user speaks questions and hears grounded answers. The actual
conversational intelligence lives in `agents.conversational`; the voice layer
only transports audio.

Environment variables:
    LIVEKIT_URL       — LiveKit server URL (e.g., wss://xxx.livekit.cloud)
    LIVEKIT_API_KEY   — LiveKit API key
    LIVEKIT_API_SECRET — LiveKit API secret

If these are not set, the token endpoint returns a clear error and the frontend
can fall back to browser SpeechSynthesis / SpeechRecognition.
"""

import os
from dataclasses import dataclass

try:
    from livekit.api import AccessToken, VideoGrants
    _HAS_LIVEKIT = True
except Exception:  # pragma: no cover — livekit-server-sdk is optional
    _HAS_LIVEKIT = False


@dataclass
class VoiceToken:
    token: str
    url: str
    room: str
    identity: str


def _env(key: str) -> str | None:
    return os.environ.get(key)


def is_configured() -> bool:
    """Return True when LiveKit credentials are present."""
    return bool(_env("LIVEKIT_URL") and _env("LIVEKIT_API_KEY") and _env("LIVEKIT_API_SECRET") and _HAS_LIVEKIT)


def create_token(
    client_id: str,
    room_name: str | None = None,
    identity: str | None = None,
    ttl_seconds: int = 3600,
) -> VoiceToken:
    """Create a LiveKit access token for a conversational assurance session.

    Args:
        client_id: Portfolio/client identifier used to namespace the room.
        room_name: Optional explicit room name; defaults to "assure-{client_id}".
        identity: Optional participant identity; defaults to "user-{client_id}".
        ttl_seconds: Token lifetime.

    Returns:
        VoiceToken with token, server URL, room, and identity.

    Raises:
        RuntimeError: if LiveKit is not configured or the SDK is missing.
    """
    url = _env("LIVEKIT_URL")
    api_key = _env("LIVEKIT_API_KEY")
    api_secret = _env("LIVEKIT_API_SECRET")
    if not url or not api_key or not api_secret:
        raise RuntimeError("LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.")
    if not _HAS_LIVEKIT:
        raise RuntimeError(
            "LiveKit server SDK is not installed. Run: pip install livekit-server-sdk"
        )

    room = room_name or f"assure-{client_id}"
    identity = identity or f"user-{client_id}"
    grants = VideoGrants(room_join=True, room=room)
    token = AccessToken(api_key, api_secret).with_identity(identity).with_grants(grants).to_jwt()
    return VoiceToken(token=token, url=url, room=room, identity=identity)
