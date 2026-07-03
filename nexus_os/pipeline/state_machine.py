"""NEXUS phase state machine and transition logic."""

from __future__ import annotations

from nexus_os.pipeline.models import NEXUS_PHASES, PipelineState, Task, Verdict


def get_phase(phase_number: int) -> dict:
    """Return phase metadata by number."""
    for phase in NEXUS_PHASES:
        if phase.number == phase_number:
            return phase.model_dump()
    return {"number": phase_number, "name": "Unknown", "gate_keeper": None}


def advance_phase(state: PipelineState) -> bool:
    """Advance to the next phase if the current phase gate is satisfied."""
    current = state.phase
    if current >= 6:
        return False
    # For MVP, allow phase advancement when all tasks in current phase are done.
    phase_tasks = [t for t in state.tasks if t.metadata.get("phase", 3) == current]
    if not phase_tasks or all(t.status == "done" for t in phase_tasks):
        state.phase = current + 1
        return True
    return False


def evaluate_task_after_qa(task: Task, verdict: Verdict, evidence: list[str]) -> None:
    """Update a task based on a QA verdict."""
    task.attempts += 1
    task.evidence.extend(evidence)
    task.verdict = verdict
    if verdict == Verdict.PASS:
        task.status = "done"
    elif task.can_retry():
        task.status = "pending"
    else:
        task.status = "failed"


def all_tasks_done(state: PipelineState) -> bool:
    """Return True when every task is done or failed and there are no pending."""
    return all(t.status in ("done", "failed") for t in state.tasks)
