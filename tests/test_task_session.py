"""Tests for business task session lifecycle."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from computer_use import task_session


@pytest.fixture(autouse=True)
def _patch_task_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path)


def test_generate_task_id_format() -> None:
    assert re.fullmatch(
        r"task-\d{8}-\d{6}-[a-z0-9]{6}",
        task_session.generate_task_id(),
    )


def test_start_task_creates_explicit_task() -> None:
    task = task_session.start_task("audit traces")

    assert task["goal"] == "audit traces"
    assert task["mode"] == "explicit"
    assert task["status"] == "active"
    assert Path(task["task_path"]).is_dir()


def test_register_complete_and_finish_task() -> None:
    task = task_session.start_task("demo")
    task_id = task["task_id"]

    task_session.register_trace(task_id, "trace-001", kind="atomic", tool="sleep")
    task_session.complete_trace(task_id, "trace-001", status="succeeded")
    finished = task_session.finish_task(task_id, summary="done")

    assert finished["status"] == "succeeded"
    assert finished["summary"] == "done"
    details = task_session.get_task(task_id)
    assert details["trace_count"] == 1
    assert details["failed_trace_count"] == 0
    assert details["active_trace_count"] == 0


def test_trace_can_belong_to_only_one_task() -> None:
    first = task_session.start_task("first")["task_id"]
    second = task_session.start_task("second")["task_id"]
    task_session.register_trace(first, "trace-001", kind="atomic", tool="sleep")

    with pytest.raises(task_session.TraceTaskConflictError):
        task_session.register_trace(second, "trace-001", kind="atomic", tool="sleep")


def test_register_trace_rejects_closed_task() -> None:
    task_id = task_session.start_task("closed")["task_id"]
    task_session.finish_task(task_id, cancel=True)

    with pytest.raises(task_session.TaskClosedError):
        task_session.register_trace(task_id, "trace-001", kind="atomic", tool="sleep")


def test_finish_task_derives_failed_status() -> None:
    task_id = task_session.start_task("failure")["task_id"]
    task_session.register_trace(task_id, "trace-001", kind="atomic", tool="sleep")
    task_session.complete_trace(task_id, "trace-001", status="failed")

    assert task_session.finish_task(task_id)["status"] == "failed"


def test_list_tasks_filters_by_status() -> None:
    succeeded = task_session.start_task("succeeded")["task_id"]
    failed = task_session.start_task("failed")["task_id"]
    task_session.register_trace(succeeded, "trace-ok", kind="atomic", tool="sleep")
    task_session.complete_trace(succeeded, "trace-ok", status="succeeded")
    task_session.finish_task(succeeded)
    task_session.register_trace(failed, "trace-fail", kind="atomic", tool="sleep")
    task_session.complete_trace(failed, "trace-fail", status="failed")
    task_session.finish_task(failed)

    tasks = task_session.list_tasks(status="failed")

    assert [task["task_id"] for task in tasks] == [failed]
