"""Models for the NEXUS pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Phase(BaseModel):
    """A NEXUS phase with a gate keeper and pass criteria."""

    number: int
    name: str
    gate_keeper: str | None = None
    pass_criteria: list[str] = Field(default_factory=list)


class Verdict(StrEnum):
    """QA / gate verdict values."""

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_WORK = "NEEDS_WORK"
    NOT_READY = "NOT_READY"


class Task(BaseModel):
    """A unit of work in a NEXUS pipeline."""

    id: str
    description: str
    agent_slug: str
    qa_slug: str | None = None
    status: str = "pending"  # pending, in_progress, done, failed, blocked
    attempts: int = 0
    max_attempts: int = 3
    verdict: Verdict | None = None
    evidence: list[str] = Field(default_factory=list)
    output: str = ""
    depends_on: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def can_retry(self) -> bool:
        return self.attempts < self.max_attempts


class PipelineState(BaseModel):
    """Runtime state for a pipeline execution."""

    mode: str = "micro"
    phase: int = 0
    goal: str = ""
    agents: list[str] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    current_task_id: str | None = None
    status: str = "idle"  # idle, running, completed, failed
    metadata: dict[str, Any] = Field(default_factory=dict)

    def current_task(self) -> Task | None:
        if not self.current_task_id:
            return None
        for task in self.tasks:
            if task.id == self.current_task_id:
                return task
        return None

    def next_pending_task(self) -> Task | None:
        for task in self.tasks:
            if task.status == "pending":
                # Check dependencies
                if task.depends_on:
                    dep_done = all(
                        any(t.id == dep and t.status == "done" for t in self.tasks)
                        for dep in task.depends_on
                    )
                    if not dep_done:
                        continue
                return task
        return None


NEXUS_PHASES: list[Phase] = [
    Phase(number=0, name="Discover", gate_keeper="Executive Summary Generator"),
    Phase(number=1, name="Strategize", gate_keeper="Studio Producer + Reality Checker"),
    Phase(number=2, name="Scaffold", gate_keeper="DevOps Automator + Evidence Collector"),
    Phase(number=3, name="Build", gate_keeper="Agents Orchestrator"),
    Phase(number=4, name="Harden", gate_keeper="Reality Checker"),
    Phase(number=5, name="Launch", gate_keeper="Studio Producer + Analytics Reporter"),
    Phase(number=6, name="Operate", gate_keeper="Studio Producer"),
]
