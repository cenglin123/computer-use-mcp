"""Tests for the structured trace module."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from computer_use import trace


@pytest.fixture
def tmp_trace_dir(tmp_path, monkeypatch):
    """Redirect trace output to a temporary directory."""
    monkeypatch.setattr(trace, "trace_dir", lambda: tmp_path)
    return tmp_path


def test_generate_trace_id_format() -> None:
    trace_id = trace.generate_trace_id()
    assert re.fullmatch(r"\d{8}-\d{6}-[a-z0-9]{6}", trace_id)


def test_record_step_writes_trace_file(tmp_trace_dir: Path) -> None:
    trace_id = "test-trace-001"
    record = trace.record_step(
        trace_id=trace_id,
        step_index=0,
        tool="sleep",
        args={"duration": 0.5},
        result={"slept": True},
        duration_ms=12,
        screenshot_path="C:/shots/1.png",
        ui_snapshot_path="C:/snaps/1.json",
    )
    assert record.trace_id == trace_id
    assert record.step_index == 0

    records = trace.read_trace(trace_id)
    assert len(records) == 1
    assert records[0]["trace_id"] == trace_id
    assert records[0]["step_index"] == 0
    assert records[0]["tool"] == "sleep"
    assert records[0]["args"] == {"duration": 0.5}
    assert records[0]["result"] == {"slept": True}
    assert records[0]["duration_ms"] == 12
    assert records[0]["screenshot_path"] == "C:/shots/1.png"
    assert records[0]["ui_snapshot_path"] == "C:/snaps/1.json"
    assert records[0]["error_kind"] is None
    assert records[0]["error_message"] is None

    trace_file = tmp_trace_dir / trace_id / "trace.jsonl"
    assert trace_file.exists()


def test_read_trace_returns_empty_for_missing_trace(tmp_trace_dir: Path) -> None:
    assert trace.read_trace("does-not-exist") == []


def test_generate_report_creates_markdown(tmp_trace_dir: Path) -> None:
    trace_id = "report-trace-001"
    trace.record_step(
        trace_id=trace_id,
        step_index=0,
        tool="click",
        args={"x": 100, "y": 200},
        result={"clicked": True},
        duration_ms=45,
    )
    trace.record_step(
        trace_id=trace_id,
        step_index=1,
        tool="find_control",
        args={"name": "OK"},
        result={"error": "not found"},
        duration_ms=120,
        error_kind="ui_not_found",
        error_message="Control OK not found",
    )

    report_path = trace.generate_report(trace_id, goal="Click the OK button")
    assert report_path.exists()
    assert report_path.parent == tmp_trace_dir / trace_id
    text = report_path.read_text(encoding="utf-8")
    assert trace_id in text
    assert "Click the OK button" in text
    assert "click" in text
    assert "find_control" in text
    assert "ui_not_found" in text
