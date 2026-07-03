"""LLM-backed agent runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus_os.agents.prompts import activation_prompt
from nexus_os.config import Settings, get_settings
from nexus_os.pipeline.models import Task, Verdict


class AgentRunner:
    """Run an agent task against an LLM and parse the result."""

    def __init__(self, settings: Settings | None = None, project_path: Path | None = None):
        self.settings = settings or get_settings()
        self.project_path = project_path or Path.cwd()
        self._client: Any | None = None

    def _client_instance(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError:
            return None
        if not self.settings.anthropic_api_key:
            return None
        self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    def __call__(self, task: Task, state: Any) -> tuple[str, Verdict, list[str]]:
        """Execute a task and return (output, verdict, evidence)."""
        client = self._client_instance()
        prompt = activation_prompt(task, str(self.project_path), state.goal)
        if client is None:
            return self._mock_result(task, prompt)

        try:
            response = client.messages.create(
                model=self.settings.default_model,
                max_tokens=4096,
                system="You are a specialist agent executing a NEXOS OS task. Be concise and evidence-based.",
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text if response.content else ""
            return self._parse_content(content)
        except Exception as exc:  # pragma: no cover - defensive
            return (
                f"Agent execution failed: {exc}",
                Verdict.FAIL,
                [f"Exception during LLM call: {exc}"],
            )

    def _mock_result(self, task: Task, prompt: str) -> tuple[str, Verdict, list[str]]:
        """Dry-run result when no API key is available."""
        lines = [
            f"## Mock execution for {task.agent_slug}",
            "",
            "No ANTHROPIC_API_KEY available; this is a dry-run output.",
            "",
            "### Activation prompt (truncated)",
            prompt[:500] + "..." if len(prompt) > 500 else prompt,
            "",
            "### Simulated verdict",
            "PASS (dry-run)",
        ]
        return "\n".join(lines), Verdict.PASS, ["Dry-run evidence: no real execution."]

    def _parse_content(self, content: str) -> tuple[str, Verdict, list[str]]:
        """Extract a verdict and evidence from agent output."""
        upper = content.upper()
        if "VERDICT: PASS" in upper or "PASS" in upper:
            verdict = Verdict.PASS
        elif "VERDICT: FAIL" in upper or "FAIL" in upper:
            verdict = Verdict.FAIL
        elif "NEEDS_WORK" in upper:
            verdict = Verdict.NEEDS_WORK
        else:
            verdict = Verdict.PASS
        evidence = ["Agent produced a text response; manual review recommended."]
        return content, verdict, evidence
