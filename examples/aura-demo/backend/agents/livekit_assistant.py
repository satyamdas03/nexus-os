"""LiveKit voice assistant for ASSURE Conversational Assurance.

This module is a standalone, optional voice-agent entry point. When run, it
connects to a LiveKit room as a bot participant, listens to the user's speech,
transcribes it, calls the deterministic conversational assurance agent
(`agents.conversational.chat`), and speaks the grounded answer back.

It is NOT imported by `main.py`; it must be launched separately so that the rest
of the backend starts even when `livekit-agents` is not installed.

Environment variables:
    LIVEKIT_URL         — LiveKit server URL (e.g., wss://xxx.livekit.cloud)
    LIVEKIT_API_KEY     — LiveKit API key
    LIVEKIT_API_SECRET  — LiveKit API secret
    DEEPGRAM_API_KEY    — Deepgram STT API key
    OPENAI_API_KEY      — OpenAI TTS API key
    ASSURE_API_BASE     — URL of this backend (default http://127.0.0.1:8000)
"""

import os
import sys

from .voice import is_configured

try:
    # livekit-agents and its speech plugins are optional.
    from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
    from livekit.plugins import deepgram, openai  # type: ignore

    _HAS_AGENTS = True
except Exception:  # pragma: no cover — optional agent stack
    _HAS_AGENTS = False


def _env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def _assure_chat_url(client_id: str) -> str:
    base = (_env("ASSURE_API_BASE") or "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/portfolio/{client_id}/chat"


async def _answer_query(client_id: str, query: str) -> str:
    """Call the local ASSURE chat endpoint with a deterministic query."""
    import httpx

    url = _assure_chat_url(client_id)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"query": query})
        response.raise_for_status()
        data = response.json()
    return data.get("answer", "I didn't get an answer from the assurance engine.")


if _HAS_AGENTS:

    class AssureVoiceAgent(Agent):
        """Minimal LiveKit voice agent that forwards transcribed speech to ASSURE.

        The real reasoning happens in `agents.conversational`; this agent only
        satisfies the livekit-agents LLM node by returning the grounded answer.
        """

        def __init__(self, client_id: str) -> None:
            self._assure_client_id = client_id
            super().__init__(
                instructions=(
                    "You are ASSURE, a deterministic assurance assistant for wealth management. "
                    "Answer only from the rules-engine facts returned by the backend."
                ),
                stt=deepgram.STT(),
                llm=None,  # we override llm_node to call ASSURE directly
                tts=openai.TTS(),
            )

        async def llm_node(
            self,
            chat_ctx,
            tools,
            model_settings,
        ):
            # Find the most recent user message in the history.
            user_items = [
                m for m in chat_ctx.items if getattr(m, "role", None) == "user"
            ]
            query = (
                user_items[-1].content
                if user_items and getattr(user_items[-1], "content", None)
                else "Summarize the portfolio"
            )
            answer = await _answer_query(self._assure_client_id, query)
            yield answer


async def _entrypoint(ctx: JobContext) -> None:
    """LiveKit worker entrypoint.

    The client_id is read from the ASSURE_CLIENT_ID environment variable because
    the worker is started per portfolio session.
    """
    client_id = _env("ASSURE_CLIENT_ID")
    if not client_id:
        raise RuntimeError(
            "ASSURE_CLIENT_ID is not set. Start the agent with --client-id <id>."
        )
    await ctx.connect()
    session = AgentSession()
    await session.start(agent=AssureVoiceAgent(client_id), room=ctx.room)


def run_agent(client_id: str) -> None:
    """Launch the LiveKit voice agent for a specific client/portfolio.

    Usage:
        python -m agents.livekit_assistant --client-id C123

    This blocks forever and processes LiveKit jobs. Requires `livekit-agents`
    and the speech plugins to be installed.
    """
    if not is_configured():
        raise RuntimeError(
            "LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."
        )
    if not _HAS_AGENTS:
        raise RuntimeError(
            "livekit-agents is not installed. Run: "
            "pip install livekit-agents livekit-plugins-deepgram livekit-plugins-openai"
        )
    if not _env("DEEPGRAM_API_KEY"):
        raise RuntimeError("DEEPGRAM_API_KEY is not set.")
    if not _env("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    os.environ["ASSURE_CLIENT_ID"] = client_id
    # livekit-agents' own CLI parses sys.argv and needs a subcommand like
    # `start` or `dev`. We already consumed --client-id, so reconstruct argv
    # to contain only the program name plus the default subcommand.
    original_argv = sys.argv
    subcommand = "start"
    if len(original_argv) > 1 and original_argv[-1] in (
        "start",
        "dev",
        "console",
        "connect",
        "download-files",
    ):
        subcommand = original_argv[-1]
    sys.argv = [original_argv[0], subcommand]
    try:
        cli.run_app(WorkerOptions(entrypoint_fnc=_entrypoint))
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ASSURE LiveKit voice assistant")
    parser.add_argument(
        "--client-id", required=True, help="Portfolio client_id to answer about"
    )
    args = parser.parse_args()

    try:
        run_agent(args.client_id)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
