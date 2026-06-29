"""Skill curation loop — auto-extract lessons from execution traces.

Phases (integrated in single CLI):
  Phase 1 — Read recent traces, call LLM, output JSON lesson proposals.
  Phase 2 — LLM-as-judge subcommand for per-trace success/failure verdict.
  Phase 3 — ``--apply`` flag to write approved proposals back to MEMORY.md.
  Phase 4 — ``test`` subcommand for curator quality verification.

Usage:
  python scripts/curator.py --trace-dir <path> [--count 5]
  python scripts/curator.py judge --trace-dir <path> --trace-id <id>
  python scripts/curator.py --apply --input <path>
  python scripts/curator.py test --trace-dir <path>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek-v4-flash"
MAX_COST_USD = 0.50
RETRY_BASE_S = 2
RETRY_MAX_S = 30
RETRY_MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_S = 60
CONNECT_TIMEOUT_S = 10

CURATION_DIR = Path.home() / ".computer-use" / "curations"
COST_LOG_PATH = Path.home() / ".computer-use" / "curator_cost_log.jsonl"
MEMORY_PATH = Path.cwd() / ".agents" / "memory" / "MEMORY.md"

# Rough pricing estimate (USD per 1M tokens) for common models.
# Keyed by model prefix; unknown models fall back to DEFAULT_COST_RATE.
COST_RATES: dict[str, tuple[float, float]] = {
    "deepseek": (0.15, 0.60),
    "gpt-4": (3.00, 15.00),
    "gpt-3.5": (0.50, 1.50),
    "claude": (3.00, 15.00),
}
DEFAULT_COST_RATE: tuple[float, float] = (0.50, 1.50)

# Regex for path-like strings that should be redacted before sending to LLM.
_PATH_PATTERN = re.compile(
    r"""
    (?P<drive>[A-Za-z]:\\ |\\.\\)?
    (?P<path>
        [\\/]?(?:Users|Users |home|tmp|temp|var|opt|usr|etc)
        [\\/][A-Za-z0-9._-]+
        (?:[\\/][A-Za-z0-9._\ \-]+)*
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_REDACTED_PATH = "<REDACTED_PATH>"

# ---------------------------------------------------------------------------
# Output schemas (for validation)
# ---------------------------------------------------------------------------

CURATOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["curator_run", "proposals"],
    "properties": {
        "curator_run": {
            "type": "object",
            "required": ["timestamp", "trace_count", "model", "total_cost_estimate_usd"],
            "properties": {
                "timestamp": {"type": "string"},
                "trace_count": {"type": "integer", "minimum": 0},
                "model": {"type": "string"},
                "total_cost_estimate_usd": {"type": "number", "minimum": 0},
            },
        },
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action", "target", "content", "evidence_trace_ids", "rationale", "metadata"],
                "properties": {
                    "action": {"type": "string", "enum": ["insert", "update", "delete"]},
                    "target": {
                        "type": "object",
                        "properties": {
                            "lesson_index": {"type": ["integer", "null"], "minimum": 1},
                            "after_index": {"type": ["integer", "null"], "minimum": 0},
                        },
                    },
                    "content": {"type": "string"},
                    "evidence_trace_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rationale": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        },
                    },
                },
            },
        },
    },
}

JUDGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["trace_id", "verdict", "confidence", "reasoning", "judged_at"],
    "properties": {
        "trace_id": {"type": "string"},
        "verdict": {"type": "string", "enum": ["success", "failure", "ambiguous"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"},
        "judged_at": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _redact_paths(text: str) -> str:
    return _PATH_PATTERN.sub(_REDACTED_PATH, text)


def _cluster_key(root: Path) -> str:
    """Return ``YYYY-MM-DD`` from a date-partitioned trace root path."""
    parts = root.parts
    for i, part in enumerate(parts):
        if part.isdigit() and len(part) == 4:
            tail = parts[i : i + 3]
            if len(tail) == 3:
                return "-".join(tail)
    # Fallback: use mtime of trace.jsonl, or the root name.
    trace_file = root / "trace.jsonl"
    try:
        mtime = trace_file.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except Exception:
        return "0000-00-00"


# ---------------------------------------------------------------------------
# Trace discovery
# ---------------------------------------------------------------------------


def find_recent_traces(trace_dir: Path, count: int) -> list[Path]:
    """Return the ``count`` most recent trace roots (date-partitioned layout).

    Structure: ``<trace_dir>/YYYY/MM/DD/<trace_id>/trace.jsonl``
    """
    candidates: list[tuple[str, Path]] = []  # (cluster_key, root_path)

    if not trace_dir.exists():
        raise SystemExit(f"trace directory not found: {trace_dir}")

    for year_dir in sorted(trace_dir.iterdir(), reverse=True):
        if not year_dir.is_dir() or not year_dir.name.isdigit() or len(year_dir.name) != 4:
            continue
        for month_dir in sorted(year_dir.iterdir(), reverse=True):
            if not month_dir.is_dir() or not month_dir.name.isdigit() or len(month_dir.name) != 2:
                continue
            for day_dir in sorted(month_dir.iterdir(), reverse=True):
                if not day_dir.is_dir() or not day_dir.name.isdigit() or len(day_dir.name) != 2:
                    continue
                for trace_root in sorted(day_dir.iterdir(), reverse=True):
                    if not trace_root.is_dir():
                        continue
                    trace_file = trace_root / "trace.jsonl"
                    if trace_file.is_file():
                        key = _cluster_key(trace_root)
                        candidates.append((key, trace_root))

    # Deduplicate by cluster_key (keep newest per day) then sort.
    seen: set[str] = set()
    unique: list[Path] = []
    for key, root in candidates:
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)

    return unique[:count]


def read_trace_records(trace_root: Path) -> list[dict[str, Any]]:
    """Read all JSONL lines from a trace root."""
    trace_file = trace_root / "trace.jsonl"
    if not trace_file.exists():
        return []
    with open(trace_file, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_trace_meta(trace_root: Path) -> dict[str, Any]:
    """Read meta.json from a trace root if present."""
    meta_file = trace_root / "meta.json"
    if not meta_file.exists():
        return {}
    with open(meta_file, "r", encoding="utf-8") as f:
        return json.load(f)


def build_trace_summary(trace_root: Path) -> dict[str, Any]:
    """Produce a deterministic summary for curator consumption."""
    records = read_trace_records(trace_root)
    meta = read_trace_meta(trace_root)

    trace_id = meta.get("trace_id") or trace_root.name
    goal = meta.get("goal")

    total = len(records)
    errors = [r for r in records if r.get("error_kind")]
    error_kinds: dict[str, int] = {}
    for rec in errors:
        k = rec.get("error_kind") or "unknown"
        error_kinds[k] = error_kinds.get(k, 0) + 1

    durations = [r.get("duration_ms", 0) for r in records if isinstance(r.get("duration_ms"), (int, float))]
    total_duration_ms = sum(durations)

    tools = list({r.get("tool", "") for r in records})

    retry_count = sum(
        1 for r in records
        if isinstance(r.get("step_index"), str) and ".retry." in r["step_index"]
    )

    # Sanitize args for LLM consumption (remove sensitive fields, redact paths).
    sanitized_steps = []
    for rec in records:
        args = rec.get("args", {})
        sanitized_args = _sanitize_args_for_llm(args)
        error_message = rec.get("error_message") or ""
        sanitized_steps.append({
            "step_index": rec.get("step_index"),
            "tool": rec.get("tool", ""),
            "args_keys": list(sanitized_args.keys()) if isinstance(sanitized_args, dict) else [],
            "duration_ms": rec.get("duration_ms", 0),
            "error_kind": rec.get("error_kind"),
            "error_message": _redact_paths(error_message),
        })

    return {
        "trace_id": trace_id,
        "goal": _redact_paths(str(goal or "")),
        "total_steps": total,
        "failed_steps": len(errors),
        "retry_steps": retry_count,
        "total_duration_ms": total_duration_ms,
        "error_kinds": error_kinds,
        "tools_used": tools,
        "steps": sanitized_steps,
    }


_SENSITIVE_ARGS_KEYS = {"text", "value", "password", "secret", "keys"}


def _sanitize_args_for_llm(args: Any) -> Any:
    """Remove sensitive values from args, keep only metadata."""
    if isinstance(args, dict):
        cleaned: dict[str, Any] = {}
        for key, value in args.items():
            key_lower = str(key).lower()
            if key_lower in _SENSITIVE_ARGS_KEYS:
                # Keep only type info, not the actual value.
                if isinstance(value, str):
                    cleaned[key] = f"<string of length {len(value)}>"
                elif isinstance(value, list):
                    cleaned[key] = f"<list of {len(value)} items>"
                else:
                    cleaned[key] = "<redacted>"
            elif isinstance(value, (dict, list)):
                cleaned[key] = _sanitize_args_for_llm(value)
            else:
                cleaned[key] = value
        return cleaned
    if isinstance(args, list):
        return [_sanitize_args_for_llm(item) for item in args]
    return args


# ---------------------------------------------------------------------------
# MEMORY.md parsing / writing
# ---------------------------------------------------------------------------


@dataclass
class LessonEntry:
    index: int
    line_start: int  # 0-based line index in file
    content: str


LESSON_SECTION_HEADING = "## 已验证的重要教训"


def parse_memory_lessons(memory_path: Path) -> list[LessonEntry]:
    """Parse numbered lessons from the ``## 已验证的重要教训`` section.

    Returns a list of LessonEntry sorted by index. Raises ValueError on
    unrecoverable format issues.
    """
    if not memory_path.is_file():
        raise ValueError(f"MEMORY.md not found: {memory_path}")

    lines = memory_path.read_text(encoding="utf-8").splitlines()
    section_start: int | None = None

    for i, line in enumerate(lines):
        if line.strip() == LESSON_SECTION_HEADING:
            section_start = i
            break

    if section_start is None:
        raise ValueError(f"section '{LESSON_SECTION_HEADING}' not found in {memory_path}")

    lessons: list[LessonEntry] = []
    numbered_re = re.compile(r"^(\d+)\.\s+(.+)")

    for i in range(section_start + 1, len(lines)):
        line = lines[i]
        m = numbered_re.match(line)
        if m:
            idx = int(m.group(1))
            content = m.group(2).strip()
            if lessons and idx != lessons[-1].index + 1:
                raise ValueError(
                    f"non-sequential lesson index at line {i + 1}: "
                    f"expected {lessons[-1].index + 1}, got {idx}"
                )
            lessons.append(LessonEntry(index=idx, line_start=i, content=content))
            continue
        # Allow continuations of the previous lesson (indented or wrapped text).
        if lessons and line.strip():
            # This is a continuation of the previous lesson if indented.
            stripped = line.strip()
            if stripped and (line.startswith("  ") or line.startswith("\t")):
                lessons[-1].content += " " + stripped

    if not lessons:
        raise ValueError(
            f"section '{LESSON_SECTION_HEADING}' contains no numbered list items"
        )

    return lessons


def apply_proposals(
    memory_path: Path,
    proposals: list[dict[str, Any]],
    lessons: list[LessonEntry],
) -> str:
    """Apply proposals to the memory file and return the updated content.

    Implements index-drift-safe order:
      1. Delete (largest index first, then rest in descending order)
      2. Update (in any order, indexes are stable after deletes)
      3. Insert (after_index descending order)
    """
    lines = memory_path.read_text(encoding="utf-8").splitlines()
    section_start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == LESSON_SECTION_HEADING:
            section_start = i
            break
    if section_start is None:
        raise ValueError(f"section '{LESSON_SECTION_HEADING}' not found")

    # Current lesson indexes and line ranges (inclusive start, exclusive end).
    lesson_ranges: list[tuple[int, int, int]] = []  # [(index, line_start, line_end_exclusive)]
    numbered_re = re.compile(r"^(\d+)\.\s+")
    lesson_index = section_start + 1
    lesson_count_observed = 0
    while lesson_index < len(lines):
        m = numbered_re.match(lines[lesson_index])
        if m:
            idx = int(m.group(1))
            start = lesson_index
            lesson_index += 1
            while lesson_index < len(lines):
                next_m = numbered_re.match(lines[lesson_index])
                if next_m:
                    break
                if not lines[lesson_index].strip():
                    # Check if next line is a new lesson.
                    if lesson_index + 1 < len(lines) and numbered_re.match(lines[lesson_index + 1]):
                        break
                lesson_index += 1
            lesson_ranges.append((idx, start, lesson_index))
            lesson_count_observed += 1
        else:
            lesson_index += 1

    if lesson_count_observed != len(lessons):
        raise ValueError(
            f"lesson count mismatch: parsed {len(lessons)} from memory but "
            f"found {lesson_count_observed} in file"
        )

    # Validate proposal indexes.
    valid_indexes = {entry.index for entry in lessons}
    for prop in proposals:
        action = prop.get("action")
        target = prop.get("target", {})
        if action in ("update", "delete"):
            idx = target.get("lesson_index")
            if idx is not None and idx not in valid_indexes:
                raise ValueError(
                    f"invalid lesson_index {idx} for {action}: "
                    f"valid indexes are {sorted(valid_indexes)}"
                )

    # Build operation lists.
    delete_ops: list[dict] = []
    update_ops: list[dict] = []
    insert_ops: list[dict] = []
    for prop in proposals:
        action = prop.get("action", "")
        if action == "delete":
            delete_ops.append(prop)
        elif action == "update":
            update_ops.append(prop)
        elif action == "insert":
            insert_ops.append(prop)

    # Step 1: Delete — process in descending index order.
    delete_ops.sort(
        key=lambda p: p.get("target", {}).get("lesson_index", 0) or 0,
        reverse=True,
    )
    # Track which line ranges are deleted (by original line_start).
    deleted_starts: set[int] = set()
    for op in delete_ops:
        idx = op.get("target", {}).get("lesson_index")
        for i, (lid, lstart, lend) in enumerate(lesson_ranges):
            if lid == idx:
                # Remove the lines.
                del lines[lstart:lend]
                deleted_starts.add(lstart)
                # Shift subsequent ranges.
                shift = lend - lstart
                for j in range(i + 1, len(lesson_ranges)):
                    old_start, old_end = lesson_ranges[j][1], lesson_ranges[j][2]
                    lesson_ranges[j] = (
                        lesson_ranges[j][0],
                        old_start - shift,
                        old_end - shift,
                    )
                lesson_ranges.pop(i)
                break

    # Rebuild lesson_ranges after deletes (line starts may have shifted).
    lesson_ranges = _rebuild_lesson_ranges(lines, section_start)

    # Step 2: Update — in original index order.
    for op in update_ops:
        idx = op.get("target", {}).get("lesson_index")
        new_content = op.get("content", "")
        for i, (lid, lstart, lend) in enumerate(lesson_ranges):
            if lid == idx:
                # Replace the content line(s) with new content.
                # Keep the first line with index intact, replace content after.
                header_match = numbered_re.match(lines[lstart])
                if not header_match:
                    raise ValueError(f"cannot find index header at line {lstart + 1}")
                prefix = header_match.group(0)
                # Rebuild the block: index line + content (wrapped at 80 chars? No, preserve as-is).
                new_lines = [f"{prefix}{new_content}"]
                lines[lstart:lend] = new_lines
                # Adjust subsequent ranges.
                shift = (lend - lstart) - len(new_lines)
                for j in range(i + 1, len(lesson_ranges)):
                    old_start, old_end = lesson_ranges[j][1], lesson_ranges[j][2]
                    lesson_ranges[j] = (
                        lesson_ranges[j][0],
                        old_start - shift,
                        old_end - shift,
                    )
                lesson_ranges[i] = (lid, lstart, lstart + len(new_lines))
                break

    # Step 3: Insert — process in descending after_index order.
    # If after_index is None, append to end.
    insert_ops.sort(
        key=lambda p: p.get("target", {}).get("after_index") or 999999,
        reverse=False,
    )
    # We process from end to start to avoid index drift.
    # Sort by after_index descending so later inserts don't shift earlier ones.
    insert_ops.sort(
        key=lambda p: (p.get("target", {}).get("after_index") is None,  # None last -> append
                       p.get("target", {}).get("after_index") or 999999),
        reverse=True,
    )
    for op in insert_ops:
        after_idx = op.get("target", {}).get("after_index")
        new_content = op.get("content", "")
        if after_idx is None:
            # Append to end. Find the last lesson range's end.
            if lesson_ranges:
                insert_line = lesson_ranges[-1][2]
            else:
                insert_line = section_start + 1
            # If there are trailing blank lines, insert before them.
            while insert_line < len(lines) and lines[insert_line].strip() == "":
                insert_line += 0  # We want to keep blanks after section start.
            # Actually, let's find the actual end of content.
            # Scan for blank lines after the last lesson.
            last_lesson_end = lesson_ranges[-1][2] if lesson_ranges else section_start + 1
            # Skip blank lines after last lesson.
            content_end = last_lesson_end
            while content_end < len(lines) and lines[content_end].strip() == "":
                content_end += 1
            insert_line = content_end
        else:
            insert_line = -1  # sentinel
            for lid, lstart, lend in lesson_ranges:
                if lid == after_idx:
                    insert_line = lend
                    break
            if insert_line == -1:
                raise ValueError(f"after_index {after_idx} not found in current lessons")

        new_index = (lesson_ranges[-1][0] + 1) if lesson_ranges else 1
        new_lines = [f"{new_index}. {new_content}"]
        lines[insert_line:insert_line] = new_lines
        # Adjust lesson_ranges.
        shift = len(new_lines)
        # Update ranges for items after insertion point.
        lesson_ranges.append((new_index, insert_line, insert_line + shift))
        # Renumber all lessons sequentially.
        lesson_ranges.sort(key=lambda x: x[1])
        for j, (_, lstart, lend) in enumerate(lesson_ranges):
            new_num = j + 1
            old_line = lines[lstart]
            old_rest = numbered_re.sub("", old_line, count=1).lstrip()
            lines[lstart] = f"{new_num}. {old_rest}"
            lesson_ranges[j] = (new_num, lstart, lend)

    # After all operations, renumber to fix any gaps.
    lesson_ranges.sort(key=lambda x: x[1])
    for j, (_, lstart, lend) in enumerate(lesson_ranges):
        new_num = j + 1
        old_line = lines[lstart]
        old_rest = numbered_re.sub("", old_line, count=1).lstrip()
        lines[lstart] = f"{new_num}. {old_rest}"

    return "\n".join(lines) + "\n"


def _rebuild_lesson_ranges(
    lines: list[str], section_start: int
) -> list[tuple[int, int, int]]:
    """Re-scan lines to build lesson ranges after modifications."""
    numbered_re = re.compile(r"^(\d+)\.\s+")
    ranges: list[tuple[int, int, int]] = []
    i = section_start + 1
    while i < len(lines):
        m = numbered_re.match(lines[i])
        if m:
            idx = int(m.group(1))
            start = i
            i += 1
            while i < len(lines):
                next_m = numbered_re.match(lines[i])
                if next_m:
                    break
                if not lines[i].strip():
                    if i + 1 < len(lines) and numbered_re.match(lines[i + 1]):
                        break
                i += 1
            ranges.append((idx, start, i))
        else:
            i += 1
    return ranges


# ---------------------------------------------------------------------------
# LLM client (OpenAI-compatible via httpx)
# ---------------------------------------------------------------------------


def _llm_headers() -> dict[str, str]:
    api_key = os.environ.get("LLM_API_KEY", "")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _llm_base() -> str:
    return os.environ.get("LLM_API_BASE", "https://api.deepseek.com/beta").rstrip("/")


def _curator_model() -> str:
    return os.environ.get("CURATOR_MODEL", DEFAULT_MODEL)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (chars / 4)."""
    return max(1, len(text) // 4)


def _lookup_rate(model: str) -> tuple[float, float]:
    for prefix, rate in COST_RATES.items():
        if model.lower().startswith(prefix):
            return rate
    return DEFAULT_COST_RATE


def _estimate_cost(input_text: str, output_text: str, model: str) -> float:
    input_tokens = _estimate_tokens(input_text)
    output_tokens = _estimate_tokens(output_text)
    in_rate, out_rate = _lookup_rate(model)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def _append_cost_log(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    record = {
        "timestamp": _now_iso(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
    }
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _llm_chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    response_json: bool = True,
) -> tuple[dict[str, Any], int, int]:
    """Call the LLM API with retry logic. Returns (parsed_json, input_tokens, output_tokens)."""
    import httpx

    model = model or _curator_model()
    base = _llm_base()
    url = f"{base}/v1/chat/completions"
    headers = _llm_headers()

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    if response_json:
        body["response_format"] = {"type": "json_object"}

    last_error: Exception | None = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(REQUEST_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
            ) as client:
                resp = client.post(url, headers=headers, json=body)
                if resp.status_code == 429 or resp.status_code == 503:
                    retry_after = RETRY_BASE_S * (2 ** attempt)
                    retry_after = min(retry_after, RETRY_MAX_S)
                    print(
                        f"  LLM rate-limited ({resp.status_code}), "
                        f"retrying in {retry_after}s (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})",
                        file=sys.stderr,
                    )
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                content = data["choices"][0]["message"]["content"]
                return json.loads(content), input_tokens, output_tokens

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 503):
                retry_after = min(RETRY_BASE_S * (2 ** attempt), RETRY_MAX_S)
                print(
                    f"  LLM rate-limited ({exc.response.status_code}), "
                    f"retrying in {retry_after}s (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS})",
                    file=sys.stderr,
                )
                time.sleep(retry_after)
                continue
            raise
        except (httpx.RequestError, json.JSONDecodeError, KeyError) as exc:
            last_error = exc
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                retry_after = min(RETRY_BASE_S * (2 ** attempt), RETRY_MAX_S)
                print(
                    f"  LLM call failed ({exc.__class__.__name__}): {exc}, "
                    f"retrying in {retry_after}s",
                    file=sys.stderr,
                )
                time.sleep(retry_after)
            else:
                raise

    raise RuntimeError(f"LLM API call failed after {RETRY_MAX_ATTEMPTS} attempts: {last_error}")


# ---------------------------------------------------------------------------
# JSON schema validation (lightweight, no external dep)
# ---------------------------------------------------------------------------


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Recursive schema validation. Returns list of errors."""
    errors: list[str] = []

    if schema.get("type") == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return errors
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"{path}: missing required field '{required}'")
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            if key in value:
                errors.extend(_validate_schema(value[key], prop_schema, f"{path}.{key}"))

    elif schema.get("type") == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
            return errors
        items_schema = schema.get("items", {})
        for i, item in enumerate(value):
            errors.extend(_validate_schema(item, items_schema, f"{path}[{i}]"))

    elif schema.get("type") in ("string", "number", "integer", "boolean"):
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
        }
        expected_type = type_map.get(schema["type"])
        if expected_type is not None and not isinstance(value, expected_type):
            errors.append(f"{path}: expected {schema['type']}, got {type(value).__name__} = {value!r}")
        # Check min/max for numbers.
        if isinstance(value, (int, float)):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(f"{path}: {value} < minimum {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    elif "enum" in schema:
        if value not in schema["enum"]:
            errors.append(f"{path}: expected one of {schema['enum']}, got {value!r}")

    elif schema.get("type") == ["integer", "null"]:
        if value is not None and not isinstance(value, int):
            errors.append(f"{path}: expected integer or null, got {type(value).__name__}")

    return errors


def validate_curator_output(data: Any, lesson_count: int) -> list[dict[str, Any]]:
    """Validate curator output JSON. Returns list of invalid proposals."""
    errors = _validate_schema(data, CURATOR_OUTPUT_SCHEMA)
    if errors:
        raise ValueError(f"output schema validation failed:\n" + "\n".join(errors))

    valid_indexes = set(range(1, lesson_count + 1))
    invalid_proposals: list[dict[str, Any]] = []
    for prop in data.get("proposals", []):
        action = prop.get("action")
        target = prop.get("target", {})

        if action in ("update", "delete"):
            idx = target.get("lesson_index")
            if idx is not None and idx not in valid_indexes:
                prop["_invalid_reason"] = (
                    f"lesson_index {idx} out of range ({1}-{lesson_count})"
                )
                invalid_proposals.append(prop)

        # Check evidence_trace_ids reference actual trace files (if trace_dir known).
        # We skip this check here since trace_dir context is not available.
        # The trace_dir check is done in the cmd handler.

    return invalid_proposals


def validate_judgment(data: Any) -> list[str]:
    return _validate_schema(data, JUDGMENT_SCHEMA)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


CURATOR_SYSTEM_PROMPT = """You are a Skill Curator for an AI agent that performs Windows GUI automation tasks.

Your job is to analyze execution traces and propose lessons to be added, updated, or deleted
from the project's MEMORY.md file. Lessons are reusable knowledge that helps future agents
avoid mistakes and work more effectively.

Rules:
1. Only propose a lesson when you have concrete evidence from the traces.
2. Lessons should be general and reusable — not specific to one application or window title.
3. Avoid redundancy with existing lessons.
4. Each proposal must cite evidence_trace_ids that support it.
5. Be concise and actionable.

Output JSON with this structure:
{
  "curator_run": {
    "timestamp": "<ISO timestamp>",
    "trace_count": <number>,
    "model": "<model name>",
    "total_cost_estimate_usd": <float>
  },
  "proposals": [
    {
      "action": "insert" | "update" | "delete",
      "target": {
        "lesson_index": <int or null>,
        "after_index": <int or null>
      },
      "content": "<lesson text>",
      "evidence_trace_ids": ["trace-id-1", "trace-id-2"],
      "rationale": "<why this lesson matters>",
      "metadata": {
        "severity": "high" | "medium" | "low"
      }
    }
  ]
}

For "insert": set target.lesson_index to null, optionally set target.after_index for position.
For "update": set target.lesson_index to the existing lesson number.
For "delete": set target.lesson_index to the existing lesson number to remove.

Be conservative: only propose a lesson if the evidence strongly supports it.
When all traces are successful with no issues, return an empty proposals list."""

JUDGE_SYSTEM_PROMPT = """You are a judge that determines whether an automated GUI task execution succeeded or failed.

Read the full execution trace and decide:
- "success": the task accomplished its goal without meaningful errors.
- "failure": the task did not accomplish its goal, or encountered unrecoverable errors.
- "ambiguous": the outcome is unclear or partially successful.

Output JSON:
{
  "trace_id": "<trace id>",
  "verdict": "success" | "failure" | "ambiguous",
  "confidence": <0.0-1.0>,
  "reasoning": "<explanation>"
}"""


def build_curator_prompt(
    traces: list[dict[str, Any]],
    memory_lessons: list[LessonEntry],
) -> str:
    """Build the user message for the curator LLM call."""
    parts: list[str] = [
        "# Current MEMORY.md Lessons\n",
    ]
    if memory_lessons:
        for lesson in memory_lessons:
            parts.append(f"{lesson.index}. {lesson.content}")
    else:
        parts.append("(No existing lessons.)")

    parts.append("\n# Recent Execution Traces\n")
    for t in traces:
        parts.append(f"## Trace: {t['trace_id']}")
        parts.append(f"- Goal: {t.get('goal', 'N/A')}")
        parts.append(f"- Steps: {t['total_steps']} total, {t['failed_steps']} failed, {t['retry_steps']} retries")
        parts.append(f"- Duration: {t['total_duration_ms']}ms")
        parts.append(f"- Errors: {t.get('error_kinds', {})}")
        parts.append(f"- Tools: {t.get('tools_used', [])}")
        parts.append("")
        for step in t.get("steps", []):
            parts.append(
                f"  [{step['step_index']}] tool={step['tool']} "
                f"args={step['args_keys']} duration={step['duration_ms']}ms "
                f"error={step.get('error_kind', 'none')}"
            )
            if step.get("error_message"):
                parts.append(f"       msg: {step['error_message'][:200]}")
        parts.append("")

    parts.append(
        "\nBased on the above traces and existing lessons, propose insert/update/delete "
        "operations for the MEMORY.md lesson list. Output valid JSON only."
    )
    return "\n".join(parts)


def build_judge_prompt(records: list[dict[str, Any]], trace_id: str, goal: str | None) -> str:
    """Build the user message for the judge LLM call."""
    parts: list[str] = [
        f"# Trace: {trace_id}",
        f"Goal: {goal or 'N/A'}",
        "\n## Steps\n",
    ]
    for rec in records:
        error = rec.get("error_kind") or "none"
        parts.append(
            f"[{rec.get('step_index')}] tool={rec.get('tool')} "
            f"duration={rec.get('duration_ms')}ms error={error}"
        )
        if rec.get("error_message"):
            parts.append(f"  error_msg: {rec['error_message'][:300]}")
        result = rec.get("result")
        if isinstance(result, dict):
            result_summary = {k: v for k, v in result.items()
                             if k not in ("screenshot_path", "ui_snapshot_path")}
            parts.append(f"  result: {json.dumps(result_summary, ensure_ascii=False)[:200]}")
    parts.append(
        "\nDetermine if this task succeeded, failed, or is ambiguous. Output valid JSON."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Curation output directory and writing
# ---------------------------------------------------------------------------


def _ensure_curation_dir() -> Path:
    CURATION_DIR.mkdir(parents=True, exist_ok=True)
    return CURATION_DIR


def _curation_path(timestamp: str | None = None) -> Path:
    ts = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    return _ensure_curation_dir() / f"{ts}.json"


def _latest_curation() -> Path | None:
    """Return the most recent curation file, or None."""
    if not CURATION_DIR.is_dir():
        return None
    files = sorted(CURATION_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def _find_trace_root(trace_dir: Path, trace_id: str) -> Path | None:
    """Find a trace root by ID within the date-partitioned trace directory."""
    if not trace_dir.exists():
        return None
    for year_dir in trace_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit() or len(year_dir.name) != 4:
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir() or not month_dir.name.isdigit() or len(month_dir.name) != 2:
                continue
            for day_dir in month_dir.iterdir():
                if not day_dir.is_dir() or not day_dir.name.isdigit() or len(day_dir.name) != 2:
                    continue
                for trace_root in day_dir.iterdir():
                    if trace_root.is_dir() and (trace_root / "trace.jsonl").is_file():
                        if trace_root.name == trace_id:
                            return trace_root
                        # Also check meta.json for the trace_id.
                        meta = trace_root / "meta.json"
                        if meta.exists():
                            try:
                                meta_data = json.loads(meta.read_text(encoding="utf-8"))
                                if meta_data.get("trace_id") == trace_id:
                                    return trace_root
                            except Exception:
                                pass
    return None


# ---------------------------------------------------------------------------
# Cost check / user confirmation
# ---------------------------------------------------------------------------


def _check_cost_and_confirm(
    input_text: str,
    output_text: str,
    model: str,
) -> bool:
    cost = _estimate_cost(input_text, output_text, model)
    print(f"  Estimated cost: ${cost:.4f} (cap: ${MAX_COST_USD:.2f})", file=sys.stderr)
    if cost > MAX_COST_USD:
        print(
            f"  WARNING: Estimated cost ${cost:.4f} exceeds cap ${MAX_COST_USD:.2f}. "
            f"Pass --force-cost to bypass.",
            file=sys.stderr,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Command: curate (Phase 1 + Phase 3 default)
# ---------------------------------------------------------------------------


def _cmd_curate(args: argparse.Namespace) -> None:
    trace_dir = Path(args.trace_dir)
    count = args.count
    model = args.model or _curator_model()

    print(f"Finding {count} most recent traces in {trace_dir}...", file=sys.stderr)
    trace_roots = find_recent_traces(trace_dir, count)
    if not trace_roots:
        raise SystemExit("no traces found")

    print(f"  Found {len(trace_roots)} trace(s)", file=sys.stderr)

    # Read trace summaries.
    traces = []
    for root in trace_roots:
        summary = build_trace_summary(root)
        traces.append(summary)

    # Read current MEMORY.md lessons.
    memory_path = args.memory or MEMORY_PATH
    try:
        lessons = parse_memory_lessons(memory_path)
        print(f"  Read {len(lessons)} existing lessons from MEMORY.md", file=sys.stderr)
    except ValueError as exc:
        print(f"  Warning: cannot parse MEMORY lessons: {exc}", file=sys.stderr)
        lessons = []

    # Build prompt.
    prompt = build_curator_prompt(traces, lessons)
    sys_prompt = CURATOR_SYSTEM_PROMPT

    if not args.force_cost:
        if not _check_cost_and_confirm(prompt, "{}", model):
            raise SystemExit("cost cap exceeded; rerun with --force-cost or reduce --count")

    print(f"  Calling LLM model={model}...", file=sys.stderr)
    result, input_tokens, output_tokens = _llm_chat([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ], model=model)

    # Inject curator_run metadata.
    result.setdefault("curator_run", {})
    result["curator_run"]["timestamp"] = _now_iso()
    result["curator_run"]["trace_count"] = len(traces)
    result["curator_run"]["model"] = model
    cost = _estimate_cost(prompt, json.dumps(result), model)
    result["curator_run"]["total_cost_estimate_usd"] = round(cost, 6)

    # Log cost.
    _append_cost_log(model, input_tokens, output_tokens, cost)

    # Validate output schema.
    try:
        invalid = validate_curator_output(result, len(lessons))
        if invalid:
            print(
                f"  Warning: {len(invalid)} proposal(s) marked invalid:\n"
                + "\n".join(f"    - {p.get('_invalid_reason', 'unknown')}" for p in invalid),
                file=sys.stderr,
            )
    except ValueError as exc:
        print(f"  Output schema validation failed: {exc}", file=sys.stderr)
        if args.strict:
            raise SystemExit("strict mode: aborting due to validation failure")
        print("  (continuing despite validation failure)", file=sys.stderr)

    # Write output.
    output_path = args.output or _curation_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Output written to {output_path}", file=sys.stderr)
    print(f"  Proposals: {len(result.get('proposals', []))}", file=sys.stderr)

    # If --apply was also given, run apply now.
    if args.apply:
        _write_apply(result, memory_path, dry_run=False)


# ---------------------------------------------------------------------------
# Command: judge (Phase 2)
# ---------------------------------------------------------------------------


def _cmd_judge(args: argparse.Namespace) -> None:
    trace_dir = Path(args.trace_dir)
    trace_id = args.trace_id
    model = args.model or _curator_model()

    trace_root = _find_trace_root(trace_dir, trace_id)
    if trace_root is None:
        raise SystemExit(f"trace {trace_id} not found in {trace_dir}")

    records = read_trace_records(trace_root)
    if not records:
        raise SystemExit(f"no records in trace {trace_id}")

    meta = read_trace_meta(trace_root)
    goal = meta.get("goal")

    prompt = build_judge_prompt(records, trace_id, goal)
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    print(f"  Judging trace {trace_id} with model={model}...", file=sys.stderr)
    result, _input_tokens, _output_tokens = _llm_chat(messages, model=model)

    # Ensure trace_id and judged_at are set.
    result.setdefault("trace_id", trace_id)
    result.setdefault("judged_at", _now_iso())

    # Validate output.
    errors = validate_judgment(result)
    if errors:
        print(
            f"  Warning: judgment schema validation errors:\n"
            + "\n".join(f"    - {e}" for e in errors),
            file=sys.stderr,
        )

    # Write judgment to trace root.
    judgment_path = trace_root / "judgment.json"
    with open(judgment_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Judgment written to {judgment_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Command: apply (Phase 3)
# ---------------------------------------------------------------------------


def _cmd_apply(args: argparse.Namespace) -> None:
    input_path: Path | None = args.input
    if input_path is None:
        latest = _latest_curation()
        if latest is None:
            raise SystemExit(
                "no --input specified and no curation files found in "
                f"{CURATION_DIR}"
            )
        input_path = latest
        print(f"  Using latest curation: {input_path}", file=sys.stderr)

    if not input_path.is_file():
        raise SystemExit(f"input file not found: {input_path}")

    data = json.loads(input_path.read_text(encoding="utf-8"))

    memory_path = args.memory or MEMORY_PATH
    _write_apply(data, memory_path, dry_run=args.dry_run)


def _write_apply(
    data: dict[str, Any],
    memory_path: Path,
    dry_run: bool = False,
) -> None:
    """Validate and apply curator output to MEMORY.md."""
    # Validate high-level schema.
    errors = _validate_schema(data, CURATOR_OUTPUT_SCHEMA)
    if errors:
        raise SystemExit(f"input data schema validation failed:\n" + "\n".join(errors))

    # Parse current lessons.
    try:
        lessons = parse_memory_lessons(memory_path)
    except ValueError as exc:
        raise SystemExit(f"cannot parse MEMORY.md: {exc}")

    # Validate proposal index validity.
    invalid_count = 0
    for prop in data.get("proposals", []):
        action = prop.get("action")
        target = prop.get("target", {})
        if action in ("update", "delete"):
            idx = target.get("lesson_index")
            if idx is not None and not any(l.index == idx for l in lessons):
                print(f"  Warning: skipping invalid proposal (lesson_index={idx} not found)", file=sys.stderr)
                prop["_skip"] = True
                invalid_count += 1

    # Filter out invalid proposals.
    valid_proposals = [p for p in data.get("proposals", []) if not p.get("_skip")]

    if not valid_proposals:
        print("  No valid proposals to apply.", file=sys.stderr)
        return

    # Apply.
    try:
        updated = apply_proposals(memory_path, valid_proposals, lessons)
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"apply failed: {exc}")

    # Write back only if content changed.
    current = memory_path.read_text(encoding="utf-8")
    if updated == current:
        print("  No changes to MEMORY.md (content unchanged).", file=sys.stderr)
        return

    if dry_run:
        print(updated)
        return

    memory_path.write_text(updated, encoding="utf-8")
    print(f"  Updated {memory_path}", file=sys.stderr)
    print(f"  {len(valid_proposals)} proposal(s) applied.", file=sys.stderr)
    print(f"  Review the diff before committing.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Command: test (Phase 4)
# ---------------------------------------------------------------------------


def _cmd_test(args: argparse.Namespace) -> None:
    """Run curator test suite against available traces and current MEMORY.md."""
    trace_dir = Path(args.trace_dir)
    count = args.count or 10
    model = args.model or _curator_model()
    memory_path = args.memory or MEMORY_PATH

    if not trace_dir.exists():
        raise SystemExit(f"trace directory not found: {trace_dir}")

    print("=" * 60, file=sys.stderr)
    print("Phase 4 — Curator Test Suite", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # -----------------------------------------------------------------------
    # 4a. Replay traces with known error patterns.
    # -----------------------------------------------------------------------
    print("\n[4a] Replay traces — capturing lessons from error patterns", file=sys.stderr)
    print(f"  Finding up to {count} traces...", file=sys.stderr)
    trace_roots = find_recent_traces(trace_dir, count)

    error_roots = []
    clean_roots = []
    for root in trace_roots:
        records = read_trace_records(root)
        has_errors = any(r.get("error_kind") for r in records)
        if has_errors:
            error_roots.append(root)
        else:
            clean_roots.append(root)

    print(f"  Error traces: {len(error_roots)}, Clean traces: {len(clean_roots)}", file=sys.stderr)

    if len(error_roots) < 3:
        print(
            f"  WARNING: Only {len(error_roots)} error traces found (need ≥3 for meaningful test). "
            f"Results may be inconclusive.",
            file=sys.stderr,
        )

    # Build trace summaries and run curator.
    all_traces = [build_trace_summary(r) for r in error_roots[:count]]

    try:
        lessons = parse_memory_lessons(memory_path)
    except ValueError as exc:
        print(f"  Warning: cannot parse lessons: {exc}", file=sys.stderr)
        lessons = []

    sys_prompt = CURATOR_SYSTEM_PROMPT

    if all_traces:
        prompt = build_curator_prompt(all_traces, lessons)

        # Skip cost check for test.
        print(f"  Calling LLM model={model}...", file=sys.stderr)
        result, _it, _ot = _llm_chat([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ], model=model)

        result.setdefault("curator_run", {})
        result["curator_run"]["timestamp"] = _now_iso()
        result["curator_run"]["trace_count"] = len(all_traces)
        result["curator_run"]["model"] = model

        proposals = result.get("proposals", [])
        actionable = [p for p in proposals if p.get("content") and p.get("evidence_trace_ids")]
        print(f"\n  -- Error trace curator produced {len(actionable)} actionable proposal(s)", file=sys.stderr)
        for p in actionable:
            print(f"     [{p['action']}] {p['content'][:100]}...", file=sys.stderr)

        # Validate schema.
        try:
            invalid = validate_curator_output(result, len(lessons))
            if invalid:
                print(f"  -- {len(invalid)} invalid proposal(s):", file=sys.stderr)
                for inv in invalid:
                    print(f"     - {inv.get('_invalid_reason', 'unknown')}", file=sys.stderr)
        except ValueError as exc:
            print(f"  -- Schema validation failed: {exc}", file=sys.stderr)
    else:
        print("  No traces to analyze.", file=sys.stderr)
        proposals = []

    # -----------------------------------------------------------------------
    # 4b. False positive check: run on clean traces.
    # -----------------------------------------------------------------------
    print("\n[4b] False positive check — clean traces", file=sys.stderr)
    if clean_roots:
        clean_traces = [build_trace_summary(r) for r in clean_roots[:5]]
        prompt2 = build_curator_prompt(clean_traces, lessons)
        result2, _it2, _ot2 = _llm_chat([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt2},
        ], model=model)

        fp_proposals = result2.get("proposals", [])
        print(f"  Clean traces produced {len(fp_proposals)} proposal(s)", file=sys.stderr)
        if fp_proposals:
            print("  WARNING: False positives detected:", file=sys.stderr)
            for p in fp_proposals:
                if p.get("evidence_trace_ids"):
                    print(f"    [{p['action']}] {p.get('content', '')[:100]}...", file=sys.stderr)
        else:
            print("  ✓ No false positives (empty proposals for clean traces)", file=sys.stderr)
    else:
        print("  SKIP: no clean traces available", file=sys.stderr)

    # -----------------------------------------------------------------------
    # 4c. Blind test (if we have trace data).
    # -----------------------------------------------------------------------
    print("\n[4c] Blind test — rediscovery rate (requires manual setup)", file=sys.stderr)
    print("  This test requires a prior version of MEMORY.md for comparison.", file=sys.stderr)
    print("  Run with --baseline-memory <path> to an older MEMORY.md version.", file=sys.stderr)
    if args.baseline_memory:
        baseline_path = Path(args.baseline_memory)
        if baseline_path.is_file():
            try:
                baseline_lessons = parse_memory_lessons(baseline_path)
                print(f"  Baseline has {len(baseline_lessons)} lessons", file=sys.stderr)
                # Compute removed lessons.
                current_texts = {l.content for l in lessons}
                removed = [l for l in baseline_lessons if l.content not in current_texts]
                print(f"  Removed lessons (from baseline): {len(removed)}", file=sys.stderr)
                for r in removed:
                    print(f"    - {r.index}. {r.content[:100]}", file=sys.stderr)
                if all_traces:
                    # Check if proposals recover any removed lessons.
                    proposal_texts = [p.get("content", "") for p in proposals]
                    recovered = [r for r in removed
                                 if any(r.content[:50] in pt or pt[:50] in r.content
                                        for pt in proposal_texts)]
                    ratio = len(recovered) / max(len(removed), 1)
                    print(f"  Rediscovery rate: {len(recovered)}/{len(removed)} = {ratio:.0%}", file=sys.stderr)
                    if ratio >= 2 / 3:
                        print(f"  ✓ Rediscovery rate >= 2/3", file=sys.stderr)
                    else:
                        print(f"  WARNING: Rediscovery rate < 2/3 threshold", file=sys.stderr)
            except ValueError as exc:
                print(f"  Error parsing baseline: {exc}", file=sys.stderr)
        else:
            print(f"  Baseline file not found: {baseline_path}", file=sys.stderr)
    else:
        print("  (no --baseline-memory provided)", file=sys.stderr)

    # Save test report to output dir.
    output_path = args.output or (_ensure_curation_dir() / f"test-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    report = {
        "test_timestamp": _now_iso(),
        "trace_dir": str(trace_dir),
        "error_traces_found": len(error_roots),
        "clean_traces_found": len(clean_roots),
        "proposals_count": len(proposals),
        "baseline_rediscovery_rate": None,
        "baseline_comparison": None,
    }
    if args.baseline_memory:
        baseline_path = Path(args.baseline_memory)
        if baseline_path.is_file():
            baseline_lessons = parse_memory_lessons(baseline_path)
            current_texts = {l.content for l in lessons}
            removed = [l for l in baseline_lessons if l.content not in current_texts]
            proposal_texts = [p.get("content", "") for p in proposals]
            recovered = [r for r in removed
                         if any(r.content[:50] in pt or pt[:50] in r.content
                                for pt in proposal_texts)]
            report["baseline_removed_count"] = len(removed)
            report["baseline_recovered_count"] = len(recovered)
            report["baseline_rediscovery_rate"] = round(len(recovered) / max(len(removed), 1), 3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nTest report saved to {output_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Skill curation loop — auto-extract lessons from execution traces.",
    )
    parser.add_argument(
        "--trace-dir",
        default=str(Path.home() / ".computer-use" / "traces"),
        help="Directory containing date-partitioned traces (default: ~/.computer-use/traces)",
    )
    parser.add_argument(
        "--memory",
        type=Path,
        default=MEMORY_PATH,
        help="Path to MEMORY.md (default: ./.agents/memory/MEMORY.md)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=("LLM model override (default: $CURATOR_MODEL env or '" + DEFAULT_MODEL + "')"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path for curation JSON",
    )

    sub = parser.add_subparsers(dest="command", required=False)

    # Default mode (curate)
    parser.add_argument(
        "--count", type=int, default=5,
        help="Number of recent traces to analyze (default: 5)",
    )
    parser.add_argument(
        "--threshold", type=int, default=3,
        help="Error count threshold",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply proposals to MEMORY.md after curation",
    )
    parser.add_argument(
        "--force-cost", action="store_true",
        help="Skip cost cap check",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Abort on schema validation failure",
    )

    # Judge subcommand
    p_judge = sub.add_parser("judge", help="Judge a single trace (Phase 2)")
    p_judge.add_argument("--trace-id", required=True, help="Trace ID to judge")
    p_judge.set_defaults(func=_cmd_judge)

    # Apply subcommand
    p_apply = sub.add_parser("apply", help="Apply a curation JSON to MEMORY.md (Phase 3)")
    p_apply.add_argument("--input", type=Path, default=None, help="Curation JSON input file")
    p_apply.add_argument("--dry-run", action="store_true", help="Print updated MEMORY.md without writing")
    p_apply.set_defaults(func=_cmd_apply)

    # Test subcommand
    p_test = sub.add_parser("test", help="Run curator test suite (Phase 4)")
    p_test.add_argument("--baseline-memory", type=Path, default=None, help="Older MEMORY.md for blind test")
    p_test.set_defaults(func=_cmd_test)

    return parser


def main(argv: list[str] | None = None) -> None:
    _force_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "judge":
        args.func(args)
    elif args.command == "apply":
        args.func(args)
    elif args.command == "test":
        args.func(args)
    else:
        # Default: curate mode
        _cmd_curate(args)


if __name__ == "__main__":
    main(sys.argv[1:])
