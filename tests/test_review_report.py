"""Tests for the standardized retrospective report writer."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from computer_use import review_report


@pytest.fixture(autouse=True)
def _tmp_review_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(review_report, "load_config", lambda: {"review_dir": str(tmp_path)})
    # Deterministic, fast environment snapshot.
    monkeypatch.setattr(
        review_report,
        "_doctor_snapshot",
        lambda: {"captured_at": "2026-06-21T00:00:00.000+00:00", "status": "ok", "checks": []},
    )
    return tmp_path


def _frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    parts = text.split("---\n", 2)
    return yaml.safe_load(parts[1]), text


def test_save_review_without_task_id(tmp_path):
    res = review_report.save_review("# Retro\nbody", outcome="succeeded")
    assert res["saved"] is True
    p = Path(res["review_path"])
    assert p.exists() and p.suffix == ".md"
    assert not list(tmp_path.glob("*.json"))  # single-file, no sidecar
    meta, text = _frontmatter(p)
    assert meta["outcome"] == "succeeded"
    assert meta["mcp_version"]
    assert meta["created_at"]
    assert meta["doctor"]["captured_at"]
    assert "task_evidence" not in meta
    assert "Review before sharing" in text


def test_invalid_outcome_falls_back_to_unknown():
    res = review_report.save_review("body", outcome="weird")
    meta, _ = _frontmatter(Path(res["review_path"]))
    assert meta["outcome"] == "unknown"


def test_empty_report_rejected():
    res = review_report.save_review("   ")
    assert res["saved"] is False
    assert "non-empty" in res["error"]


def test_oversize_report_rejected():
    big = "x" * (review_report.MAX_REPORT_MARKDOWN_BYTES + 1)
    res = review_report.save_review(big)
    assert res["saved"] is False
    assert "max length" in res["error"]


def test_task_id_enrichment_and_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review_report,
        "_task_evidence",
        lambda tid: {"task_id": tid, "status": "succeeded", "artifacts": []},
    )
    r1 = review_report.save_review("first", outcome="succeeded", task_id="task-abc")
    p1 = Path(r1["review_path"])
    assert p1.name == "review_task-abc.md"
    meta1, _ = _frontmatter(p1)
    assert meta1["task_evidence"]["task_id"] == "task-abc"

    r2 = review_report.save_review("second", outcome="failed", task_id="task-abc")
    assert r2["review_path"] == r1["review_path"]  # deterministic name
    body = p1.read_text(encoding="utf-8")
    assert "second" in body and "first" not in body  # overwritten
    assert len(list(tmp_path.glob("review_*.md"))) == 1


def test_enrichment_failure_degrades(monkeypatch):
    def boom(task_id, detail=False):
        raise RuntimeError("trace store down")

    monkeypatch.setattr("computer_use.review.review_task_session", boom)
    res = review_report.save_review("body", task_id="task-x")
    assert res["saved"] is True  # main report still written
    meta, _ = _frontmatter(Path(res["review_path"]))
    assert meta["task_evidence"]["error"]
