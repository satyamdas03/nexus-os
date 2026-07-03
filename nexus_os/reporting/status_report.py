"""Render NEXUS Pipeline Status Reports."""

from __future__ import annotations

from nexus_os.pipeline.models import PipelineState


def render_status_report(state: PipelineState) -> str:
    """Render a markdown status report."""
    lines = [
        "# NEXUS Pipeline Status Report",
        "",
        f"**Mode**: {state.mode}",
        f"**Phase**: {state.phase}",
        f"**Goal**: {state.goal}",
        f"**Status**: {state.status}",
        f"**Current Task**: {state.current_task_id or 'None'}",
        "",
        "## Tasks",
        "| ID | Agent | Status | Attempts | Verdict |",
        "|---|---|---|---|---|",
    ]
    for task in state.tasks:
        lines.append(
            f"| {task.id} | {task.agent_slug} | {task.status} | {task.attempts} | {task.verdict or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)
