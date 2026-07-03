"""Render NEXUS handoff templates."""

from __future__ import annotations

from datetime import UTC, datetime


def standard_handoff(
    from_agent: str,
    to_agent: str,
    phase: int,
    task_id: str | None,
    project: str,
    current_state: str,
    deliverable_request: str,
    acceptance_criteria: list[str],
    references: list[str],
) -> str:
    """Render a standard NEXUS handoff document."""
    lines = [
        "# NEXUS Handoff Document",
        "",
        "## Metadata",
        f"| **From** | {from_agent} |",
        f"| **To** | {to_agent} |",
        f"| **Phase** | Phase {phase} |",
        f"| **Task Reference** | {task_id or 'n/a'} |",
        f"| **Timestamp** | {datetime.now(UTC).isoformat()} |",
        "",
        "## Context",
        f"**Project**: {project}",
        f"**Current State**: {current_state}",
    ]
    if references:
        lines.append("**Reference Materials**:")
        for ref in references:
            lines.append(f"- {ref}")
    lines.extend([
        "",
        "## Deliverable Request",
        f"**What is needed**: {deliverable_request}",
        "",
        "**Acceptance Criteria**:",
    ])
    for criterion in acceptance_criteria:
        lines.append(f"- [ ] {criterion}")
    lines.append("")
    return "\n".join(lines)


def qa_pass_handoff(
    from_agent: str,
    to_agent: str,
    phase: int,
    task_id: str | None,
    evidence: list[str],
) -> str:
    """Render a QA PASS handoff."""
    lines = [
        "# NEXUS QA PASS Handoff",
        "",
        f"- **From**: {from_agent}",
        f"- **To**: {to_agent}",
        f"- **Phase**: {phase}",
        f"- **Task**: {task_id or 'n/a'}",
        f"- **Timestamp**: {datetime.now(UTC).isoformat()}",
        "",
        "## Evidence",
    ]
    for item in evidence:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def qa_fail_handoff(
    from_agent: str,
    to_agent: str,
    phase: int,
    task_id: str | None,
    issues: list[dict],
    retry_count: int,
) -> str:
    """Render a QA FAIL handoff with specific issues."""
    lines = [
        "# NEXUS QA FAIL Handoff",
        "",
        f"- **From**: {from_agent}",
        f"- **To**: {to_agent}",
        f"- **Phase**: {phase}",
        f"- **Task**: {task_id or 'n/a'}",
        f"- **Retry**: {retry_count}/3",
        f"- **Timestamp**: {datetime.now(UTC).isoformat()}",
        "",
        "## Issues Found",
    ]
    for issue in issues:
        lines.append(f"### {issue.get('title', 'Issue')}")
        lines.append(f"- **Priority**: {issue.get('priority', 'Medium')}")
        lines.append(f"- **Evidence**: {issue.get('evidence', 'N/A')}")
        lines.append(f"- **Fix instruction**: {issue.get('fix', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def escalation_handoff(
    from_agent: str,
    phase: int,
    task_id: str | None,
    failure_history: list[dict],
    impact: str,
) -> str:
    """Render an escalation report."""
    lines = [
        "# NEXUS Escalation Report",
        "",
        f"- **From**: {from_agent}",
        f"- **Phase**: {phase}",
        f"- **Task**: {task_id or 'n/a'}",
        f"- **Timestamp**: {datetime.now(UTC).isoformat()}",
        "",
        "## Failure History",
    ]
    for attempt in failure_history:
        lines.append(f"- Attempt {attempt.get('attempt')}: {attempt.get('summary')}")
    lines.extend([
        "",
        f"## Impact\n{impact}",
        "",
        "## Recommended Resolution",
        "- Reassign to a different agent",
        "- Decompose the task into smaller pieces",
        "- Defer to a future sprint",
        "- Accept with documented limitations",
        "",
    ])
    return "\n".join(lines)
