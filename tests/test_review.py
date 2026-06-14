"""Tests for deterministic trace review."""

from __future__ import annotations

import pytest

from computer_use import review as review_mod
from computer_use import trace as trace_module


@pytest.fixture(autouse=True)
def _patch_trace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)


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
