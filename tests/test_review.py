"""Tests for deterministic trace review."""

from __future__ import annotations

import json

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


def test_review_task_detail_true_includes_steps() -> None:
    trace_id = "review-detail-001"
    trace_module.write_trace_meta(trace_id, goal="Detail trace")
    trace_module.record_step(
        trace_id=trace_id,
        step_index=1,
        tool="click",
        args={"x": 100, "y": 200},
        result={"clicked": True},
        duration_ms=45,
        screenshot_path="C:/shots/1.png",
        ui_snapshot_path="C:/snaps/1.json",
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

    result = review_mod.review_task(trace_id, detail=True)

    assert "steps" in result
    steps = result["steps"]
    assert len(steps) == 2

    assert steps[0]["step_index"] == 1
    assert steps[0]["tool"] == "click"
    assert steps[0]["args"] == {"x": 100, "y": 200}
    assert steps[0]["result"] == {"clicked": True}
    assert steps[0]["duration_ms"] == 45
    assert steps[0]["screenshot_path"] == "C:/shots/1.png"
    assert steps[0]["ui_snapshot_path"] == "C:/snaps/1.json"
    assert steps[0]["error_kind"] is None
    assert steps[0]["error_message"] is None

    assert steps[1]["step_index"] == 2
    assert steps[1]["tool"] == "find_control"
    assert steps[1]["error_kind"] == "ui_not_found"
    assert steps[1]["error_message"] == "Control OK not found"
    assert steps[1]["screenshot_path"] is None


def test_review_task_detail_false_omits_steps() -> None:
    trace_id = "review-detail-002"
    trace_module.write_trace_meta(trace_id, goal="No detail")
    trace_module.record_step(trace_id, 1, "sleep", {"duration": 0})

    result_default = review_mod.review_task(trace_id)
    result_explicit = review_mod.review_task(trace_id, detail=False)

    assert "steps" not in result_default
    assert "steps" not in result_explicit


def test_review_task_detail_redacts_sensitive_input() -> None:
    trace_id = "review-detail-redact"
    trace_module.write_trace_meta(trace_id, goal="Redact")
    trace_module.record_step(
        trace_id=trace_id,
        step_index=1,
        tool="type",
        args={"text": "top-secret"},
        result={"typed": True},
    )

    result = review_mod.review_task(trace_id, detail=True)
    serialized = str(result["steps"])

    assert "top-secret" not in serialized
    assert result["steps"][0]["args"]["text"] == {"redacted": True, "length": 10}


def test_review_task_detail_sanitizes_raw_legacy_trace() -> None:
    trace_id = "review-detail-raw"
    root = trace_module.trace_root(trace_id)
    (root / "trace.jsonl").write_text(
        json.dumps(
            {
                "trace_id": trace_id,
                "step_index": 1,
                "tool": "type",
                "args": {"text": "top-secret"},
                "result": {
                    "echo": "top-secret",
                    "value": "result-secret",
                    "message": "result-secret",
                },
                "duration_ms": 1,
                "error_message": "failed with top-secret and result-secret",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = review_mod.review_task(trace_id, detail=True)
    step = result["steps"][0]
    serialized = json.dumps(step, ensure_ascii=False)

    assert "top-secret" not in serialized
    assert "result-secret" not in serialized
    assert step["args"]["text"] == {"redacted": True, "length": 10}
    assert step["result"]["echo"] == "<redacted>"
    assert step["result"]["value"] == {"redacted": True, "length": 13}
    assert step["result"]["message"] == "<redacted>"
    assert step["error_message"] == "failed with <redacted> and <redacted>"


def test_review_task_detail_sanitizes_malformed_redacted_placeholder() -> None:
    trace_id = "review-detail-placeholder"
    root = trace_module.trace_root(trace_id)
    (root / "trace.jsonl").write_text(
        json.dumps(
            {
                "trace_id": trace_id,
                "step_index": 1,
                "tool": "type",
                "args": {
                    "text": {
                        "redacted": True,
                        "length": 10,
                        "preview": "top-secret",
                    }
                },
                "result": {"echo": "top-secret"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = review_mod.review_task(trace_id, detail=True)
    step = result["steps"][0]
    serialized = json.dumps(step, ensure_ascii=False)

    assert "top-secret" not in serialized
    assert "preview" not in step["args"]["text"]
    assert step["args"]["text"] == {"redacted": True, "length": 10}
    assert step["result"]["echo"] == "<redacted>"


def test_review_task_session_detail_true_propagates_to_traces() -> None:
    task_id = task_session.start_task("detail session")["task_id"]
    trace_module.record_step("trace-detail-a", 1, "sleep", {"duration": 0})
    trace_module.record_step("trace-detail-a", 2, "click", {"x": 1, "y": 2})
    task_session.register_trace(task_id, "trace-detail-a", kind="atomic", tool="batch")
    task_session.complete_trace(task_id, "trace-detail-a", status="succeeded")

    result_detail = review_mod.review_task_session(task_id, detail=True)
    result_plain = review_mod.review_task_session(task_id, detail=False)

    assert "steps" in result_detail["traces"][0]["review"]
    assert len(result_detail["traces"][0]["review"]["steps"]) == 2
    assert "steps" not in result_plain["traces"][0]["review"]
