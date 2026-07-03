"""Prompt templates for agent activation."""

from __future__ import annotations

from nexus_os.pipeline.models import Task


def activation_prompt(task: Task, project_path: str, goal: str) -> str:
    """Render a NEXUS activation prompt for an agent task."""
    lines = [
        f"You are the {task.agent_slug} agent working within the NEXUS pipeline.",
        "",
        f"Project path: {project_path}",
        f"Pipeline goal: {goal}",
        f"Task ID: {task.id}",
        f"Task description: {task.description}",
    ]
    if task.depends_on:
        lines.append(f"Depends on tasks: {', '.join(task.depends_on)}")
    lines.extend([
        "",
        "Instructions:",
        "1. Read any relevant reference files in the project.",
        "2. Produce a concrete, measurable deliverable.",
        "3. Do not add scope beyond the task description.",
        "4. When complete, summarize what you did and any evidence.",
    ])
    return "\n".join(lines)
