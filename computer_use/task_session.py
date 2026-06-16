"""Business task session lifecycle and trace ownership."""

from __future__ import annotations

import json
import re
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from computer_use import audit_store
from computer_use.config import load_config


_ALPHANUM = string.ascii_lowercase + string.digits
_TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_WINDOWS_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class TaskSessionError(Exception):
    """Base error for task session operations."""


class TaskNotFoundError(TaskSessionError):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"task not found: {task_id}")


class TaskClosedError(TaskSessionError):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"task is closed: {task_id}")


class TraceTaskConflictError(TaskSessionError):
    def __init__(self, trace_id: str, task_id: str, existing_task_id: str):
        self.trace_id = trace_id
        self.task_id = task_id
        self.existing_task_id = existing_task_id
        super().__init__(
            f"trace {trace_id} already belongs to task {existing_task_id}"
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def task_dir() -> Path:
    """Return configured task session directory."""
    config = load_config()
    path = config.get("task_dir", Path.home() / ".computer-use" / "tasks")
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_task_id(task_id: str) -> str:
    """Reject unsafe task IDs as a single Windows path component."""
    if not isinstance(task_id, str) or not _TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("Invalid task_id")
    if task_id.endswith("."):
        raise ValueError("Invalid task_id")
    if task_id.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES:
        raise ValueError("Invalid task_id")
    return task_id


def generate_task_id() -> str:
    now = datetime.now(timezone.utc)
    slug = "".join(secrets.choice(_ALPHANUM) for _ in range(6))
    return f"task-{now.strftime('%Y%m%d-%H%M%S')}-{slug}"


def _task_root(task_id: str) -> Path | None:
    validate_task_id(task_id)
    return audit_store.resolve_location(task_dir(), task_id)


def _require_task_root(task_id: str) -> Path:
    root = _task_root(task_id)
    if root is None:
        raise TaskNotFoundError(task_id)
    return root


def _read_task_json(root: Path) -> dict[str, Any]:
    return json.loads((root / "task.json").read_text(encoding="utf-8"))


def _write_task_json(root: Path, data: dict[str, Any]) -> None:
    data["updated_at"] = _now()
    audit_store.write_json_atomic(root / "task.json", data)


def _trace_file(root: Path, trace_id: str) -> Path:
    return root / "traces" / f"{trace_id}.json"


def _read_trace_links(root: Path) -> list[dict[str, Any]]:
    trace_dir_path = root / "traces"
    if not trace_dir_path.is_dir():
        return []
    links: list[dict[str, Any]] = []
    for path in sorted(trace_dir_path.glob("*.json")):
        try:
            links.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            links.append({"trace_id": path.stem, "status": "missing_trace"})
    return links


def _stats(links: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "trace_count": len(links),
        "failed_trace_count": sum(1 for link in links if link.get("status") == "failed"),
        "active_trace_count": sum(1 for link in links if link.get("status") == "active"),
    }


def _find_trace_owner(trace_id: str) -> str | None:
    root = task_dir()
    for task_root in audit_store._partition_dirs(root):  # noqa: SLF001 - shared internal scanner
        for path in (task_root / "traces").glob(f"{trace_id}.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                task_id = data.get("task_id")
                if isinstance(task_id, str):
                    return task_id
            except Exception:
                return task_root.name
    return None


def start_task(goal: str, *, mode: str = "explicit") -> dict[str, Any]:
    if mode not in {"explicit", "standalone"}:
        raise ValueError("mode must be explicit or standalone")
    task_id = generate_task_id()
    root = task_dir() / audit_store.partition_for(datetime.now().astimezone()) / task_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "traces").mkdir(exist_ok=True)
    audit_store.register_location(task_dir(), task_id, root)
    created_at = _now()
    data: dict[str, Any] = {
        "schema_version": 1,
        "task_id": task_id,
        "goal": goal,
        "mode": mode,
        "status": "active",
        "created_at": created_at,
        "updated_at": created_at,
        "finished_at": None,
        "summary": None,
        "trace_count": 0,
        "failed_trace_count": 0,
        "active_trace_count": 0,
    }
    audit_store.write_json_atomic(root / "task.json", data)
    return get_task(task_id)


def start_standalone_task(goal: str = "standalone tool call") -> dict[str, Any]:
    return start_task(goal, mode="standalone")


def register_trace(
    task_id: str,
    trace_id: str,
    *,
    kind: str,
    tool: str,
) -> dict[str, Any]:
    root = _require_task_root(task_id)
    task = _read_task_json(root)
    if task.get("status") != "active":
        raise TaskClosedError(task_id)

    existing_owner = _find_trace_owner(trace_id)
    if existing_owner is not None and existing_owner != task_id:
        raise TraceTaskConflictError(trace_id, task_id, existing_owner)

    path = _trace_file(root, trace_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    data = {
        "schema_version": 1,
        "task_id": task_id,
        "trace_id": trace_id,
        "kind": kind,
        "tool": tool,
        "started_at": _now(),
        "finished_at": None,
        "status": "active",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError:
        return json.loads(path.read_text(encoding="utf-8"))

    task.update(_stats(_read_trace_links(root)))
    _write_task_json(root, task)
    return data


def complete_trace(
    task_id: str,
    trace_id: str,
    *,
    status: str,
) -> dict[str, Any]:
    if status not in {"succeeded", "failed"}:
        raise ValueError("status must be succeeded or failed")
    root = _require_task_root(task_id)
    path = _trace_file(root, trace_id)
    if not path.exists():
        raise FileNotFoundError(f"trace link not found: {trace_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = status
    data["finished_at"] = _now()
    audit_store.write_json_atomic(path, data)

    task = _read_task_json(root)
    task.update(_stats(_read_trace_links(root)))
    _write_task_json(root, task)
    return data


def get_task(task_id: str) -> dict[str, Any]:
    root = _require_task_root(task_id)
    data = _read_task_json(root)
    traces = _read_trace_links(root)
    data.update(_stats(traces))
    data["task_path"] = str(root)
    data["traces"] = traces
    return data


def finish_task(
    task_id: str,
    *,
    summary: str | None = None,
    cancel: bool = False,
) -> dict[str, Any]:
    root = _require_task_root(task_id)
    task = _read_task_json(root)
    if task.get("status") != "active":
        return get_task(task_id)

    traces = _read_trace_links(root)
    stats = _stats(traces)
    if cancel:
        status = "cancelled"
    elif stats["trace_count"] == 0 or stats["failed_trace_count"] or stats["active_trace_count"]:
        status = "failed"
    else:
        status = "succeeded"
    task.update(stats)
    task["status"] = status
    task["summary"] = summary
    task["finished_at"] = _now()
    _write_task_json(root, task)
    return get_task(task_id)


def list_tasks(
    *,
    date: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    roots = audit_store._partition_dirs(task_dir())  # noqa: SLF001 - shared internal scanner
    tasks = [get_task(path.name) for path in roots if (path / "task.json").is_file()]
    if date is not None:
        tasks = [task for task in tasks if str(task.get("created_at", "")).startswith(date)]
    if status is not None:
        tasks = [task for task in tasks if task.get("status") == status]
    tasks.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    if limit is not None:
        tasks = tasks[:limit]
    return tasks
