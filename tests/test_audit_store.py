"""Tests for partitioned audit storage helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from computer_use import audit_store


def test_partition_for_uses_year_month_day() -> None:
    moment = datetime(2026, 6, 16, 10, 15, tzinfo=timezone.utc)

    assert audit_store.partition_for(moment) == Path("2026") / "06" / "16"


def test_locator_name_is_sha256_json_filename() -> None:
    name = audit_store.locator_name("trace/custom-id")

    assert re.fullmatch(r"[0-9a-f]{64}\.json", name)


def test_register_location_resolves_original_identifier(tmp_path: Path) -> None:
    target = tmp_path / "2026" / "06" / "16" / "trace-001"
    target.mkdir(parents=True)

    locator = audit_store.register_location(tmp_path, "trace-001", target)

    assert locator.parent == tmp_path / ".index"
    assert audit_store.resolve_location(tmp_path, "trace-001") == target


def test_register_location_is_idempotent_for_same_target(tmp_path: Path) -> None:
    target = tmp_path / "2026" / "06" / "16" / "trace-001"
    target.mkdir(parents=True)

    first = audit_store.register_location(tmp_path, "trace-001", target)
    second = audit_store.register_location(tmp_path, "trace-001", target)

    assert first == second


def test_register_location_rejects_conflicting_target(tmp_path: Path) -> None:
    first = tmp_path / "2026" / "06" / "16" / "trace-001"
    second = tmp_path / "2026" / "06" / "17" / "trace-001"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    audit_store.register_location(tmp_path, "trace-001", first)

    with pytest.raises(audit_store.LocationConflictError):
        audit_store.register_location(tmp_path, "trace-001", second)


def test_resolve_location_rejects_locator_path_escape(tmp_path: Path) -> None:
    index = tmp_path / ".index"
    index.mkdir()
    locator = index / audit_store.locator_name("escape")
    locator.write_text(
        json.dumps({"identifier": "escape", "relative_path": "../escape"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes"):
        audit_store.resolve_location(tmp_path, "escape")


def test_rebuild_location_index_scans_partitioned_directories(tmp_path: Path) -> None:
    trace_root = tmp_path / "2026" / "06" / "16" / "trace-001"
    trace_root.mkdir(parents=True)
    (trace_root / "meta.json").write_text(
        json.dumps({"trace_id": "trace-001"}),
        encoding="utf-8",
    )
    legacy = tmp_path / "legacy-trace"
    legacy.mkdir()
    (tmp_path / ".tmp").write_text("ignored", encoding="utf-8")

    result = audit_store.rebuild_location_index(tmp_path, "trace_id")

    assert result["scanned"] == 1
    assert result["created"] == 1
    assert result["invalid"] == 0
    assert audit_store.resolve_location(tmp_path, "trace-001") == trace_root
    assert audit_store.resolve_location(tmp_path, "legacy-trace") is None
