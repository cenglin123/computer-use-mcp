"""Structured execution tracing for the Computer Use MCP Server.

Every tool invocation (atomic, batch sub-step, or run_task_plan step) writes a
single JSONL record under ``<trace_dir>/<trace_id>/trace.jsonl``.  A task-level
call (``run_task_plan``) also generates a human-readable ``report.md``.

Trace IDs are generated per call and shared across sub-steps inside one
``batch`` or ``run_task_plan`` invocation.  Single atomic tool calls get their
own one-record trace.
"""

from __future__ import annotations

import json
import re
import secrets
import string
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from computer_use.config import load_config


_ALPHANUM = string.ascii_lowercase + string.digits
_TRACE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_WINDOWS_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_SENSITIVE_INPUT_KEYS = {"text", "value", "password", "secret"}
_ARTIFACT_KINDS = {"screenshots", "snapshots"}


def generate_trace_id() -> str:
    """Return a trace ID: ``YYYYMMDD-HHMMSS-XXXXXX``."""
    now = datetime.now(timezone.utc)
    slug = "".join(secrets.choice(_ALPHANUM) for _ in range(6))
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{slug}"


def trace_dir() -> Path:
    """Return the configured trace directory, creating it if needed."""
    config = load_config()
    path = config.get("trace_dir", Path.home() / ".computer-use" / "traces")
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_trace_id(trace_id: str) -> str:
    """Reject trace IDs that are unsafe as a single Windows path component."""
    if not isinstance(trace_id, str) or not _TRACE_ID_PATTERN.fullmatch(trace_id):
        raise ValueError("Invalid trace_id")
    if trace_id.endswith("."):
        raise ValueError("Invalid trace_id")
    if trace_id.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES:
        raise ValueError("Invalid trace_id")
    return trace_id


def trace_root(trace_id: str) -> Path:
    """Return ``<trace_dir>/<trace_id>`` creating the trace root only."""
    validate_trace_id(trace_id)
    root = trace_dir() / trace_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def artifact_dir(trace_id: str, kind: str) -> Path:
    """Return a trace artifact subdirectory, creating only the requested kind."""
    if kind not in _ARTIFACT_KINDS:
        raise ValueError(f"Invalid artifact kind: {kind}")
    path = trace_root(trace_id) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifact_manifest(trace_id: str) -> dict[str, Any]:
    """Return existing trace artifact paths without creating missing files."""
    validate_trace_id(trace_id)
    root = trace_dir() / trace_id
    trace_path = root / "trace.jsonl"
    report_path = root / "report.md"

    def files(kind: str) -> list[str]:
        directory = root / kind
        if not directory.is_dir():
            return []
        return [str(path) for path in sorted(directory.iterdir()) if path.is_file()]

    return {
        "trace_id": trace_id,
        "artifact_root": str(root),
        "trace_path": str(trace_path) if trace_path.is_file() else None,
        "report_path": str(report_path) if report_path.is_file() else None,
        "screenshots": files("screenshots"),
        "snapshots": files("snapshots"),
    }


def write_trace_meta(trace_id: str, goal: str | None = None) -> Path:
    """Persist task metadata such as the goal to ``<trace_id>/meta.json``."""
    root = trace_root(trace_id)
    meta_path = root / "meta.json"
    data: dict[str, Any] = {"trace_id": trace_id}
    if goal is not None:
        data["goal"] = goal
    meta_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return meta_path


def read_trace_meta(trace_id: str) -> dict[str, Any]:
    """Read task metadata for ``trace_id`` if it exists."""
    validate_trace_id(trace_id)
    meta_path = trace_dir() / trace_id / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # pragma: no cover
        return {}


