"""Standardized retrospective report persistence (write side).

Separate from ``review.py`` (read-only trace summaries). ``save_review`` wraps an
agent-composed markdown body with metadata plus an environment/evidence snapshot
and writes a single ``.md`` (YAML frontmatter + body) to the configured
``review_dir`` for easy, uniform feedback collection after distribution.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from computer_use.config import load_config

logger = logging.getLogger(__name__)

#: Upper bound on the agent-composed report body. 500KB of plain text is far more
#: than any retrospective needs; base64/images never belong in the body.
MAX_REPORT_MARKDOWN_BYTES = 500_000

#: Controlled vocabulary for ``outcome`` so reports aggregate cleanly.
VALID_OUTCOMES = ("succeeded", "partial", "failed", "unknown")

_PRIVACY_NOTICE = (
    "<!-- This report was auto-generated. It contains file paths, an environment "
    "snapshot, and dependency info. Review before sharing. -->"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _mcp_version() -> str:
    try:
        from importlib.metadata import version

        return version("computer-use")
    except Exception as exc:  # pragma: no cover
        logger.warning("could not resolve mcp version: %s", exc)
        return "unknown"


def _doctor_snapshot() -> dict[str, Any]:
    """Concise environment snapshot, captured at report-generation time."""
    captured_at = _now_iso()
    try:
        from computer_use import doctor

        result = doctor.run_doctor()
        return {
            "captured_at": captured_at,
            "status": result.get("status"),
            "checks": result.get("checks"),
        }
    except Exception as exc:  # pragma: no cover
        logger.warning("doctor snapshot failed: %s", exc)
        return {"captured_at": captured_at, "error": str(exc)}


def _task_evidence(task_id: str) -> dict[str, Any]:
    """Resolve task-session summary + trace artifact paths. Safe-degrades."""
    try:
        from computer_use import review, trace as trace_module

        summary = review.review_task_session(task_id, detail=False)
        artifacts: list[dict[str, Any]] = []
        for link in summary.get("traces", []):
            trace_id = link.get("trace_id")
            if isinstance(trace_id, str):
                try:
                    artifacts.append(trace_module.artifact_manifest(trace_id))
                except Exception as exc:  # pragma: no cover
                    logger.debug("artifact_manifest failed for %s: %s", trace_id, exc)
        return {
            "task_id": task_id,
            "status": summary.get("status"),
            "goal": summary.get("goal"),
            "trace_count": summary.get("trace_count"),
            "failed_trace_count": summary.get("failed_trace_count"),
            "total_steps": summary.get("total_steps"),
            "error_distribution": summary.get("error_distribution"),
            "artifacts": artifacts,
        }
    except Exception as exc:
        logger.warning("task evidence enrichment failed: %s", exc)
        return {"task_id": task_id, "error": str(exc)}


def save_review(
    report_markdown: str,
    outcome: str = "unknown",
    task_id: str | None = None,
    client: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Persist a standardized retrospective report and return its path.

    The agent composes ``report_markdown`` (the narrative/analysis); this wraps it
    with metadata, a doctor environment snapshot, and — when ``task_id`` is given —
    trace/task evidence paths, then writes one ``.md`` to ``review_dir``. Enrichment
    failures degrade safely; the report is still written. Never raises.
    """
    if not isinstance(report_markdown, str) or not report_markdown.strip():
        return {"saved": False, "error": "report_markdown must be a non-empty string"}
    if len(report_markdown.encode("utf-8")) > MAX_REPORT_MARKDOWN_BYTES:
        return {
            "saved": False,
            "error": f"report_markdown exceeds max length ({MAX_REPORT_MARKDOWN_BYTES} bytes)",
        }

    if outcome not in VALID_OUTCOMES:
        outcome = "unknown"

    now = datetime.now(timezone.utc)
    metadata: dict[str, Any] = {
        "created_at": now.isoformat(timespec="milliseconds"),
        "mcp_version": _mcp_version(),
        "outcome": outcome,
        "client": client,
        "model": model,
        "task_id": task_id,
        "doctor": _doctor_snapshot(),
    }
    if task_id:
        metadata["task_evidence"] = _task_evidence(task_id)

    try:
        review_dir = Path(load_config()["review_dir"])
        review_dir.mkdir(parents=True, exist_ok=True)
        if task_id:
            # Deterministic name so a re-run for the same task overwrites.
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(task_id))
            filename = f"review_{safe}.md"
        else:
            filename = f"review_{now.strftime('%Y%m%dT%H%M%S_%f')[:-3]}.md"
        review_path = review_dir / filename

        frontmatter = yaml.safe_dump(
            metadata, allow_unicode=True, sort_keys=False
        ).rstrip("\n")
        body = report_markdown.rstrip("\n")
        content = f"---\n{frontmatter}\n---\n\n{body}\n\n{_PRIVACY_NOTICE}\n"
        review_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        logger.exception("save_review failed")
        return {"saved": False, "error": str(exc)}

    return {
        "saved": True,
        "review_path": str(review_path),
        "review_dir": str(review_dir),
    }
