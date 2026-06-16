"""Partitioned audit storage helpers for traces and task sessions."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditStoreError(Exception):
    """Base error for audit store operations."""


class LocationConflictError(AuditStoreError):
    """Raised when an identifier already points at a different location."""


def partition_for(moment: datetime) -> Path:
    """Return a ``YYYY/MM/DD`` partition path for ``moment``."""
    if moment.tzinfo is None:
        moment = moment.astimezone()
    else:
        moment = moment.astimezone()
    return Path(moment.strftime("%Y")) / moment.strftime("%m") / moment.strftime("%d")


def locator_name(identifier: str) -> str:
    """Return a filesystem-safe locator filename for an arbitrary identifier."""
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{digest}.json"


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write JSON via same-directory temp file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temp.replace(path)


def _assert_inside(root: Path, target: Path) -> Path:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes audit root: {target}") from exc
    return target_resolved


def _relative_path(root: Path, target: Path) -> str:
    target_resolved = _assert_inside(root, target)
    return target_resolved.relative_to(root.resolve()).as_posix()


def _index_dir(root: Path) -> Path:
    return root / ".index"


def _locator_path(root: Path, identifier: str) -> Path:
    return _index_dir(root) / locator_name(identifier)


def register_location(root: Path, identifier: str, target: Path) -> Path:
    """Register ``identifier`` -> ``target`` under ``root/.index``."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    relative = _relative_path(root, target)
    locator = _locator_path(root, identifier)
    if locator.exists():
        existing = json.loads(locator.read_text(encoding="utf-8"))
        existing_relative = existing.get("relative_path")
        if existing_relative == relative:
            return locator
        raise LocationConflictError(
            f"identifier {identifier!r} already points to {existing_relative!r}"
        )

    write_json_atomic(
        locator,
        {
            "schema_version": 1,
            "identifier": identifier,
            "relative_path": relative,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        },
    )
    return locator


def resolve_location(root: Path, identifier: str) -> Path | None:
    """Resolve an identifier through ``root/.index`` without scanning."""
    root = Path(root)
    locator = _locator_path(root, identifier)
    if not locator.exists():
        return None
    data = json.loads(locator.read_text(encoding="utf-8"))
    relative = data.get("relative_path")
    if not isinstance(relative, str):
        raise ValueError(f"invalid locator for {identifier!r}")
    target = root / relative
    return _assert_inside(root, target)


def _partition_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    found: list[Path] = []
    for year in root.iterdir():
        if not year.is_dir() or not year.name.isdigit() or len(year.name) != 4:
            continue
        for month in year.iterdir():
            if not month.is_dir() or not month.name.isdigit() or len(month.name) != 2:
                continue
            for day in month.iterdir():
                if not day.is_dir() or not day.name.isdigit() or len(day.name) != 2:
                    continue
                found.extend(path for path in day.iterdir() if path.is_dir())
    return found


def _identifier_from_directory(path: Path, id_field: str) -> str | None:
    for metadata_name in ("meta.json", "task.json"):
        metadata_path = path / metadata_name
        if not metadata_path.is_file():
            continue
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        value = data.get(id_field)
        if isinstance(value, str) and value:
            return value
    return path.name


def rebuild_location_index(root: Path, id_field: str) -> dict[str, int]:
    """Rebuild missing locators by scanning partitioned directories."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stats = {
        "scanned": 0,
        "created": 0,
        "unchanged": 0,
        "conflicts": 0,
        "invalid": 0,
    }
    for directory in _partition_dirs(root):
        try:
            identifier = _identifier_from_directory(directory, id_field)
            if not identifier:
                stats["invalid"] += 1
                continue
            stats["scanned"] += 1
            locator = _locator_path(root, identifier)
            existed = locator.exists()
            register_location(root, identifier, directory)
            stats["unchanged" if existed else "created"] += 1
        except LocationConflictError:
            stats["conflicts"] += 1
        except Exception:
            stats["invalid"] += 1
    return stats
