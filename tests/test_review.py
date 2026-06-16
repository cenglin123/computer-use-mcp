"""Tests for deterministic trace review."""

from __future__ import annotations

import pytest

from computer_use import review as review_mod
from computer_use import task_session
from computer_use import trace as trace_module


@pytest.fixture(autouse=True)
def _patch_trace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")


def test_review_task_summarizes_trace(tmp_path) -> None:
    trace_id = "review-001"
    trace_module.write_trace_meta(trace_id, goal="Click the OK button")
    trace_module.record_step(
        trace_id=trace_id,
        step_index=1,
        tool="click",
        args={"x": 100, "y": 200},
        result={"clicked": True},
        duration_ms=45,
        screenshot_path="C:/shots/1.png",
    )
    trace_module.record_step(
        trace_id=trace_id,
        step_index=2,
        tool="find_control",
        args={"name": "OK"},
        result={"error": "not found"},
        duration_ms=120,
        error_kind="ui_not_found",
        error_message="Control OK not found",
    )
    trace_module.record_step(
        trace_id=trace_id,
        step_index="2.retry.1",
        tool="find_control",
        args={"name": "OK"},
        result={"found": True},
        duration_ms=50,
    )

    result = review_mod.review_task(trace_id)

    assert result["trace_id"] == trace_id
    assert result["goal"] == "Click the OK button"
    assert result["summary"]["total_steps"] == 3
    assert result["summary"]["successful_steps"] == 2
    assert result["summary"]["failed_steps"] == 1
    assert result["summary"]["retry_steps"] == 1
    assert result["error_distribution"] == {"ui_not_found": 1}
    assert result["screenshots"] == ["C:/shots/1.png"]
    assert result["step_index_range"]["first"] == 1
    assert result["step_index_range"]["last"] == "2.retry.1"


def test_review_task_missing_trace() -> None:
    result = review_mod.review_task("missing")
    assert result["error"] == "trace_not_found"


def test_review_task_session_summarizes_task_traces() -> None:
    task_id = task_session.start_task("session")["task_id"]
    trace_module.record_step("trace-a", 1, "sleep", {"duration": 0})
    task_session.register_trace(task_id, "trace-a", kind="atomic", tool="sleep")
    task_session.complete_trace(task_id, "trace-a", status="succeeded")

    result = review_mod.review_task_session(task_id)

    assert result["task_id"] == task_id
    assert result["trace_count"] == 1
    assert result["failed_trace_count"] == 0
    assert result["traces"][0]["trace_id"] == "trace-a"
    assert result["traces"][0]["review"]["summary"]["total_steps"] == 1
