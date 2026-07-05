"""Run NEXUS-Micro audit against the aura-demo copy using real Anthropic API."""
from __future__ import annotations

import os
import sys
from pathlib import Path


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import anthropic
from nexus_os.agents.runner import AgentRunner
from nexus_os.config import get_settings
from nexus_os.pipeline.orchestrator import MicroOrchestrator

REPO = Path(__file__).parent / "examples" / "aura-demo"
GOAL = (
    "Audit and propose concrete improvements for the ASSURE portfolio compliance demo app "
    "in examples/aura-demo. Focus on architecture, backend quality, frontend UX, and security. "
    "Read relevant files, identify issues, and produce actionable recommendations with file paths."
)
AGENTS = [
    "engineering-software-architect",
    "engineering-backend-architect",
    "engineering-frontend-developer",
    "security-appsec-engineer",
]
MODEL = "qwen3-coder:latest"


def _verify_api() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("NEXUS_ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=64,
        messages=[{"role": "user", "content": "Say 'Ollama API ready' briefly."}],
    )
    text = response.content[0].text if response.content else ""
    print(f"API test: {text.strip()}")


def main() -> int:
    print(f"API key loaded: {bool(get_settings().anthropic_api_key)}")
    print(f"Using model: {MODEL}")
    print(f"Target repo: {REPO.resolve()}")
    _verify_api()

    runner = AgentRunner(project_path=REPO)
    # Patch the runner to use a model that exists on Anthropic's API.
    runner.settings = runner.settings.model_copy(update={"default_model": MODEL})

    orchestrator = MicroOrchestrator(REPO, runner=runner)

    state = orchestrator.init(goal=GOAL, agents=AGENTS)
    state = orchestrator.plan(state, goal=GOAL, agents=AGENTS)
    state = orchestrator.run(state)

    print(f"\nRun status: {state.status}")
    for task in state.tasks:
        print(f"\n--- {task.id}: {task.agent_slug} ({task.status}) ---")
        print(task.output[:4000] if task.output else "(no output)")
    return 0 if state.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
