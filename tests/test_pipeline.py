"""Tests for the pipeline state machine and orchestrator."""

from __future__ import annotations

from nexus_os.pipeline.models import PipelineState, Task, Verdict
from nexus_os.pipeline.orchestrator import MicroOrchestrator, all_tasks_complete
from nexus_os.pipeline.state_machine import advance_phase, evaluate_task_after_qa


def test_advance_phase():
    state = PipelineState(phase=3, tasks=[Task(id="T1", description="x", agent_slug="a", status="done")])
    assert advance_phase(state) is True
    assert state.phase == 4


def test_advance_phase_blocked():
    state = PipelineState(phase=3, tasks=[Task(id="T1", description="x", agent_slug="a", status="pending")])
    assert advance_phase(state) is False


def test_evaluate_task_pass():
    task = Task(id="T1", description="x", agent_slug="a")
    evaluate_task_after_qa(task, Verdict.PASS, ["ok"])
    assert task.status == "done"
    assert task.attempts == 1


def test_evaluate_task_fail_then_retry():
    task = Task(id="T1", description="x", agent_slug="a")
    evaluate_task_after_qa(task, Verdict.FAIL, ["bad"])
    assert task.status == "pending"
    assert task.attempts == 1


def test_evaluate_task_max_retries():
    task = Task(id="T1", description="x", agent_slug="a", attempts=2)
    evaluate_task_after_qa(task, Verdict.FAIL, ["bad"])
    assert task.status == "failed"
    assert task.attempts == 3


def test_all_tasks_complete():
    state = PipelineState(tasks=[Task(id="T1", description="x", agent_slug="a", status="done")])
    assert all_tasks_complete(state) is True


def test_orchestrator_plan_and_run(temp_repo):
    orchestrator = MicroOrchestrator(temp_repo)
    state = orchestrator.init(goal="test goal", agents=["a", "b"])
    state = orchestrator.plan(state, goal="test goal", agents=["a", "b"])
    assert len(state.tasks) == 2
    final = orchestrator.run(state)
    assert final.status == "completed"


def test_orchestrator_resume(temp_repo):
    orchestrator = MicroOrchestrator(temp_repo)
    orchestrator.init(goal="test goal", agents=["a"])
    orchestrator.plan(orchestrator.store.read_state() and PipelineState(**orchestrator.store.read_state()), goal="test goal", agents=["a"])
    # Simulate interruption.
    raw = orchestrator.store.read_state()
    raw["status"] = "running"
    orchestrator.store.write_state(raw)
    final = orchestrator.resume()
    assert final.status in ("completed", "running")
