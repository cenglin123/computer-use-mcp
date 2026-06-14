"""Tests for task-level execution runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from computer_use import runner as runner_mod
from computer_use import trace as trace_module


@pytest.fixture(autouse=True)
def _patch_trace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)


def test_run_task_plan_executes_steps_and_generates_report(monkeypatch, tmp_path) -> None:
    call_log = []

    import computer_use.mcp_server as server

    def fake_dispatch_tool(name, args, cs, trace_id=None, parent_step_index=None):
        call_log.append((name, args, trace_id, parent_step_index))
        return json.dumps({"called": name, "args": args})

    monkeypatch.setattr(server, "_dispatch_tool", fake_dispatch_tool)

    result = runner_mod.run_task_plan(
        steps=[
            {"tool": "click", "args": {"x": 100, "y": 200}},
            {"tool": "type", "args": {"text": "hello"}},
        ],
        goal="test task",
        trace_id="task-001",
        capture_screenshots=False,
    )

    assert result["trace_id"] == "task-001"
    assert result["failed_index"] is None
    assert len(result["results"]) == 2
    assert Path(result["report_path"]).exists()

    records = trace_module.read_trace("task-001")
    assert len(records) == 2
    assert all(r["trace_id"] == "task-001" for r in records)
    assert records[0]["step_index"] == 1
    assert records[1]["step_index"] == 2


def test_run_task_plan_stops_on_error(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    def fake_dispatch_tool(name, args, cs, trace_id=None, parent_step_index=None):
        if name == "click":
            return json.dumps({"error": "out of bounds"})
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_dispatch_tool", fake_dispatch_tool)

    result = runner_mod.run_task_plan(
        steps=[
            {"tool": "click", "args": {"x": 99999, "y": 99999}},
            {"tool": "type", "args": {"text": "hello"}},
        ],
        capture_screenshots=False,
    )

    assert result["failed_index"] == 0
    assert len(result["results"]) == 1


def test_run_task_plan_requires_steps() -> None:
    with pytest.raises(ValueError, match="steps must contain"):
        runner_mod.run_task_plan(steps=[])


def test_run_task_plan_requires_tool_in_step() -> None:
    with pytest.raises(ValueError, match="missing 'tool'"):
        runner_mod.run_task_plan(steps=[{"args": {}}])


def test_retry_step_single_replays_one_step(monkeypatch, tmp_path) -> None:
    call_log = []

    def fake_call_tool(name, args, trace_context=None):
        call_log.append((name, args, trace_context))
        return json.dumps({"retried": True})

    import computer_use.runner as runner_module
    monkeypatch.setattr(runner_module, "_call_tool", fake_call_tool)

    trace_module.record_step(
        trace_id="retry-001",
        step_index=2,
        tool="click",
        args={"x": 100, "y": 200},
        result={"clicked": True},
        duration_ms=10,
    )

    result = runner_mod.retry_step("retry-001", step_index=2, mode="single")

    assert result["trace_id"] == "retry-001"
    assert result["original_step_index"] == 2
    assert result["mode"] == "single"
    assert result["retry_step_index"] == "2.retry.1"
    assert call_log[-1][0] == "click"
    assert call_log[-1][1] == {"x": 100, "y": 200}
    assert call_log[-1][2] == {"trace_id": "retry-001", "step_index": "2.retry.1"}


def test_retry_step_from_step_replays_subsequent(monkeypatch, tmp_path) -> None:
    call_log = []

    def fake_call_tool(name, args, trace_context=None):
        call_log.append((name, args, trace_context))
        return json.dumps({"retried": True})

    import computer_use.runner as runner_module
    monkeypatch.setattr(runner_module, "_call_tool", fake_call_tool)

    trace_module.record_step(
        trace_id="retry-002",
        step_index=1,
        tool="click",
        args={"x": 100, "y": 200},
        result={"clicked": True},
    )
    trace_module.record_step(
        trace_id="retry-002",
        step_index=2,
        tool="type",
        args={"text": "hello"},
        result={"typed": True},
    )

    result = runner_mod.retry_step("retry-002", step_index=1, mode="from_step")

    assert result["mode"] == "from_step"
    assert "subsequent_results" in result
    assert len(result["subsequent_results"]) == 1
    assert result["subsequent_results"][0]["original_step_index"] == 2


def test_retry_step_missing_trace() -> None:
    result = runner_mod.retry_step("missing", step_index=1)
    assert result["error"] == "trace_not_found"


def test_retry_step_missing_step() -> None:
    trace_module.record_step(
        trace_id="retry-003",
        step_index=0,
        tool="click",
        args={"x": 100, "y": 200},
        result={"clicked": True},
    )
    result = runner_mod.retry_step("retry-003", step_index=99)
    assert result["error"] == "step_not_found"


def test_run_task_plan_no_duplicate_step_index_for_screenshot(monkeypatch, tmp_path) -> None:
    """Screenshots must not create a separate trace record with the same step_index."""
    call_log = []

    import computer_use.mcp_server as server

    def fake_dispatch_tool(name, args, cs, trace_id=None, parent_step_index=None):
        call_log.append((name, args, trace_id, parent_step_index))
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_dispatch_tool", fake_dispatch_tool)
    monkeypatch.setattr(runner_mod, "_step_screenshot", lambda *a, **k: str(tmp_path / "shot.png"))

    result = runner_mod.run_task_plan(
        steps=[{"tool": "click", "args": {"x": 100, "y": 200}}],
        trace_id="task-screenshot",
        capture_screenshots=True,
    )

    assert result["trace_id"] == "task-screenshot"
    records = trace_module.read_trace("task-screenshot")
    step_indices = [r["step_index"] for r in records]
    assert step_indices == [1]
    assert records[0].get("screenshot_path") is not None
    assert call_log[0][0] == "click"
    assert call_log[0][3] == 1


def test_run_task_plan_writes_goal_meta(monkeypatch, tmp_path) -> None:
    def fake_call_tool(name, args, trace_context=None):
        return json.dumps({"called": name})

    monkeypatch.setattr(runner_mod, "_call_tool", fake_call_tool)

    runner_mod.run_task_plan(
        steps=[{"tool": "click", "args": {"x": 100, "y": 200}}],
        trace_id="task-goal",
        goal="open settings",
        capture_screenshots=False,
    )

    meta = trace_module.read_trace_meta("task-goal")
    assert meta.get("goal") == "open settings"
