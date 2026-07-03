"""NEXUS-Micro orchestrator with restart-proof memory."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from nexus_os.memory.handoffs import (
    escalation_handoff,
    qa_fail_handoff,
    qa_pass_handoff,
    standard_handoff,
)
from nexus_os.memory.resume import can_resume
from nexus_os.memory.store import MemoryStore
from nexus_os.pipeline.models import PipelineState, Task, Verdict
from nexus_os.pipeline.state_machine import advance_phase, evaluate_task_after_qa


class MicroOrchestrator:
    """Run a NEXUS-Micro pipeline against a target repo."""

    def __init__(
        self,
        repo_path: Path,
        runner: Callable[[Task, PipelineState], tuple[str, Verdict, list[str]]] | None = None,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.store = MemoryStore(self.repo_path)
        self.runner = runner or self._default_runner

    def _default_runner(self, task: Task, state: PipelineState) -> tuple[str, Verdict, list[str]]:
        """Placeholder runner used when no LLM runner is supplied."""
        output = f"Mock execution of task {task.id}: {task.description}"
        # QA agent would normally run here; in dry-run we simulate PASS.
        return output, Verdict.PASS, ["Mock evidence: no real execution in dry-run mode."]

    def init(
        self,
        goal: str,
        agents: list[str],
        mode: str = "micro",
    ) -> PipelineState:
        """Initialize a new Micro run in the target repo."""
        raw = self.store.init_state(
            {
                "status": "idle",
                "mode": mode,
                "phase": 3,  # Micro defaults straight to Build phase
                "goal": goal,
                "agents": agents,
                "tasks": [],
                "current_task_id": None,
                "metadata": {"initialized_at": datetime.now(UTC).isoformat()},
            }
        )
        state = PipelineState(**raw)
        self._commit(f"nexus: init {mode} run")
        return state

    def plan(self, state: PipelineState, goal: str, agents: list[str]) -> PipelineState:
        """Break the goal into tasks and assign agents."""
        state.goal = goal
        state.agents = agents
        # Simple planning: one task per requested agent in sequence.
        for idx, slug in enumerate(agents, start=1):
            is_qa = "test" in slug or "qa" in slug or "evidence" in slug or "reality" in slug
            task = Task(
                id=f"T{idx:03d}",
                description=f"{slug} contributes to: {goal}",
                agent_slug=slug,
                qa_slug="testing-evidence-collector" if not is_qa else None,
                depends_on=[f"T{idx - 1:03d}"] if idx > 1 else [],
                metadata={"phase": 3, "planned_at": datetime.now(UTC).isoformat()},
            )
            state.tasks.append(task)
        self._save_state(state)
        return state

    def run(self, state: PipelineState | None = None) -> PipelineState:
        """Execute the pipeline from current state until completion or failure."""
        if state is None:
            raw = self.store.read_state()
            if not raw:
                raise RuntimeError("No state found; run `init` and `plan` first.")
            state = PipelineState(**raw)

        state.status = "running"
        self._save_state(state)
        self.store.log(f"Pipeline {state.mode} started/resumed with {len(state.tasks)} tasks")

        while True:
            task = state.next_pending_task()
            if task is None:
                if all_tasks_complete(state):
                    state.status = "completed"
                    state.current_task_id = None
                    self._save_state(state)
                    self._commit("nexus: completed run")
                    self.store.log("Pipeline completed")
                    break
                # All tasks are blocked/failed; abort.
                state.status = "failed"
                self._save_state(state)
                self._commit("nexus: failed run")
                self.store.log("Pipeline failed: no pending tasks and not complete")
                break

            state.current_task_id = task.id
            task.status = "in_progress"
            self._save_state(state)
            self.store.checkpoint(f"task_{task.id}_start", state.model_dump())

            # Execute developer agent.
            self.store.log(f"Executing task {task.id} with agent {task.agent_slug}")
            output, dev_verdict, evidence = self.runner(task, state)
            task.output = output
            self.store.write_memory(
                task.agent_slug, task.id, output, extension="md"
            )

            # Execute QA agent if assigned.
            if task.qa_slug:
                self.store.log(f"QA task {task.id} with agent {task.qa_slug}")
                qa_output, qa_verdict, qa_evidence = self.runner(
                    Task(
                        id=f"{task.id}_qa",
                        description=f"QA validation for {task.description}",
                        agent_slug=task.qa_slug,
                    ),
                    state,
                )
                self.store.write_memory(task.qa_slug, f"{task.id}_qa", qa_output, extension="md")
                evaluate_task_after_qa(task, qa_verdict, qa_evidence)
                self._record_qa_handoff(task, qa_output, qa_evidence)
            else:
                # No QA assigned; treat developer output as PASS.
                task.attempts += 1
                task.verdict = dev_verdict
                task.status = "done" if dev_verdict == Verdict.PASS else "failed"
                task.evidence.extend(evidence)

            state.current_task_id = None
            self._save_state(state)
            self.store.checkpoint(f"task_{task.id}_end", state.model_dump())
            self._commit(f"nexus: task {task.id} {task.status}")

            # Advance phase if possible (Micro usually stays in phase 3).
            if advance_phase(state):
                self._save_state(state)
                self.store.log(f"Advanced to phase {state.phase}")

        return state

    def resume(self) -> PipelineState:
        """Resume an interrupted run if one exists."""
        if not can_resume(self.repo_path):
            raise RuntimeError("No interrupted run found.")
        return self.run()

    def _save_state(self, state: PipelineState) -> None:
        raw = state.model_dump()
        raw["project_path"] = str(self.repo_path)
        self.store.write_state(raw)

    def _commit(self, message: str) -> None:
        self.store.auto_commit(message)

    def _record_qa_handoff(
        self, task: Task, qa_output: str, qa_evidence: list[str]
    ) -> None:
        if task.verdict == Verdict.PASS:
            content = qa_pass_handoff(
                from_agent=task.qa_slug or "QA",
                to_agent="orchestrator",
                phase=3,
                task_id=task.id,
                evidence=qa_evidence,
            )
        elif task.status == "failed":
            # Escalation after max retries.
            if not task.can_retry():
                content = escalation_handoff(
                    from_agent=task.qa_slug or "QA",
                    phase=3,
                    task_id=task.id,
                    failure_history=[
                        {
                            "attempt": task.attempts,
                            "summary": qa_output[:200],
                        }
                    ],
                    impact="Task exceeded maximum retry attempts.",
                )
            else:
                content = qa_fail_handoff(
                    from_agent=task.qa_slug or "QA",
                    to_agent=task.agent_slug,
                    phase=3,
                    task_id=task.id,
                    issues=[
                        {
                            "title": f"QA failure on attempt {task.attempts}",
                            "priority": "Medium",
                            "evidence": "; ".join(qa_evidence) if qa_evidence else "N/A",
                            "fix": qa_output[:300],
                        }
                    ],
                    retry_count=task.attempts,
                )
        else:
            content = standard_handoff(
                from_agent=task.agent_slug,
                to_agent=task.qa_slug or "QA",
                phase=3,
                task_id=task.id,
                project=str(self.repo_path),
                current_state=f"Task {task.id} executed; awaiting QA.",
                deliverable_request="Validate the implementation against acceptance criteria.",
                acceptance_criteria=["Functionality matches task description"],
                references=[],
            )
        self.store.write_handoff(
            handoff_type="qa_pass" if task.verdict == Verdict.PASS else "qa_fail",
            from_agent=task.qa_slug or "QA",
            to_agent=task.agent_slug,
            phase=3,
            task_id=task.id,
            content=content,
        )


def all_tasks_complete(state: PipelineState) -> bool:
    """Return True only when all tasks are done."""
    return bool(state.tasks) and all(t.status == "done" for t in state.tasks)
