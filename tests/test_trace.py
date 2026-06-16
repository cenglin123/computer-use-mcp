"""Tests for the structured trace module."""

from __future__ import annotations

import re
from datetime import datetime, timezone
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

    trace_file = trace.trace_root(trace_id) / "trace.jsonl"
    assert trace_file.exists()


def test_trace_root_does_not_precreate_artifact_directories(
    tmp_trace_dir: Path,
) -> None:
    root = trace.trace_root("empty-artifacts")

    assert root.is_dir()
    assert not (root / "screenshots").exists()
    assert not (root / "snapshots").exists()


def test_artifact_dir_creates_only_requested_kind(tmp_trace_dir: Path) -> None:
    screenshots = trace.artifact_dir("lazy-artifacts", "screenshots")

    assert screenshots.is_dir()
    assert not (screenshots.parent / "snapshots").exists()


def test_artifact_manifest_lists_only_existing_files(tmp_trace_dir: Path) -> None:
    root = trace.trace_root("manifest")
    trace.record_step("manifest", 0, "click", {})
    screenshot = trace.artifact_dir("manifest", "screenshots") / "step.png"
    screenshot.write_bytes(b"png")

    manifest = trace.artifact_manifest("manifest")

    assert manifest == {
        "trace_id": "manifest",
        "artifact_root": str(root),
        "trace_path": str(root / "trace.jsonl"),
        "report_path": None,
        "screenshots": [str(screenshot)],
        "snapshots": [],
    }


def test_create_trace_root_partitions_by_date_and_registers_locator(
    tmp_trace_dir: Path,
) -> None:
    root = trace.create_trace_root(
        "partitioned-trace",
        created_at=datetime(2026, 6, 16, 1, 2, tzinfo=timezone.utc),
    )

    assert root == tmp_trace_dir / "2026" / "06" / "16" / "partitioned-trace"
    assert trace.resolve_trace_root("partitioned-trace") == root
    assert (tmp_trace_dir / ".index").is_dir()


def test_read_trace_supports_legacy_flat_layout(tmp_trace_dir: Path) -> None:
    legacy = tmp_trace_dir / "legacy-trace"
    legacy.mkdir()
    (legacy / "trace.jsonl").write_text(
        '{"trace_id": "legacy-trace", "step_index": 1, "tool": "sleep"}\n',
        encoding="utf-8",
    )

    assert trace.resolve_trace_root("legacy-trace") == legacy
    assert trace.read_trace("legacy-trace")[0]["tool"] == "sleep"


def test_write_trace_meta_records_task_id_and_created_at(
    tmp_trace_dir: Path,
) -> None:
    trace.write_trace_meta("task-owned-trace", goal="demo", task_id="task-001")

    meta = trace.read_trace_meta("task-owned-trace")
    assert meta["schema_version"] == 1
    assert meta["trace_id"] == "task-owned-trace"
    assert meta["task_id"] == "task-001"
    assert "created_at" in meta


def test_write_trace_meta_rejects_conflicting_task_id(tmp_trace_dir: Path) -> None:
    trace.write_trace_meta("conflict-trace", task_id="task-a")

    with pytest.raises(ValueError, match="task_id"):
        trace.write_trace_meta("conflict-trace", task_id="task-b")


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
    assert report_path.parent == trace.trace_root(trace_id)
    text = report_path.read_text(encoding="utf-8")
    assert trace_id in text
    assert "Click the OK button" in text
    assert "click" in text
    assert "find_control" in text
    assert "ui_not_found" in text


def test_generate_report_marks_error_kind_as_failed(
    tmp_trace_dir: Path,
) -> None:
    trace_id = "report-timeout-001"
    trace.record_step(
        trace_id=trace_id,
        step_index=1,
        tool="wait_for_window",
        args={"name": "Missing"},
        result={"present": False, "timeout": True},
        error_kind="timeout",
        error_message="Timed out waiting for window",
    )

    report_path = trace.generate_report(trace_id)
    row = next(
        line
        for line in report_path.read_text(encoding="utf-8").splitlines()
        if "wait_for_window" in line
    )
    assert "| failed: timeout | timeout |" in row
    assert "| ok |" not in row


@pytest.mark.parametrize(
    "trace_id",
    [
        "../escape",
        "nested/trace",
        r"nested\trace",
        r"C:\absolute",
        "CON",
        "com1",
        "trailing.",
        "contains space",
        "x" * 129,
    ],
)
def test_trace_entrypoints_reject_invalid_trace_ids(
    tmp_trace_dir: Path, trace_id: str
) -> None:
    with pytest.raises(ValueError, match="trace_id"):
        trace.trace_root(trace_id)
    with pytest.raises(ValueError, match="trace_id"):
        trace.write_trace_meta(trace_id)
    with pytest.raises(ValueError, match="trace_id"):
        trace.read_trace_meta(trace_id)
    with pytest.raises(ValueError, match="trace_id"):
        trace.read_trace(trace_id)


def test_record_step_recursively_redacts_input_values(
    tmp_trace_dir: Path,
) -> None:
    trace.record_step(
        trace_id="redaction-001",
        step_index=1,
        tool="run_task_plan",
        args={
            "steps": [
                {"tool": "type", "args": {"text": "top-secret"}},
                {
                    "tool": "batch",
                    "args": {
                        "actions": [
                            {
                                "tool": "fill_form",
                                "args": {
                                    "fields": [
                                        {
                                            "name": "Password",
                                            "value": "nested-secret",
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
            ]
        },
        result={
            "error": "failed while handling top-secret and nested-secret"
        },
    )

    record = trace.read_trace("redaction-001")[0]
    serialized = str(record)
    assert "top-secret" not in serialized
    assert "nested-secret" not in serialized
    assert record["replayable"] is False
    assert record["args"]["steps"][0]["args"]["text"] == {
        "redacted": True,
        "length": 10,
    }
    assert record["args"]["steps"][1]["args"]["actions"][0]["args"][
        "fields"
    ][0]["name"] == "Password"