@dataclass
class TraceRecord:
    """A single step in an execution trace."""

    trace_id: str
    step_index: int | str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | str | None = None
    start_time: str = ""
    duration_ms: int = 0
    screenshot_path: str | None = None
    ui_snapshot_path: str | None = None
    error_kind: str | None = None
    error_message: str | None = None
    replayable: bool = True

    def __post_init__(self) -> None:
        if not self.start_time:
            self.start_time = datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _serialize(value: Any) -> Any:
    """Serialize datetimes and Paths for JSON."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="milliseconds")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _redacted_value(value: Any) -> dict[str, Any]:
    length = len(value) if isinstance(value, (str, bytes, list, tuple)) else None
    redacted: dict[str, Any] = {"redacted": True}
    if length is not None:
        redacted["length"] = length
    return redacted


def _sanitize_arguments(value: Any) -> tuple[Any, list[str], bool]:
    secrets: list[str] = []
    redacted = False

    def visit(item: Any) -> Any:
        nonlocal redacted
        if isinstance(item, dict):
            cleaned: dict[str, Any] = {}
            for key, child in item.items():
                if str(key).lower() in _SENSITIVE_INPUT_KEYS:
                    if isinstance(child, str) and child:
                        secrets.append(child)
                    cleaned[key] = _redacted_value(child)
                    redacted = True
                else:
                    cleaned[key] = visit(child)
            return cleaned
        if isinstance(item, list):
            return [visit(child) for child in item]
        if isinstance(item, tuple):
            return [visit(child) for child in item]
        return item

    return visit(value), secrets, redacted


def _redact_secret_strings(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, str):
        cleaned = value
        for secret in sorted(secrets, key=len, reverse=True):
            cleaned = cleaned.replace(secret, "<redacted>")
        return cleaned
    if isinstance(value, dict):
        return {
            key: _redact_secret_strings(child, secrets)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_secret_strings(child, secrets) for child in value]
    if isinstance(value, tuple):
        return [_redact_secret_strings(child, secrets) for child in value]
    return value


def sanitize_for_logging(args: dict[str, Any]) -> dict[str, Any]:
    """Return arguments with typed/form values removed for safe logging."""
    cleaned, _, _ = _sanitize_arguments(args)
    return cleaned


def sanitize_message(args: dict[str, Any], message: str) -> str:
    """Remove input values from an exception or diagnostic message."""
    _, secrets, _ = _sanitize_arguments(args)
    return _redact_secret_strings(message, secrets)


def write_record(record: TraceRecord) -> Path:
    """Append a trace record to ``<trace_id>/trace.jsonl``."""
    root = trace_root(record.trace_id)
    trace_file = root / "trace.jsonl"
    data = {k: _serialize(v) for k, v in asdict(record).items()}
    cleaned_args, secrets, redacted = _sanitize_arguments(data["args"])
    data["args"] = cleaned_args
    data["result"] = _redact_secret_strings(data["result"], secrets)
    data["error_message"] = _redact_secret_strings(
        data["error_message"], secrets
    )
    data["replayable"] = bool(data["replayable"]) and not redacted
    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
    return trace_file


def record_step(
    trace_id: str,
    step_index: int | str,
    tool: str,
    args: dict[str, Any],
    result: dict[str, Any] | str | None = None,
    duration_ms: int = 0,
    screenshot_path: str | Path | None = None,
    ui_snapshot_path: str | Path | None = None,
    error_kind: str | None = None,
    error_message: str | None = None,
    start_time: str | None = None,
) -> TraceRecord:
    """Create and persist a trace record."""
    record = TraceRecord(
        trace_id=trace_id,
        step_index=step_index,
        tool=tool,
        args=args,
        result=result,
        duration_ms=duration_ms,
        screenshot_path=str(screenshot_path) if screenshot_path else None,
        ui_snapshot_path=str(ui_snapshot_path) if ui_snapshot_path else None,
        error_kind=error_kind,
        error_message=error_message,
        start_time=start_time or datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )
    write_record(record)
    return record


def read_trace(trace_id: str) -> list[dict[str, Any]]:
    """Read all records for a trace ID."""
    validate_trace_id(trace_id)
    trace_file = trace_dir() / trace_id / "trace.jsonl"
    if not trace_file.exists():
        return []
    with open(trace_file, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def generate_report(
    trace_id: str,
    goal: str | None = None,
    final_state_path: str | Path | None = None,
) -> Path:
    """Generate a human-readable ``report.md`` for a completed task."""
    records = read_trace(trace_id)
    root = trace_root(trace_id)
    report_path = root / "report.md"

    lines: list[str] = [
        "# 任务执行复盘报告",
        "",
        f"**trace_id**: `{trace_id}`",
        f"**目标**: {goal or '（未提供）'}",
        f"**生成时间**: {datetime.now(timezone.utc).isoformat(timespec='milliseconds')}",
        f"**总步骤数**: {len(records)}",
        "",
        "## 步骤概览",
        "",
        "| 步骤 | 工具 | 耗时(ms) | 结果 | 错误 |",
        "|------|------|----------|------|------|",
    ]

    for rec in records:
        step = rec.get("step_index", 0)
        tool = rec.get("tool", "")
        duration = rec.get("duration_ms", 0)
        error = rec.get("error_kind") or "无"
        result = rec.get("result")
        if rec.get("error_kind"):
            result_summary = f"failed: {rec['error_kind']}"
        elif isinstance(result, dict):
            if "error" in result:
                result_summary = f"error: {result['error']}"
            else:
                result_summary = "ok"
        else:
            result_summary = str(result)[:40]
        lines.append(f"| {step} | {tool} | {duration} | {result_summary} | {error} |")

    errors = [r for r in records if r.get("error_kind")]
    lines.extend([
        "",
        "## 错误与改进建议",
        "",
    ])
    if errors:
        for rec in errors:
            lines.append(
                f"- 步骤 {rec.get('step_index')}: `{rec.get('error_kind')}` — "
                f"{rec.get('error_message') or '无详细描述'}"
            )
    else:
        lines.append("本次执行未记录错误。")

    lines.extend([
        "",
        "## 截图与快照索引",
        "",
    ])
    for rec in records:
        if rec.get("screenshot_path") or rec.get("ui_snapshot_path"):
            lines.append(f"- 步骤 {rec.get('step_index')}:")
            if rec.get("screenshot_path"):
                lines.append(f"  - screenshot: `{rec['screenshot_path']}`")
            if rec.get("ui_snapshot_path"):
                lines.append(f"  - snapshot: `{rec['ui_snapshot_path']}`")

    if final_state_path:
        lines.extend([
            "",
            "## 最终状态",
            "",
            f"- 最终快照: `{final_state_path}`",
        ])

    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
