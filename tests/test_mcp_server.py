"""Tests for MCP server tool dispatch."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from computer_use.mcp_server import TOOLS, _call_tool
from computer_use.tools import schemas as schemas_module


@pytest.fixture(autouse=True)
def _patch_trace_dir(tmp_path, monkeypatch):
    # Load runner before tests temporarily replace mcp_server._call_tool.
    import computer_use.runner as runner_module
    import computer_use.trace as trace_module

    del runner_module
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)


def test_tools_listed() -> None:
    names = {t.name for t in TOOLS}
    assert names == {
        "screenshot",
        "get_monitors",
        "get_ui_snapshot",
        "click",
        "click_on_screenshot",
        "crop_screenshot",
        "move_to",
        "scroll",
        "type",
        "key_combo",
        "mouse_down",
        "mouse_up",
        "drag",
        "key_down",
        "key_up",
        "press_key",
        "find_control",
        "inspect_point",
        "wait_for_window",
        "wait_for_control",
        "activate_window",
        "sleep",
        "launch_app",
        "click_by_uid",
        "click_by_text",
        "open_menu",
        "fill_form",
        "scroll_until",
        "run_task_plan",
        "retry_step",
        "review_task",
        "start_task",
        "finish_task",
        "get_task",
        "list_tasks",
        "review_task_session",
        "save_review",
        "add_command_whitelist",
        "add_window_exception",
        "batch",
    }


def test_save_review_excluded_from_task_context() -> None:
    # save_review is a meta/reporting tool: exempt from the missing_task_id guard
    # and never auto-injected with task_id (like review_task / task management).
    assert "save_review" in schemas_module._TASK_CONTEXT_EXCLUDED_TOOLS


def test_save_review_routes_via_handler_preserving_task_id(monkeypatch, tmp_path) -> None:
    # Production path: call_tool -> _handle_tool_call. Because save_review is in
    # _TASK_CONTEXT_EXCLUDED_TOOLS, it dispatches without the task_id guard and,
    # unlike the generic _call_tool path, keeps task_id for evidence enrichment.
    import computer_use.mcp_server as server
    import computer_use.review_report as rr

    captured: dict[str, object] = {}

    def fake_save(report_markdown, outcome="unknown", task_id=None, client=None, model=None):
        captured.update(report_markdown=report_markdown, outcome=outcome, task_id=task_id)
        return {"saved": True, "review_path": str(tmp_path / "r.md"), "review_dir": str(tmp_path)}

    monkeypatch.setattr(rr, "save_review", fake_save)
    data = json.loads(
        server._handle_tool_call(
            "save_review",
            {"report_markdown": "hi", "outcome": "succeeded", "task_id": "task-keep"},
        )
    )
    assert data["saved"] is True
    assert captured["report_markdown"] == "hi"
    assert captured["outcome"] == "succeeded"
    assert captured["task_id"] == "task-keep"  # not stripped


def test_schemas_module_exports_tools_and_constants() -> None:
    assert hasattr(schemas_module, "TOOLS")
    assert hasattr(schemas_module, "MAX_SLEEP_DURATION")
    assert hasattr(schemas_module, "_MANIFEST_TOOL_NAMES")
    assert hasattr(schemas_module, "_TASK_MANAGEMENT_TOOLS")
    assert hasattr(schemas_module, "_TASK_CONTEXT_EXCLUDED_TOOLS")
    assert {tool.name for tool in schemas_module.TOOLS} == {tool.name for tool in TOOLS}


def test_tools_have_dispatch_handlers() -> None:
    """Every TOOLS entry must have a corresponding branch in _dispatch_tool."""
    import computer_use.mcp_server as server
    import inspect

    source = inspect.getsource(server._dispatch_tool)
    handled: set[str] = set(re.findall(r'if name == "([^"]+)":', source))

    # Capture multi-line `if name in { ... }:` blocks as well.
    for match in re.finditer(r'if name in \{', source):
        start = match.end()
        end = source.find("}:", start)
        block = source[start:end]
        handled.update(re.findall(r'"([^"]+)"', block))

    registered = {tool.name for tool in TOOLS}
    assert registered <= handled, f"missing dispatch handlers for {registered - handled}"


def test_activate_window_dispatch_routes_name(monkeypatch) -> None:
    import computer_use.mcp_server as server

    captured: dict[str, object] = {}

    def fake_activate(name):
        captured["name"] = name
        return {"activated": True, "name": name, "process_name": "game.exe", "rect": None}

    monkeypatch.setattr(server, "activate_window", fake_activate)

    data = json.loads(_call_tool("activate_window", {"name": "Genshin"}))
    assert captured["name"] == "Genshin"
    assert data["activated"] is True


def _png_result(path: Path, extra: dict | None = None) -> str:
    payload = {"screenshot_taken": True, "saved_path": str(path), "width": 100, "height": 50}
    if extra:
        payload.update(extra)
    return json.dumps(payload)


def test_screenshot_inline_appends_full_image(tmp_path) -> None:
    import asyncio
    import base64
    import computer_use.mcp_server as server

    png = tmp_path / "shot.png"
    raw = b"\x89PNG\r\n\x1a\n fake png bytes"
    png.write_bytes(raw)

    content = asyncio.run(server._screenshot_result_content(_png_result(png)))

    assert len(content) == 2
    text, image = content
    assert text.type == "text"
    assert json.loads(text.text)["inline_image"] is True
    assert image.type == "image"
    assert image.mimeType == "image/png"
    assert base64.b64decode(image.data) == raw
    # base64 must never leak into the text block
    assert image.data not in text.text


def test_screenshot_inline_missing_file_degrades(tmp_path) -> None:
    import asyncio
    import computer_use.mcp_server as server

    content = asyncio.run(
        server._screenshot_result_content(_png_result(tmp_path / "missing.png"))
    )
    assert len(content) == 1
    assert json.loads(content[0].text)["inline_image"] is False


def test_screenshot_inline_error_result_passthrough() -> None:
    import asyncio
    import computer_use.mcp_server as server

    err = json.dumps({"error": "Failed to save screenshot: boom"})
    content = asyncio.run(server._screenshot_result_content(err))
    assert len(content) == 1
    assert content[0].text == err


def test_screenshot_inline_too_large_skips(tmp_path) -> None:
    import asyncio
    import computer_use.mcp_server as server

    png = tmp_path / "big.png"
    png.write_bytes(b"\x00" * (server._MAX_INLINE_IMAGE_RAW_BYTES + 1))

    content = asyncio.run(server._screenshot_result_content(_png_result(png)))
    assert len(content) == 1
    assert json.loads(content[0].text)["inline_image_skipped"] == "payload_too_large"


def test_screenshot_inline_unparseable_passthrough() -> None:
    import asyncio
    import computer_use.mcp_server as server

    content = asyncio.run(server._screenshot_result_content("not json at all"))
    assert len(content) == 1
    assert content[0].text == "not json at all"


def test_include_image_not_forwarded_to_dispatch(monkeypatch) -> None:
    import computer_use.mcp_server as server

    captured: dict[str, object] = {}

    def fake_dispatch(name, args, cs, **kwargs):
        captured["args"] = dict(args)
        return json.dumps({"ok": True})

    monkeypatch.setattr(server, "_dispatch_tool", fake_dispatch)

    _call_tool("screenshot", {"monitor": 1, "include_image": True})
    assert "include_image" not in captured["args"]
    assert captured["args"]["monitor"] == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("press_key", "press_key"),
        ("computer-use_press_key", "press_key"),
        ("mcp__computer-use__press_key", "press_key"),
    ],
)
def test_normalize_nested_tool_name_accepts_known_names(raw, expected):
    from computer_use.tool_contract import (
        BATCH_ACTION_TOOL_NAMES,
        normalize_nested_tool_name,
    )

    assert (
        normalize_nested_tool_name(raw, allowed_tools=BATCH_ACTION_TOOL_NAMES)
        == expected
    )


def test_normalize_nested_tool_name_rejects_unknown_name():
    from computer_use.tool_contract import (
        BATCH_ACTION_TOOL_NAMES,
        InvalidToolName,
        normalize_nested_tool_name,
    )

    with pytest.raises(InvalidToolName) as exc:
        normalize_nested_tool_name(
            "computer-use_press_keey",
            allowed_tools=BATCH_ACTION_TOOL_NAMES,
        )

    assert exc.value.requested_tool == "computer-use_press_keey"
    assert "press_key" in exc.value.candidates


def test_batch_schema_enumerates_canonical_tool_names():
    from computer_use.tool_contract import BATCH_ACTION_TOOL_NAMES

    batch = next(tool for tool in TOOLS if tool.name == "batch")
    tool_schema = batch.inputSchema["properties"]["actions"]["items"]["properties"]["tool"]

    assert tool_schema["enum"] == list(BATCH_ACTION_TOOL_NAMES)
    assert "computer-use_press_key" not in tool_schema["enum"]


def test_batch_action_tool_names_match_tools_registry():
    """Guard against drift between the nested allow-list and TOOLS."""
    from computer_use.tool_contract import (
        BATCH_ACTION_TOOL_NAMES,
        _DIAGNOSTIC_TOOL_NAMES,
        _ORCHESTRATION_TOOL_NAMES,
    )

    registered = {tool.name for tool in TOOLS}
    excluded = _ORCHESTRATION_TOOL_NAMES | _DIAGNOSTIC_TOOL_NAMES

    assert set(BATCH_ACTION_TOOL_NAMES) <= registered
    assert set(BATCH_ACTION_TOOL_NAMES) == registered - excluded


def test_task_plan_schema_enumerates_canonical_tool_names():
    from computer_use.tool_contract import TASK_STEP_TOOL_NAMES

    task_plan = next(tool for tool in TOOLS if tool.name == "run_task_plan")
    tool_schema = task_plan.inputSchema["properties"]["steps"]["items"]["properties"][
        "tool"
    ]

    assert tool_schema["enum"] == list(TASK_STEP_TOOL_NAMES)
    assert "computer-use_press_key" not in tool_schema["enum"]


def test_task_plan_tool_names_match_tools_registry():
    """Guard against drift between task-plan steps and TOOLS."""
    from computer_use.tool_contract import (
        TASK_STEP_TOOL_NAMES,
        _ORCHESTRATION_TOOL_NAMES,
    )

    registered = {tool.name for tool in TOOLS}
    allowed_orchestration = {"batch"}
    excluded_orchestration = _ORCHESTRATION_TOOL_NAMES - allowed_orchestration

    assert set(TASK_STEP_TOOL_NAMES) <= registered
    assert set(TASK_STEP_TOOL_NAMES) == registered - excluded_orchestration


def test_batch_normalizes_known_mcp_prefix(monkeypatch):
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(
        server,
        "_call_tool",
        lambda name, args, trace_context=None: calls.append(name)
        or json.dumps({"pressed": True}),
    )

    result = json.loads(
        server._batch_tool(
            {"actions": [{"tool": "computer-use_press_key", "args": {"key": "Down"}}]},
            trace_id="alias-batch",
        )
    )

    assert calls == ["press_key"]
    assert result["results"][0]["requested_tool"] == "computer-use_press_key"
    assert result["results"][0]["tool"] == "press_key"


def test_batch_returns_invalid_tool_with_candidates():
    import computer_use.mcp_server as server

    result = json.loads(
        server._batch_tool(
            {
                "actions": [
                    {"tool": "computer-use_press_keey", "args": {"key": "Down"}}
                ]
            },
            trace_id="invalid-tool-batch",
        )
    )

    failure = result["results"][0]["result"]
    assert failure["error"] == "invalid_tool"
    assert failure["requested_tool"] == "computer-use_press_keey"
    assert "press_key" in failure["candidates"]
    assert result["failed_index"] == 0


def test_invalid_tool_is_recorded_with_dedicated_error_kind():
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module

    result = json.loads(
        server._call_tool(
            "batch",
            {"actions": [{"tool": "computer-use_press_keey", "args": {}}]},
        )
    )
    records = trace_module.read_trace(result["trace_id"])

    assert result["results"][0]["result"]["error"] == "invalid_tool"
    assert records[-1]["error_kind"] == "invalid_tool"


def test_batch_response_exposes_authoritative_failure_summary():
    import computer_use.mcp_server as server

    result = json.loads(
        server._call_tool(
            "batch",
            {"actions": [{"tool": "bad_tool", "args": {}}]},
        )
    )

    assert result["status"] == "failed"
    assert result["failed_index"] == 0
    assert result["error_kind"] == "invalid_tool"
    assert result["executed_count"] == 1
    assert result["requested_count"] == 1
    assert result["artifacts"]["screenshots"] == []
    assert result["artifacts"]["snapshots"] == []
    assert result["artifacts"]["report"] is None
    assert result["trace_path"] is not None


def test_start_task_tool_dispatches_task_session(tmp_path, monkeypatch):
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path)

    data = json.loads(_call_tool("start_task", {"goal": "audit traces"}))

    assert data["goal"] == "audit traces"
    assert data["status"] == "active"
    assert Path(data["task_path"]).is_dir()
    assert "timestamp" in data


def test_finish_task_tool_returns_task_not_found(tmp_path, monkeypatch):
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path)

    data = json.loads(_call_tool("finish_task", {"task_id": "missing"}))

    assert data["error"] == "task_not_found"
    assert data["task_id"] == "missing"
    assert "timestamp" in data


def test_task_management_handler_does_not_create_execution_trace(tmp_path, monkeypatch):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session
    import computer_use.trace as trace_module

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path / "traces")

    data = json.loads(server._handle_tool_call("start_task", {"goal": "managed"}))
    task = task_session.get_task(data["task_id"])

    assert task["mode"] == "explicit"
    assert task["trace_count"] == 0
    assert list((tmp_path / "traces").rglob("trace.jsonl")) == []


def test_executable_tool_schemas_include_optional_task_id():
    no_task_id_tools = {"start_task", "list_tasks", "review_task"}
    task_management_tools = {"finish_task", "get_task", "review_task_session"}

    for tool in TOOLS:
        properties = tool.inputSchema.get("properties", {})
        if tool.name in no_task_id_tools:
            assert "task_id" not in properties
        elif tool.name in task_management_tools:
            assert "task_id" in properties
        else:
            assert properties["task_id"]["type"] == "string"


def test_explicit_task_groups_multiple_top_level_calls(tmp_path, monkeypatch):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session
    import computer_use.trace as trace_module

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path / "traces")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)
    task_id = json.loads(_call_tool("start_task", {"goal": "group"}))["task_id"]

    first = json.loads(server._handle_tool_call("sleep", {"duration": 0, "task_id": task_id}))
    second = json.loads(server._handle_tool_call("sleep", {"duration": 0, "task_id": task_id}))

    task = task_session.get_task(task_id)
    assert first["task_id"] == task_id
    assert second["task_id"] == task_id
    assert task["status"] == "active"
    assert task["trace_count"] == 2
    assert {link["status"] for link in task["traces"]} == {"succeeded"}


def test_missing_task_id_creates_closed_standalone_task(tmp_path, monkeypatch):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)

    data = json.loads(server._handle_tool_call("sleep", {"duration": 0}))
    task = task_session.get_task(data["task_id"])

    assert task["mode"] == "standalone"
    assert task["status"] == "succeeded"
    assert task["trace_count"] == 1


def test_standalone_context_register_conflict_does_not_leave_active_task(
    tmp_path,
    monkeypatch,
):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session
    import computer_use.trace as trace_module

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path / "traces")
    owner = task_session.start_task("owner")["task_id"]
    task_session.register_trace(
        owner,
        "shared-trace",
        kind="task_plan",
        tool="run_task_plan",
    )
    task_session.finish_task(owner)

    data = json.loads(
        server._handle_tool_call(
            "run_task_plan",
            {
                "trace_id": "shared-trace",
                "steps": [{"tool": "sleep", "args": {"duration": 0}}],
            },
        )
    )
    standalone_tasks = [
        task for task in task_session.list_tasks() if task["mode"] == "standalone"
    ]

    assert data["error"] == "trace_task_conflict"
    assert all(task["status"] != "active" for task in standalone_tasks)


def test_top_level_tool_without_task_id_is_rejected_when_active_explicit_task_exists(
    tmp_path, monkeypatch
):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)
    task_id = task_session.start_task("guarded")["task_id"]

    data = json.loads(server._handle_tool_call("sleep", {"duration": 0}))

    assert data["error"] == "missing_task_id"
    assert data["active_task_id"] == task_id
    task = task_session.get_task(task_id)
    assert task["trace_count"] == 0


def test_top_level_tool_without_task_id_still_creates_standalone_when_no_active_task(
    tmp_path, monkeypatch
):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)

    data = json.loads(server._handle_tool_call("sleep", {"duration": 0}))

    task = task_session.get_task(data["task_id"])
    assert task["mode"] == "standalone"
    assert task["status"] == "succeeded"
    assert task["trace_count"] == 1


def test_top_level_tool_with_task_id_registers_trace_to_explicit_task(
    tmp_path, monkeypatch
):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)
    task_id = task_session.start_task("grouped")["task_id"]

    data = json.loads(
        server._handle_tool_call("sleep", {"duration": 0, "task_id": task_id})
    )

    assert data["task_id"] == task_id
    task = task_session.get_task(task_id)
    assert task["status"] == "active"
    assert task["trace_count"] == 1


def test_task_management_tools_do_not_require_task_id_guard(
    tmp_path, monkeypatch
):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    task_session.start_task("owner")

    data = json.loads(server._handle_tool_call("list_tasks", {}))

    assert "error" not in data
    assert isinstance(data["tasks"], list)
    assert any(task["mode"] == "explicit" for task in data["tasks"])


def test_batch_registers_only_top_level_trace_for_task(tmp_path, monkeypatch):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)

    data = json.loads(
        server._handle_tool_call(
            "batch",
            {
                "actions": [
                    {"tool": "sleep", "args": {"duration": 0}},
                    {"tool": "sleep", "args": {"duration": 0}},
                ],
            },
        )
    )
    task = task_session.get_task(data["task_id"])

    assert task["status"] == "succeeded"
    assert task["trace_count"] == 1
    assert task["traces"][0]["trace_id"] == data["trace_id"]


def test_task_id_is_not_written_to_trace_args(tmp_path, monkeypatch):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session
    import computer_use.trace as trace_module

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path / "traces")
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)
    task_id = json.loads(_call_tool("start_task", {"goal": "redact task id"}))["task_id"]

    data = json.loads(server._handle_tool_call("sleep", {"duration": 0, "task_id": task_id}))
    record = trace_module.read_trace(data["trace_id"])[0]

    assert "task_id" not in record["args"]


def test_get_monitors() -> None:
    result = _call_tool("get_monitors", {})
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    for mon in data:
        assert "index" in mon
        assert "primary" in mon
        assert "left" in mon
        assert "top" in mon
        assert "width" in mon
        assert "height" in mon


def _minimal_config(tmpdir: str, screenshot_sensitive_window_check: bool = False) -> dict:
    return {
        "log_dir": Path(tmpdir),
        "screenshot_dir": Path(tmpdir) / "shots",
        "safety": {
            "screenshot_sensitive_window_check": screenshot_sensitive_window_check,
            "sensitive_processes": [],
            "sensitive_window_classes": [],
            "allowed_commands": [],
        },
        "display": {"default_monitor": 1},
    }


def _fake_save_screenshot(path: str | Path, monitor: int) -> Path:
    saved = Path(path)
    saved.write_bytes(b"fake-png")
    return saved


def test_screenshot_default_saves_to_configured_dir(monkeypatch) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server, "load_config", lambda: _minimal_config(tmpdir))
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)
        result = _call_tool("screenshot", {})
        data = json.loads(result)
        assert data["screenshot_taken"] is True
        assert data["monitor"] == 1
        assert "saved_path" in data
        assert "timestamp" in data
        assert "image" not in data
        saved = Path(data["saved_path"])
        assert saved.exists()


def test_screenshot_with_monitor(monkeypatch) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server, "load_config", lambda: _minimal_config(tmpdir))
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)
        result = _call_tool("screenshot", {"monitor": 1})
        data = json.loads(result)
        assert data["screenshot_taken"] is True
        assert data["monitor"] == 1
        assert "saved_path" in data
        assert Path(data["saved_path"]).exists()


def test_screenshot_invalid_monitor() -> None:
    result = _call_tool("screenshot", {"monitor": 99})
    data = json.loads(result)
    assert "error" in data or "out of range" in result


def test_screenshot_save_path_returns_path(monkeypatch) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        config = _minimal_config(tmpdir)
        screenshot_dir = Path(config["screenshot_dir"])
        screenshot_dir.mkdir()
        path = screenshot_dir / "shot.png"
        monkeypatch.setattr(server, "load_config", lambda: config)
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)
        result = _call_tool("screenshot", {"save_path": str(path)})
        data = json.loads(result)
        assert data["screenshot_taken"] is True
        assert "saved_path" in data
        assert Path(data["saved_path"]).resolve() == path.resolve()
        assert path.exists()
        assert "image" not in data
        assert "timestamp" in data


def test_screenshot_save_path_outside_configured_dir_is_rejected(
    monkeypatch,
) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        config = _minimal_config(tmpdir)
        Path(config["screenshot_dir"]).mkdir()
        path = Path(tmpdir) / "outside.png"
        monkeypatch.setattr(server, "load_config", lambda: config)
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)

        result = _call_tool("screenshot", {"save_path": str(path)})

        data = json.loads(result)
        assert "error" in data
        assert "screenshot_dir" in data["error"]
        assert not path.exists()


@pytest.mark.parametrize(
    "path_factory",
    [
        lambda root, shots: shots,
        lambda root, shots: shots / ".." / "escape.png",
        lambda root, shots: Path(r"\\server\share\shot.png"),
        lambda root, shots: Path("C:drive-relative.png"),
    ],
    ids=["directory", "parent-traversal", "unc", "drive-relative"],
)
def test_screenshot_save_path_rejects_path_edge_cases(
    monkeypatch, path_factory
) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        config = _minimal_config(tmpdir)
        shots = Path(config["screenshot_dir"])
        shots.mkdir()
        path = path_factory(Path(tmpdir), shots)
        monkeypatch.setattr(server, "load_config", lambda: config)
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)

        data = json.loads(
            _call_tool("screenshot", {"save_path": str(path)})
        )

        assert "error" in data
        assert "screenshot_dir" in data["error"]


@pytest.mark.manual
@pytest.mark.skipif(
    os.environ.get("COMPUTER_USE_RUN_MANUAL") != "1",
    reason="requires an interactive Windows desktop",
)
def test_manual_real_screenshot_capture(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    config = _minimal_config(str(tmp_path))
    monkeypatch.setattr(server, "load_config", lambda: config)

    data = json.loads(_call_tool("screenshot", {"monitor": 1}))

    assert data["screenshot_taken"] is True
    assert Path(data["saved_path"]).is_file()


def test_type_allows_safe_password_control(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="Password",
        control_type="Edit",
        class_name="Edit",
        process_name="app.exe",
        is_password=True,
        rect=(0, 0, 200, 30),
        center=(100, 15),
    )
    typed = []
    monkeypatch.setattr(server, "_current_logical_position", lambda: (100, 15))
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "type_text", typed.append)

    data = json.loads(_call_tool("type", {"text": "safe-password"}))

    assert data["typed"] is True
    assert data["length"] == len("safe-password")
    assert typed == ["safe-password"]


@pytest.mark.parametrize(
    ("process_name", "class_name"),
    [
        ("KeePass.exe", "Edit"),
        ("app.exe", "#32770"),
    ],
)
def test_type_blocks_sensitive_password_control(
    monkeypatch, process_name, class_name
) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="Password",
        control_type="Edit",
        class_name=class_name,
        process_name=process_name,
        is_password=True,
        rect=(0, 0, 200, 30),
        center=(100, 15),
    )
    typed = []
    monkeypatch.setattr(server, "_current_logical_position", lambda: (100, 15))
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "type_text", typed.append)

    data = json.loads(_call_tool("type", {"text": "safe-password"}))

    assert "error" in data
    assert "sensitive" in data["error"].lower()
    assert typed == []


def test_type_blocks_dangerous(monkeypatch) -> None:
    import computer_use.mcp_server as server

    typed = []
    monkeypatch.setattr(server, "type_text", typed.append)

    result = _call_tool("type", {"text": "rm -rf /"})
    data = json.loads(result)
    assert "error" in data or "Refusing" in result
    assert typed == []


def test_click_out_of_bounds() -> None:
    result = _call_tool("click", {"x": 99999, "y": 99999})
    data = json.loads(result)
    assert "error" in data or "outside" in result


def _multi_monitor_coordinate_system() -> SimpleNamespace:
    monitors = [
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ]
    return SimpleNamespace(
        monitors=monitors,
        get_screen_size=lambda: SimpleNamespace(width=3840, height=1080),
    )


def test_click_rejects_secondary_monitor_coordinate(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "get_coordinate_system", _multi_monitor_coordinate_system)
    monkeypatch.setattr(server, "click", lambda *args, **kwargs: calls.append((args, kwargs)))

    data = json.loads(_call_tool("click", {"x": 2000, "y": 500}))

    assert "primary" in data["error"].lower()
    assert calls == []


def test_type_rejects_secondary_monitor_current_cursor(monkeypatch) -> None:
    import computer_use.mcp_server as server

    typed = []
    monkeypatch.setattr(server, "get_coordinate_system", _multi_monitor_coordinate_system)
    monkeypatch.setattr(server.pyautogui, "position", lambda: (2000, 500))
    monkeypatch.setattr(server, "type_text", typed.append)

    data = json.loads(_call_tool("type", {"text": "safe text"}))

    assert "primary" in data["error"].lower()
    assert typed == []


@pytest.mark.parametrize(
    ("tool_name", "args", "action_name"),
    [
        ("key_combo", {"keys": ["ctrl", "c"]}, "key_combo"),
        ("key_down", {"key": "ctrl"}, "key_down"),
        ("key_up", {"key": "ctrl"}, "key_up"),
        ("press_key", {"key": "enter"}, "press_key"),
        ("mouse_up", {}, "mouse_up"),
    ],
)
def test_current_cursor_input_rejects_secondary_monitor(
    monkeypatch, tool_name, args, action_name
) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "get_coordinate_system", _multi_monitor_coordinate_system)
    monkeypatch.setattr(server.pyautogui, "position", lambda: (2000, 500))
    monkeypatch.setattr(
        server,
        action_name,
        lambda *action_args, **action_kwargs: calls.append(
            (action_args, action_kwargs)
        ),
    )

    data = json.loads(_call_tool(tool_name, args))

    assert "primary" in data["error"].lower()
    assert calls == []


def test_click_gap_region() -> None:
    # Virtual screen width is required; the exact gap depends on the host layout.
    # We first query size, then pick a point that is outside any monitor but
    # inside the virtual screen bounding box. If only one monitor is present,
    # this test is skipped because there is no gap.
    from computer_use.core import get_coordinate_system

    cs = get_coordinate_system()
    size = cs.get_screen_size()
    monitors = cs.get_monitors()
    if len(monitors) <= 1:
        pytest.skip("Need at least two monitors to test gap rejection.")

    # Pick x beyond the right edge of the primary monitor but within virtual width,
    # and y=0 (assuming no monitor extends there).
    primary = next((m for m in monitors if m.primary), monitors[0])
    gap_x = primary.left + primary.width
    gap_y = 0
    result = _call_tool("click", {"x": gap_x, "y": gap_y})
    data = json.loads(result)
    assert "error" in data or "gap" in result


def test_click_accepts_duration(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "click", lambda x, y, duration: calls.append((x, y, duration)))
    result = _call_tool("click", {"x": 100, "y": 200, "duration": 0.5})
    data = json.loads(result)
    assert data["duration"] == 0.5
    assert calls == [(100, 200, 0.5)]


def test_move_to_accepts_duration(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "move_to", lambda x, y, duration: calls.append((x, y, duration)))
    result = _call_tool("move_to", {"x": 100, "y": 200, "duration": 0.8})
    data = json.loads(result)
    assert data["duration"] == 0.8
    assert calls == [(100, 200, 0.8)]


def test_click_default_duration(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "click", lambda x, y, duration: calls.append((x, y, duration)))
    result = _call_tool("click", {"x": 100, "y": 200})
    data = json.loads(result)
    assert data["duration"] == 0.2
    assert calls == [(100, 200, 0.2)]


def test_move_to_default_duration(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "move_to", lambda x, y, duration: calls.append((x, y, duration)))
    result = _call_tool("move_to", {"x": 100, "y": 200})
    data = json.loads(result)
    assert data["duration"] == 0.2
    assert calls == [(100, 200, 0.2)]


def test_click_negative_duration_returns_error() -> None:
    result = _call_tool("click", {"x": 100, "y": 200, "duration": -0.1})
    data = json.loads(result)
    assert "error" in data
    assert "duration" in data["error"].lower() or "non-negative" in data["error"].lower()


def test_move_to_negative_duration_returns_error() -> None:
    result = _call_tool("move_to", {"x": 100, "y": 200, "duration": -0.1})
    data = json.loads(result)
    assert "error" in data
    assert "duration" in data["error"].lower() or "non-negative" in data["error"].lower()


def test_find_control_tool_dispatch(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    calls = []

    def fake_find_control(**kwargs):
        calls.append(kwargs)
        return {"found": True, "name": "OK"}

    monkeypatch.setattr(uia_module, "find_control", fake_find_control)
    monkeypatch.setattr(server, "find_control", fake_find_control)

    result = _call_tool("find_control", {"name": "Tools", "scope": "foreground"})
    data = json.loads(result)
    assert data["found"] is True
    assert data["name"] == "OK"
    assert "timestamp" in data
    assert calls == [
        {
            "name": "Tools",
            "automation_id": None,
            "control_type": None,
            "class_name": None,
            "scope": "foreground",
            "window_name": None,
            "match": "contains",
            "sensitive_check": True,
        }
    ]


def test_inspect_point_tool_dispatch(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="Button",
        control_type="Button",
        class_name="Btn",
        process_name="app.exe",
        is_password=False,
        rect=(0, 0, 100, 20),
        center=(50, 10),
    )
    monkeypatch.setattr(uia_module, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)

    result = _call_tool("inspect_point", {"x": 50, "y": 10})
    data = json.loads(result)
    assert data["name"] == "Button"
    assert data["control_type"] == "Button"
    assert data["rect"] == {"left": 0, "top": 0, "right": 100, "bottom": 20}
    assert data["center"] == {"x": 50, "y": 10}


def test_wait_for_window_tool_dispatch(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    calls = []

    def fake_wait_for_window(name, exists=True, timeout=10):
        calls.append((name, exists, timeout))
        return {"present": True, "name": name}

    monkeypatch.setattr(uia_module, "wait_for_window", fake_wait_for_window)
    monkeypatch.setattr(server, "wait_for_window", fake_wait_for_window)

    result = _call_tool("wait_for_window", {"name": "HiBit", "timeout": 5})
    data = json.loads(result)
    assert data["present"] is True
    assert data["name"] == "HiBit"
    assert "timestamp" in data
    assert calls == [("HiBit", True, 5)]


def test_wait_for_control_tool_dispatch(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    calls = []

    def fake_wait_for_control(**kwargs):
        calls.append(kwargs)
        return {"present": True, "name": "OK"}

    monkeypatch.setattr(uia_module, "wait_for_control", fake_wait_for_control)
    monkeypatch.setattr(server, "wait_for_control", fake_wait_for_control)

    result = _call_tool("wait_for_control", {"name": "Registry", "timeout": 3})
    data = json.loads(result)
    assert data["present"] is True
    assert data["name"] == "OK"
    assert "timestamp" in data
    assert calls == [
        {
            "name": "Registry",
            "automation_id": None,
            "control_type": None,
            "exists": True,
            "timeout": 3,
        }
    ]


def test_sleep_tool_sleeps(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server.time, "sleep", lambda d: calls.append(d))

    result = _call_tool("sleep", {"duration": 2.5})
    data = json.loads(result)
    assert data["slept"] is True
    assert data["duration"] == 2.5
    assert "timestamp" in data
    assert calls == [2.5]


def test_sleep_negative_duration_returns_error() -> None:
    result = _call_tool("sleep", {"duration": -1})
    data = json.loads(result)
    assert "error" in data
    assert "duration" in data["error"].lower() or "non-negative" in data["error"].lower()


def test_sleep_too_long_returns_error() -> None:
    result = _call_tool("sleep", {"duration": 100})
    data = json.loads(result)
    assert "error" in data
    assert "60" in data["error"] or "exceed" in data["error"].lower()


def test_launch_app_tool_dispatch(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []

    def fake_launch_app(name):
        calls.append(name)
        return {"launched": True, "name": name, "target_path": "C:/App/app.exe"}

    monkeypatch.setattr(server, "launch_app", fake_launch_app)

    result = _call_tool("launch_app", {"name": "App"})
    data = json.loads(result)
    assert data["launched"] is True
    assert data["name"] == "App"
    assert data["target_path"] == "C:/App/app.exe"
    assert "timestamp" in data
    assert calls == ["App"]


def test_batch_tool_runs_actions(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_call_tool(name, args, trace_context=None):
        if name == "screenshot":
            return json.dumps({"screenshot_taken": True, "saved_path": "C:/shots/final.png"})
        return json.dumps({"called": name, "args": args})

    monkeypatch.setattr(server, "_call_tool", fake_call_tool)

    result = _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "click", "args": {"x": 100, "y": 200}},
                {"tool": "type", "args": {"text": "hello"}},
            ],
            "final_screenshot": True,
        },
    )
    data = json.loads(result)
    assert data["failed_index"] is None
    assert len(data["results"]) == 2
    assert data["results"][0]["result"]["called"] == "click"
    assert data["results"][0]["result"]["args"] == {"x": 100, "y": 200}
    assert data["results"][1]["result"]["called"] == "type"
    assert data["results"][1]["result"]["args"] == {"text": "hello"}
    assert "timestamp" in data["results"][0]
    assert "timestamp" in data["results"][1]
    assert data["final_screenshot"]["saved_path"] == "C:/shots/final.png"
    assert data["trace_path"] is not None
    assert data["artifact_root"].endswith(data["trace_id"])
    assert data["artifacts"] == {
        "screenshots": [],
        "snapshots": [],
        "report": None,
    }
    assert "timestamp" in data


def test_batch_tool_stop_on_error(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_call_tool(name, args, trace_context=None):
        if name == "click":
            return json.dumps({"error": "out of bounds"})
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_call_tool", fake_call_tool)

    result = _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "click", "args": {"x": 99999, "y": 99999}},
                {"tool": "type", "args": {"text": "hello"}},
            ],
        },
    )
    data = json.loads(result)
    assert data["failed_index"] == 0
    assert len(data["results"]) == 1
    assert "error" in data["results"][0]["result"]
    assert "final_screenshot" not in data


def test_batch_tool_continue_on_error(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_call_tool(name, args, trace_context=None):
        if name == "click":
            return json.dumps({"error": "out of bounds"})
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_call_tool", fake_call_tool)

    result = _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "click", "args": {"x": 99999, "y": 99999}},
                {"tool": "type", "args": {"text": "hello"}},
            ],
            "stop_on_error": False,
        },
    )
    data = json.loads(result)
    assert data["failed_index"] == 0
    assert len(data["results"]) == 2
    assert data["results"][1]["result"]["called"] == "type"
    assert "final_screenshot" not in data


def test_batch_tool_stops_on_timeout(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_call_tool(name, args, trace_context=None):
        if name == "wait_for_window":
            return json.dumps({"present": False, "timeout": True})
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_call_tool", fake_call_tool)

    data = json.loads(
        _call_tool(
            "batch",
            {
                "actions": [
                    {"tool": "wait_for_window", "args": {"name": "Missing"}},
                    {"tool": "sleep", "args": {"duration": 0}},
                ]
            },
        )
    )

    assert data["failed_index"] == 0
    assert len(data["results"]) == 1


def test_batch_tool_rejects_nested_batch(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []

    def fake_call_tool(name, args, trace_context=None):
        calls.append(name)
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_call_tool", fake_call_tool)

    result = _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "batch", "args": {"actions": []}},
            ],
        },
    )
    data = json.loads(result)
    assert data["failed_index"] == 0
    assert data["results"][0]["result"]["error"] == "invalid_tool"
    assert data["results"][0]["requested_tool"] == "batch"
    assert calls == []
    assert "final_screenshot" not in data


def test_batch_tool_rejects_run_task_plan_with_nested_batch() -> None:
    data = json.loads(
        _call_tool(
            "batch",
            {
                "actions": [
                    {
                        "tool": "run_task_plan",
                        "args": {
                            "steps": [
                                {
                                    "tool": "batch",
                                    "args": {"actions": []},
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )

    assert data["failed_index"] == 0
    assert "run_task_plan" in json.dumps(data)


class TestLowLevelInputTools:
    @pytest.fixture(autouse=True)
    def _patch_inspect(self, monkeypatch):
        import computer_use.mcp_server as server
        import computer_use.ui_automation as uia_module

        info = uia_module.ControlInfo(
            name="",
            control_type="",
            class_name="",
            process_name="safe.exe",
            is_password=False,
            rect=None,
            center=None,
        )
        monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
        monkeypatch.setattr(uia_module, "inspect_point", lambda x, y: info)

    def test_click_with_button(self, monkeypatch) -> None:
        import computer_use.mcp_server as server

        calls = []
        monkeypatch.setattr(server, "click", lambda x, y, duration, button: calls.append((x, y, duration, button)))

        result = _call_tool("click", {"x": 100, "y": 200, "button": "right"})
        data = json.loads(result)
        assert data["clicked"] is True
        assert data["button"] == "right"
        assert calls == [(100, 200, 0.2, "right")]

    def test_mouse_down_and_up(self, monkeypatch) -> None:
        import computer_use.mcp_server as server

        down_calls = []
        up_calls = []
        monkeypatch.setattr(server, "mouse_down", lambda x, y, button: down_calls.append((x, y, button)))
        monkeypatch.setattr(server, "mouse_up", lambda x, y, button: up_calls.append((x, y, button)))

        result = _call_tool("mouse_down", {"x": 100, "y": 200, "button": "right"})
        assert json.loads(result)["mouse_down"] is True
        assert down_calls == [(100, 200, "right")]

        result = _call_tool("mouse_up", {"x": 300, "y": 400, "button": "right"})
        assert json.loads(result)["mouse_up"] is True
        assert up_calls == [(300, 400, "right")]

    def test_drag_tool(self, monkeypatch) -> None:
        import computer_use.mcp_server as server

        calls = []
        monkeypatch.setattr(server, "drag", lambda sx, sy, ex, ey, duration, button: calls.append((sx, sy, ex, ey, duration, button)))

        result = _call_tool("drag", {"start_x": 10, "start_y": 20, "end_x": 110, "end_y": 120, "button": "left"})
        data = json.loads(result)
        assert data["dragged"] is True
        assert calls == [(10, 20, 110, 120, 0.2, "left")]

    def test_drag_rejects_sensitive_start_before_input(self, monkeypatch) -> None:
        import computer_use.mcp_server as server
        from computer_use.safety import SafetyError
        from computer_use.ui_automation import ControlInfo

        drag_calls = []

        def inspect(x, y):
            process_name = "keepass.exe" if (x, y) == (10, 20) else "safe.exe"
            return ControlInfo(
                name="",
                control_type="Pane",
                class_name="SafePane",
                process_name=process_name,
                is_password=False,
                rect=None,
                center=None,
            )

        def check(process_name, class_name, control_type):
            if process_name == "keepass.exe":
                raise SafetyError("sensitive start")

        monkeypatch.setattr(server, "inspect_point", inspect)
        monkeypatch.setattr(server, "check_target_window", check)
        monkeypatch.setattr(server, "drag", lambda *args, **kwargs: drag_calls.append((args, kwargs)))

        result = _call_tool(
            "drag",
            {"start_x": 10, "start_y": 20, "end_x": 110, "end_y": 120},
        )

        assert "sensitive start" in json.loads(result)["error"]
        assert drag_calls == []

    def test_scroll_direction(self, monkeypatch) -> None:
        import computer_use.mcp_server as server
        from computer_use.ui_automation import ControlInfo

        calls = []
        checks = []
        monkeypatch.setattr(server.pyautogui, "position", lambda: (321, 432))
        monkeypatch.setattr(
            server,
            "inspect_point",
            lambda x, y: ControlInfo(
                name="List",
                control_type="Pane",
                class_name="SafePane",
                process_name="safe.exe",
                is_password=False,
                rect=None,
                center=None,
            ),
        )
        monkeypatch.setattr(
            server,
            "check_target_window",
            lambda process, class_name, control_type: checks.append(
                (process, class_name, control_type)
            ),
        )
        monkeypatch.setattr(server, "scroll", lambda amount, x, y, direction, clicks: calls.append((amount, x, y, direction, clicks)))

        result = _call_tool("scroll", {"direction": "down", "clicks": 2})
        data = json.loads(result)
        assert data["scrolled"] is True
        assert calls == [(None, None, None, "down", 2)]
        assert checks == [("safe.exe", "SafePane", "Pane")]

    def test_scroll_without_coords_rejects_out_of_bounds_cursor(
        self, monkeypatch
    ) -> None:
        import computer_use.mcp_server as server

        calls = []
        monkeypatch.setattr(server, "get_coordinate_system", _multi_monitor_coordinate_system)
        monkeypatch.setattr(server.pyautogui, "position", lambda: (2000, 500))
        monkeypatch.setattr(
            server,
            "scroll",
            lambda **kwargs: calls.append(kwargs),
        )

        data = json.loads(
            _call_tool("scroll", {"direction": "down", "clicks": 1})
        )

        assert "error" in data
        assert calls == []

    def test_key_down_up_and_press(self, monkeypatch) -> None:
        import computer_use.mcp_server as server

        calls = []
        monkeypatch.setattr(server.pyautogui, "position", lambda: (100, 100))
        monkeypatch.setattr(server, "key_down", lambda key: calls.append(("down", key)))
        monkeypatch.setattr(server, "key_up", lambda key: calls.append(("up", key)))
        monkeypatch.setattr(server, "press_key", lambda key: calls.append(("press", key)))

        assert json.loads(_call_tool("key_down", {"key": "ctrl"}))["key_down"] is True
        assert json.loads(_call_tool("key_up", {"key": "ctrl"}))["key_up"] is True
        assert json.loads(_call_tool("press_key", {"key": "enter"}))["pressed"] is True
        assert calls == [("down", "ctrl"), ("up", "ctrl"), ("press", "enter")]


def test_screenshot_redacts_when_sensitive_top_level_window_intersects(
    monkeypatch,
) -> None:
    import computer_use.mcp_server as server
    from computer_use.ui_automation import ControlInfo

    with tempfile.TemporaryDirectory() as tmpdir:
        config = _minimal_config(tmpdir, screenshot_sensitive_window_check=True)
        redacted_calls = []
        monkeypatch.setattr(server, "load_config", lambda: config)
        monkeypatch.setattr(
            server,
            "get_top_level_windows_in_rect",
            lambda bounds: [
                ControlInfo(
                    name="Secrets",
                    control_type="Window",
                    class_name="SafeWindow",
                    process_name="keepass.exe",
                    is_password=False,
                    rect=(10, 10, 200, 200),
                    center=(105, 105),
                )
            ],
        )
        monkeypatch.setattr(
            server,
            "save_redacted_image",
            lambda path, width, height: redacted_calls.append(
                (path, width, height)
            )
            or _fake_save_screenshot(path, 1),
        )

        data = json.loads(_call_tool("screenshot", {"monitor": 1}))

        assert data["redacted"] is True
        assert len(redacted_calls) == 1


def test_screenshot_monitor_zero_falls_back_to_offset_center(
    monkeypatch, tmp_path
) -> None:
    import computer_use.mcp_server as server
    from types import SimpleNamespace
    from computer_use.safety import SafetyError
    from computer_use.ui_automation import ControlInfo

    config = _minimal_config(
        str(tmp_path), screenshot_sensitive_window_check=True
    )
    fake_cs = SimpleNamespace(
        virtual_left=-200,
        virtual_top=20,
        virtual_width=2120,
        virtual_height=1060,
        monitors=[
            {"left": 0, "top": 20, "width": 1920, "height": 1060},
        ],
        get_monitors=lambda: [SimpleNamespace(index=1)],
    )
    inspected = []
    bounds_seen = []
    monkeypatch.setattr(server, "load_config", lambda: config)
    monkeypatch.setattr(server, "get_coordinate_system", lambda: fake_cs)
    monkeypatch.setattr(
        server,
        "get_top_level_windows_in_rect",
        lambda bounds: bounds_seen.append(bounds) or None,
    )
    monkeypatch.setattr(
        server,
        "inspect_point",
        lambda x, y: inspected.append((x, y))
        or ControlInfo(
            name="Sensitive",
            control_type="Window",
            class_name="SafeWindow",
            process_name="keepass.exe",
            is_password=False,
            rect=None,
            center=None,
        ),
    )
    monkeypatch.setattr(
        server,
        "check_target_window",
        lambda *args: (_ for _ in ()).throw(SafetyError("blocked")),
    )
    monkeypatch.setattr(
        server,
        "save_redacted_image",
        lambda path, width, height: _fake_save_screenshot(path, 0),
    )

    data = json.loads(_call_tool("screenshot", {"monitor": 0}))

    assert bounds_seen == [(-200, 20, 1920, 1080)]
    assert inspected == [(860, 550)]
    assert data["redacted"] is True


def _create_real_png(path, width: int, height: int) -> None:
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(str(path))


def _write_screenshot_sidecar(screenshot_path, **overrides) -> dict:
    defaults = {
        "schema_version": 1,
        "screenshot_path": str(screenshot_path),
        "monitor": 1,
        "coordinate_space": "monitor",
        "capture_left": 0,
        "capture_top": 0,
        "width": 1920,
        "height": 1080,
        "created_at": "2026-06-21T00:00:00.000+00:00",
    }
    defaults.update(overrides)
    meta_path = str(screenshot_path) + ".json"
    Path(meta_path).write_text(json.dumps(defaults), encoding="utf-8")
    return defaults


def _safe_control_info():
    from computer_use.ui_automation import ControlInfo

    return ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="safe.exe",
        is_password=False,
        rect=None,
        center=None,
    )


def _single_monitor_coordinate_system() -> SimpleNamespace:
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
    return SimpleNamespace(
        monitors=monitors,
        get_screen_size=lambda: SimpleNamespace(width=1920, height=1080),
    )


def _patch_safety_chain(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = _safe_control_info()
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(uia_module, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "check_target_window", lambda *a, **kw: None)
    monkeypatch.setattr(
        server, "get_coordinate_system", _single_monitor_coordinate_system
    )


def test_screenshot_writes_coordinate_metadata(monkeypatch) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server, "load_config", lambda: _minimal_config(tmpdir))
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)

        data = json.loads(_call_tool("screenshot", {}))

        assert data["screenshot_taken"] is True
        assert data["coordinate_space"] == "monitor"
        assert "capture_left" in data
        assert "capture_top" in data
        assert "metadata_path" in data

        meta_path = data["metadata_path"]
        assert Path(meta_path).exists()
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        assert meta["schema_version"] == 1
        assert meta["screenshot_path"] == data["saved_path"]
        assert meta["monitor"] == 1
        assert meta["coordinate_space"] == "monitor"
        assert meta["width"] == data["width"]
        assert meta["height"] == data["height"]
        assert meta["capture_left"] == data["capture_left"]
        assert meta["capture_top"] == data["capture_top"]


def test_screenshot_monitor_zero_writes_virtual_desktop_metadata(monkeypatch) -> None:
    import computer_use.mcp_server as server

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server, "load_config", lambda: _minimal_config(tmpdir))
        monkeypatch.setattr(server, "save_screenshot", _fake_save_screenshot)

        data = json.loads(_call_tool("screenshot", {"monitor": 0}))

        assert data["coordinate_space"] == "virtual_desktop"


def test_click_on_screenshot_maps_coordinates(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(shot_path, capture_left=0, capture_top=0)

    click_calls = []
    monkeypatch.setattr(
        server, "click", lambda x, y, duration: click_calls.append((x, y, duration))
    )
    _patch_safety_chain(monkeypatch)

    data = json.loads(
        _call_tool(
            "click_on_screenshot",
            {"screenshot_path": str(shot_path), "image_x": 213, "image_y": 48},
        )
    )

    assert data["clicked"] is True
    assert data["image_x"] == 213
    assert data["image_y"] == 48
    assert data["screen_x"] == 213
    assert data["screen_y"] == 48
    assert data["coordinate_space"] == "monitor"
    assert data["monitor"] == 1
    assert click_calls == [(213, 48, 0.2)]


def test_click_on_screenshot_missing_metadata(tmp_path) -> None:
    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 100, 100)

    data = json.loads(
        _call_tool(
            "click_on_screenshot",
            {"screenshot_path": str(shot_path), "image_x": 50, "image_y": 50},
        )
    )

    assert data["error"] == "screenshot_metadata_not_found"


def test_click_on_screenshot_out_of_bounds(tmp_path) -> None:
    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 100, 100)
    _write_screenshot_sidecar(shot_path, width=100, height=100)

    data = json.loads(
        _call_tool(
            "click_on_screenshot",
            {"screenshot_path": str(shot_path), "image_x": 200, "image_y": 50},
        )
    )

    assert data["error"] == "image_coordinate_out_of_bounds"
    assert data["width"] == 100
    assert data["height"] == 100


def test_click_on_screenshot_runs_safety_check(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(shot_path, capture_left=0, capture_top=0)

    inspect_calls = []
    check_calls = []
    info = _safe_control_info()
    monkeypatch.setattr(
        server,
        "inspect_point",
        lambda x, y: inspect_calls.append((x, y)) or info,
    )
    monkeypatch.setattr(
        uia_module,
        "inspect_point",
        lambda x, y: inspect_calls.append((x, y)) or info,
    )
    monkeypatch.setattr(
        server, "check_target_window", lambda *a, **kw: check_calls.append(a)
    )
    monkeypatch.setattr(
        server, "get_coordinate_system", _single_monitor_coordinate_system
    )
    monkeypatch.setattr(server, "click", lambda x, y, duration: None)

    _call_tool(
        "click_on_screenshot",
        {"screenshot_path": str(shot_path), "image_x": 100, "image_y": 200},
    )

    assert (100, 200) in inspect_calls
    assert len(check_calls) == 1


def test_crop_screenshot_inherits_offsets(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(
        shot_path, capture_left=100, capture_top=200, width=1920, height=1080
    )
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 50,
                "y": 60,
                "width": 360,
                "height": 120,
            },
        )
    )

    assert data["cropped"] is True
    assert data["capture_left"] == 150
    assert data["capture_top"] == 260
    assert data["width"] == 360
    assert data["height"] == 120

    crop_meta = json.loads(Path(data["metadata_path"]).read_text(encoding="utf-8"))
    assert crop_meta["capture_left"] == 150
    assert crop_meta["capture_top"] == 260
    assert crop_meta["source_screenshot_path"] == str(shot_path)
    assert crop_meta["width"] == 360
    assert crop_meta["height"] == 120


def test_crop_screenshot_out_of_bounds(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 200, 200)
    _write_screenshot_sidecar(shot_path, width=200, height=200)
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 0,
                "y": 0,
                "width": 300,
                "height": 200,
            },
        )
    )

    assert data["error"] == "image_coordinate_out_of_bounds"
    assert data["width"] == 200
    assert data["height"] == 200


def test_click_on_screenshot_works_with_crop(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(
        shot_path, capture_left=100, capture_top=200, width=1920, height=1080
    )
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    crop_data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 50,
                "y": 60,
                "width": 360,
                "height": 120,
            },
        )
    )
    crop_path = crop_data["saved_path"]

    click_calls = []
    monkeypatch.setattr(
        server, "click", lambda x, y, duration: click_calls.append((x, y, duration))
    )
    _patch_safety_chain(monkeypatch)

    data = json.loads(
        _call_tool(
            "click_on_screenshot",
            {"screenshot_path": crop_path, "image_x": 30, "image_y": 40},
        )
    )

    assert data["clicked"] is True
    assert data["screen_x"] == 180
    assert data["screen_y"] == 300
    assert click_calls == [(180, 300, 0.2)]


def _make_control_result(name: str = "OK") -> dict:
    return {
        "found": True,
        "name": name,
        "control_type": "Button",
        "class_name": "Btn",
        "process_name": "app.exe",
        "center": {"x": 150, "y": 250},
    }


def test_click_by_target_name(monkeypatch) -> None:
    import computer_use.mcp_server as server

    find_calls = []
    click_calls = []

    def fake_find_control(**kwargs):
        find_calls.append(kwargs)
        return _make_control_result("OK")

    monkeypatch.setattr(server, "find_control", fake_find_control)
    monkeypatch.setattr(server, "click", lambda x, y, duration: click_calls.append((x, y, duration)))

    result = _call_tool("click", {"target_name": "OK", "match": "exact"})
    data = json.loads(result)
    assert data["clicked"] is True
    assert data["x"] == 150
    assert data["y"] == 250
    assert data["duration"] == 0.2
    assert data["mode"] == "uia"
    assert data["target_name"] == "OK"
    assert data["match"] == "exact"
    assert data["control"]["process_name"] == "app.exe"
    assert click_calls == [(150, 250, 0.2)]
    assert find_calls == [
        {"name": "OK", "match": "exact", "scope": "desktop", "sensitive_check": False}
    ]


def test_click_by_target_name_rejects_secondary_monitor_center(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "get_coordinate_system", _multi_monitor_coordinate_system)
    monkeypatch.setattr(
        server,
        "find_control",
        lambda **kwargs: {
            **_make_control_result("Secondary"),
            "center": {"x": 2000, "y": 500},
        },
    )
    monkeypatch.setattr(server, "click", lambda *args, **kwargs: calls.append((args, kwargs)))

    data = json.loads(_call_tool("click", {"target_name": "Secondary"}))

    assert "primary" in data["error"].lower()
    assert calls == []


def test_move_to_by_target_name(monkeypatch) -> None:
    import computer_use.mcp_server as server

    find_calls = []
    move_calls = []

    def fake_find_control(**kwargs):
        find_calls.append(kwargs)
        return _make_control_result("Cancel")

    monkeypatch.setattr(server, "find_control", fake_find_control)
    monkeypatch.setattr(server, "move_to", lambda x, y, duration: move_calls.append((x, y, duration)))

    result = _call_tool("move_to", {"target_name": "Cancel"})
    data = json.loads(result)
    assert data["moved"] is True
    assert data["x"] == 150
    assert data["y"] == 250
    assert data["mode"] == "uia"
    assert data["target_name"] == "Cancel"
    assert move_calls == [(150, 250, 0.2)]
    assert find_calls == [
        {"name": "Cancel", "match": "contains", "scope": "desktop", "sensitive_check": False}
    ]


def test_click_target_name_not_found(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_find_control(**kwargs):
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

    monkeypatch.setattr(server, "find_control", fake_find_control)

    result = _call_tool("click", {"target_name": "Missing"})
    data = json.loads(result)
    assert "error" in data
    assert "screenshot" in data["error"] or "find_control" in data["error"]


def test_click_target_name_not_found_fallback_to_coords(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )

    def fake_find_control(**kwargs):
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

    click_calls = []
    monkeypatch.setattr(server, "find_control", fake_find_control)
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "click", lambda x, y, duration: click_calls.append((x, y, duration)))

    result = _call_tool("click", {"target_name": "Missing", "x": 100, "y": 200})
    data = json.loads(result)
    assert data["clicked"] is True
    assert data["x"] == 100
    assert data["y"] == 200
    assert data["mode"] == "coordinate"
    assert click_calls == [(100, 200, 0.2)]


def test_click_target_name_safety_block(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_find_control(**kwargs):
        return {
            "found": True,
            "name": "Secrets",
            "control_type": "Edit",
            "class_name": "Edit",
            "process_name": "KeePass.exe",
            "center": {"x": 300, "y": 300},
        }

    monkeypatch.setattr(server, "find_control", fake_find_control)

    result = _call_tool("click", {"target_name": "Secrets"})
    data = json.loads(result)
    assert "error" in data
    assert "Refusing" in result or "sensitive" in result.lower()


def test_click_target_name_passes_class_name_to_safety_check(monkeypatch) -> None:
    import computer_use.mcp_server as server
    from computer_use.safety import SafetyError

    def fake_find_control(**kwargs):
        return {
            "found": True,
            "name": "Dialog",
            "control_type": "Button",
            "class_name": "#32770",
            "process_name": "safe.exe",
            "center": {"x": 300, "y": 300},
        }

    monkeypatch.setattr(server, "find_control", fake_find_control)

    result = _call_tool("click", {"target_name": "Dialog"})
    data = json.loads(result)
    assert "error" in data
    assert "sensitive" in result.lower() or "Refusing" in result


def test_click_requires_target_or_coords() -> None:
    result = _call_tool("click", {})
    data = json.loads(result)
    assert "error" in data
    assert "target_name" in data["error"] or "x" in data["error"] or "y" in data["error"]


def test_click_by_coords_still_works(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )
    click_calls = []
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "click", lambda x, y, duration: click_calls.append((x, y, duration)))

    result = _call_tool("click", {"x": 120, "y": 220, "duration": 0.5})
    data = json.loads(result)
    assert data["clicked"] is True
    assert data["x"] == 120
    assert data["y"] == 220
    assert data["duration"] == 0.5
    assert data["mode"] == "coordinate"
    assert click_calls == [(120, 220, 0.5)]


def test_click_double_click_by_coords(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )
    calls = []
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(
        server, "double_click", lambda x, y, duration, button: calls.append((x, y, duration, button))
    )

    result = _call_tool("click", {"x": 120, "y": 220, "double_click": True, "duration": 0.5})
    data = json.loads(result)
    assert data["clicked"] is True
    assert data["double_click"] is True
    assert data["button"] == "left"
    assert calls == [(120, 220, 0.5, "left")]


def test_click_double_click_by_target_name(monkeypatch) -> None:
    import computer_use.mcp_server as server

    def fake_find_control(**kwargs):
        return {
            "found": True,
            "name": "HiBit Uninstaller",
            "control_type": "Button",
            "class_name": "Btn",
            "process_name": "safe.exe",
            "center": {"x": 300, "y": 300},
        }

    calls = []
    monkeypatch.setattr(server, "find_control", fake_find_control)
    monkeypatch.setattr(
        server, "double_click", lambda x, y, duration, button: calls.append((x, y, duration, button))
    )

    result = _call_tool("click", {"target_name": "HiBit Uninstaller", "double_click": True})
    data = json.loads(result)
    assert data["clicked"] is True
    assert data["double_click"] is True
    assert data["mode"] == "uia"
    assert data["target_name"] == "HiBit Uninstaller"
    assert calls == [(300, 300, 0.2, "left")]


def test_click_double_click_with_button(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )
    calls = []
    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(
        server, "double_click", lambda x, y, duration, button: calls.append((x, y, duration, button))
    )

    result = _call_tool("click", {"x": 120, "y": 220, "double_click": True, "button": "right"})
    data = json.loads(result)
    assert data["clicked"] is True
    assert data["double_click"] is True
    assert data["button"] == "right"
    assert calls == [(120, 220, 0.2, "right")]



def test_single_tool_call_records_trace(monkeypatch, tmp_path):
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(server.time, "sleep", lambda d: None)

    result = _call_tool("sleep", {"duration": 0.1})
    data = json.loads(result)
    assert data["slept"] is True

    trace_files = list(tmp_path.rglob("trace.jsonl"))
    assert len(trace_files) == 1
    trace_id = trace_files[0].parent.name
    records = trace_module.read_trace(trace_id)
    assert len(records) == 1
    assert records[0]["trace_id"] == trace_id
    assert records[0]["step_index"] == 0
    assert records[0]["tool"] == "sleep"
    assert records[0]["args"] == {"duration": 0.1}
    assert records[0]["result"]["slept"] is True


def test_batch_records_substeps_with_shared_trace_id(monkeypatch, tmp_path):
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(server.time, "sleep", lambda d: None)

    result = _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "sleep", "args": {"duration": 0}},
                {"tool": "sleep", "args": {"duration": 0}},
            ],
        },
    )
    data = json.loads(result)
    assert "trace_id" in data
    trace_id = data["trace_id"]

    records = sorted(trace_module.read_trace(trace_id), key=lambda r: r["step_index"])
    # batch itself + 2 sub-steps
    assert len(records) == 3
    assert records[0]["tool"] == "batch"
    assert records[0]["step_index"] == 0
    assert records[0]["trace_id"] == trace_id
    assert records[1]["tool"] == "sleep"
    assert records[1]["step_index"] == 1
    assert records[1]["trace_id"] == trace_id
    assert records[2]["tool"] == "sleep"
    assert records[2]["step_index"] == 2
    assert records[2]["trace_id"] == trace_id


def test_batch_capture_snapshot_includes_snapshot(monkeypatch, tmp_path):
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module
    import computer_use.snapshot as snapshot_mod

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(server.time, "sleep", lambda d: None)

    def fake_get_ui_snapshot(scope, include_screenshot, trace_id=None):
        return {"scope": scope, "include_screenshot": include_screenshot, "controls": []}

    monkeypatch.setattr(snapshot_mod, "get_ui_snapshot", fake_get_ui_snapshot)

    result = _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "sleep", "args": {"duration": 0}, "capture_snapshot": True},
            ],
        },
    )
    data = json.loads(result)
    assert data["failed_index"] is None
    assert len(data["results"]) == 1
    snapshot_path = data["results"][0]["result"]["snapshot"]
    assert isinstance(snapshot_path, str)
    assert snapshot_path.endswith(".json")
    assert Path(snapshot_path).exists()


def test_get_ui_snapshot_tool_dispatch(monkeypatch, tmp_path):
    import computer_use.trace as trace_module
    import computer_use.snapshot as snapshot_mod

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)

    calls = []

    def fake_get_ui_snapshot(scope, include_screenshot, trace_id=None):
        calls.append((scope, include_screenshot, trace_id))
        return {
            "screenshot_path": "C:/tmp/snap.png",
            "scope": scope,
            "include_screenshot": include_screenshot,
        }

    monkeypatch.setattr(snapshot_mod, "get_ui_snapshot", fake_get_ui_snapshot)

    result = _call_tool("get_ui_snapshot", {"scope": "foreground", "include_screenshot": True})
    data = json.loads(result)
    assert data["screenshot_path"] == "C:/tmp/snap.png"
    assert data["scope"] == "foreground"
    assert data["include_screenshot"] is True
    assert calls[0][0:2] == ("foreground", True)
    assert isinstance(calls[0][2], str)


def test_get_ui_snapshot_blocks_desktop_with_include_screenshot(monkeypatch, tmp_path):
    import computer_use.snapshot as snapshot_mod

    def fail_if_called(*args, **kwargs):
        raise AssertionError("snapshot.get_ui_snapshot must not be called")

    monkeypatch.setattr(snapshot_mod, "get_ui_snapshot", fail_if_called)

    result = _call_tool(
        "get_ui_snapshot", {"scope": "desktop", "include_screenshot": True}
    )
    data = json.loads(result)

    assert data["error"] == "high_cost_snapshot_blocked"
    assert "next_action" in data
    assert "screenshot_path" not in data
    assert "controls" not in data


def test_get_ui_snapshot_large_output_returns_compact_error(monkeypatch, tmp_path):
    import computer_use.mcp_server as server
    import computer_use.snapshot as snapshot_mod

    # Force the post-serialization budget below the fake payload size so the
    # compact-error branch fires regardless of the default 200K threshold.
    monkeypatch.setattr(server, "MAX_INLINE_SNAPSHOT_CHARS", 100)
    large_blob = "x" * 5000
    fake_payload = {
        "scope": "desktop",
        "controls": [{"uid": "0", "name": large_blob, "control_type": "Button"}],
    }

    def fake_get_ui_snapshot(scope, include_screenshot, trace_id=None):
        return fake_payload

    monkeypatch.setattr(snapshot_mod, "get_ui_snapshot", fake_get_ui_snapshot)

    result = _call_tool("get_ui_snapshot", {"scope": "desktop", "include_screenshot": False})
    data = json.loads(result)

    assert data["error"] == "snapshot_output_too_large"
    assert data["scope"] == "desktop"
    assert data["truncated"] is True
    assert data["control_count"] == 1
    assert "next_action" in data
    assert "Do not read full desktop snapshot output" in data["next_action"]
    # The full payload (with the 5K blob) must not leak through.
    assert large_blob not in result


def test_get_ui_snapshot_normal_output_still_returns_controls(monkeypatch, tmp_path):
    import computer_use.snapshot as snapshot_mod

    fake_payload = {
        "scope": "foreground",
        "controls": [
            {"uid": "0", "name": "File", "control_type": "MenuItem"},
            {"uid": "1", "name": "Edit", "control_type": "MenuItem"},
        ],
    }

    def fake_get_ui_snapshot(scope, include_screenshot, trace_id=None):
        return fake_payload

    monkeypatch.setattr(snapshot_mod, "get_ui_snapshot", fake_get_ui_snapshot)

    result = _call_tool("get_ui_snapshot", {"scope": "foreground", "include_screenshot": False})
    data = json.loads(result)

    assert data["scope"] == "foreground"
    assert data["controls"] == fake_payload["controls"]
    assert "error" not in data


def test_composite_error_sets_error_kind_in_trace(monkeypatch, tmp_path):
    import computer_use.trace as trace_module
    import computer_use.composite as composite_mod

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(
        composite_mod,
        "click_by_text",
        lambda *a, **k: {"error": "ui_not_found", "text": "Missing"},
    )

    result = _call_tool("click_by_text", {"text": "Missing"})
    data = json.loads(result)
    assert data["error"] == "ui_not_found"

    trace_files = list(tmp_path.rglob("trace.jsonl"))
    assert len(trace_files) == 1
    trace_id = trace_files[0].parent.name
    records = trace_module.read_trace(trace_id)
    assert len(records) == 1
    assert records[0]["error_kind"] == "ui_not_found"
    assert records[0]["error_message"] == "ui_not_found"


def test_batch_substeps_namespaced_under_run_task_plan(monkeypatch, tmp_path):
    import computer_use.trace as trace_module
    import computer_use.runner as runner_mod
    import computer_use.mcp_server as server

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)

    def fake_dispatch_tool(name, args, cs, trace_id=None, parent_step_index=None):
        if name == "batch":
            return server._batch_tool(args, trace_id=trace_id, parent_step_index=parent_step_index)
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_dispatch_tool", fake_dispatch_tool)

    result = runner_mod.run_task_plan(
        steps=[
            {
                "tool": "batch",
                "args": {
                    "actions": [
                        {"tool": "sleep", "args": {"duration": 0}},
                        {"tool": "sleep", "args": {"duration": 0}},
                    ],
                },
            },
        ],
        trace_id="task-batch",
        capture_screenshots=False,
    )

    assert result["trace_id"] == "task-batch"
    records = trace_module.read_trace("task-batch")
    indices = [r["step_index"] for r in records]
    assert set(indices) == {1, "1.1", "1.2"}
    assert indices[-1] == 1


def test_mcp_run_task_plan_uses_single_trace(monkeypatch, tmp_path):
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)

    data = json.loads(
        _call_tool(
            "run_task_plan",
            {
                "steps": [{"tool": "sleep", "args": {"duration": 0}}],
                "capture_screenshots": False,
            },
        )
    )

    trace_root = trace_module.resolve_trace_root(data["trace_id"])
    assert trace_root is not None
    records = trace_module.read_trace(data["trace_id"])
    assert [record["tool"] for record in records] == ["sleep"]
    assert data["trace_path"] == str(trace_root / "trace.jsonl")
    assert data["artifact_root"] == str(trace_root)
    assert data["artifacts"]["report"] == data["report_path"]


def test_mcp_run_task_plan_with_explicit_id_uses_single_trace(
    monkeypatch, tmp_path
) -> None:
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(server.time, "sleep", lambda duration: None)

    data = json.loads(
        _call_tool(
            "run_task_plan",
            {
                "trace_id": "explicit-trace",
                "steps": [{"tool": "sleep", "args": {"duration": 0}}],
                "capture_screenshots": False,
            },
        )
    )

    assert data["trace_id"] == "explicit-trace"
    trace_root = trace_module.resolve_trace_root("explicit-trace")
    assert trace_root is not None
    report_path = Path(data["report_path"])
    assert report_path.parent == trace_root
    assert report_path.exists()


def test_review_task_response_uses_reviewed_trace_manifest(tmp_path, monkeypatch):
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    trace_module.record_step(
        trace_id="review-manifest",
        step_index=1,
        tool="sleep",
        args={"duration": 0},
    )

    data = json.loads(_call_tool("review_task", {"trace_id": "review-manifest"}))
    trace_root = trace_module.resolve_trace_root("review-manifest")

    assert data["trace_id"] == "review-manifest"
    assert trace_root is not None
    assert data["trace_path"] == str(trace_root / "trace.jsonl")
    assert data["artifact_root"] == str(trace_root)
    assert data["artifacts"] == {
        "screenshots": [],
        "snapshots": [],
        "report": None,
    }


def test_review_task_detail_passthrough(tmp_path, monkeypatch):
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    trace_module.record_step(
        trace_id="review-detail-mcp",
        step_index=1,
        tool="click",
        args={"x": 1, "y": 2},
        result={"clicked": True},
        duration_ms=10,
    )
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("trace.jsonl"))

    data = json.loads(
        _call_tool(
            "review_task",
            {"trace_id": "review-detail-mcp", "detail": True},
        )
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("trace.jsonl"))

    assert "steps" in data
    assert len(data["steps"]) == 1
    assert data["steps"][0]["tool"] == "click"
    assert data["steps"][0]["args"] == {"x": 1, "y": 2}
    assert after == before


def test_handle_review_task_does_not_create_task_context(tmp_path, monkeypatch):
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session
    import computer_use.trace as trace_module

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path / "traces")
    trace_module.record_step(
        trace_id="review-readonly",
        step_index=1,
        tool="sleep",
        args={"duration": 0},
    )
    before = sorted(
        path.relative_to(tmp_path / "traces")
        for path in (tmp_path / "traces").rglob("trace.jsonl")
    )

    data = json.loads(
        server._handle_tool_call(
            "review_task",
            {"trace_id": "review-readonly", "detail": True},
        )
    )
    after = sorted(
        path.relative_to(tmp_path / "traces")
        for path in (tmp_path / "traces").rglob("trace.jsonl")
    )

    assert data["trace_id"] == "review-readonly"
    assert "steps" in data
    assert after == before
    assert not (tmp_path / "tasks").exists()


def test_review_task_session_dispatch_delegates_to_review_module(
    tmp_path, monkeypatch
):
    import computer_use.task_session as task_session
    import computer_use.trace as trace_module

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path / "traces")

    task_id = task_session.start_task("mcp session review")["task_id"]
    trace_module.record_step("mcp-session-trace", 1, "sleep", {"duration": 0})
    task_session.register_trace(
        task_id, "mcp-session-trace", kind="atomic", tool="sleep"
    )
    task_session.complete_trace(task_id, "mcp-session-trace", status="succeeded")

    data = json.loads(
        _call_tool(
            "review_task_session",
            {"task_id": task_id, "detail": True},
        )
    )

    assert data["task_id"] == task_id
    assert "total_steps" in data
    assert data["total_steps"] == 1
    assert "error_distribution" in data
    assert data["traces"][0]["trace_id"] == "mcp-session-trace"
    assert "review" in data["traces"][0]
    assert "steps" in data["traces"][0]["review"]
    assert len(data["traces"][0]["review"]["steps"]) == 1


def test_review_task_session_dispatch_returns_task_not_found(tmp_path, monkeypatch):
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")

    data = json.loads(
        _call_tool("review_task_session", {"task_id": "missing"})
    )

    assert data["error"] == "task_not_found"
    assert data["task_id"] == "missing"


def test_review_task_session_parallel_helper_is_removed():
    import computer_use.mcp_server as server

    assert not hasattr(server, "_review_task_session_result")


def test_tool_logging_redacts_nested_input_values(
    monkeypatch, caplog
) -> None:
    import computer_use.mcp_server as server

    monkeypatch.setattr(
        server,
        "_dispatch_tool",
        lambda *args, **kwargs: json.dumps({"typed": True}),
    )
    caplog.set_level("INFO")

    _call_tool(
        "batch",
        {
            "actions": [
                {"tool": "type", "args": {"text": "log-secret"}},
            ]
        },
    )

    assert "log-secret" not in caplog.text
    assert "redacted" in caplog.text


def test_exception_logging_redacts_input_values(
    monkeypatch, caplog
) -> None:
    import computer_use.mcp_server as server

    monkeypatch.setattr(
        server,
        "_dispatch_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("failed with exception-secret")
        ),
    )
    caplog.set_level("ERROR")

    with pytest.raises(RuntimeError):
        _call_tool("type", {"text": "exception-secret"})

    assert "exception-secret" not in caplog.text


def test_outer_tool_handler_redacts_exception_response_and_log(
    monkeypatch, caplog, tmp_path
) -> None:
    import computer_use.mcp_server as server
    import computer_use.task_session as task_session

    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")
    monkeypatch.setattr(
        server,
        "_call_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("failed with outer-secret")
        ),
    )
    caplog.set_level("ERROR")

    result = server._handle_tool_call(
        "type", {"text": "outer-secret"}
    )

    assert "outer-secret" not in result
    assert "outer-secret" not in caplog.text
    assert "<redacted>" in result


def test_fail_safe_returns_structured_error_and_trace(
    monkeypatch, tmp_path
) -> None:
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module
    import pyautogui

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    monkeypatch.setattr(
        server,
        "_dispatch_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pyautogui.FailSafeException("cursor corner")
        ),
    )

    data = json.loads(_call_tool("click", {"x": 10, "y": 10}))

    assert data["error"] == "fail_safe"
    trace_id = next(path.parent.name for path in tmp_path.rglob("trace.jsonl"))
    record = trace_module.read_trace(trace_id)[0]
    assert record["error_kind"] == "fail_safe"


def test_distribution_critical_tool_descriptions_include_usage_guidance() -> None:
    by_name = {tool.name: tool for tool in TOOLS}

    assert "saved_path" in by_name["screenshot"].description.lower()
    assert "read the returned" in by_name["screenshot"].description.lower()
    assert "real" in by_name["click"].description.lower()
    assert "observe" in by_name["batch"].description.lower()
    assert "task_id" in by_name["start_task"].description
    assert "source of truth" in by_name["review_task_session"].description.lower()


def test_invalid_tool_error_includes_next_action() -> None:
    import computer_use.mcp_server as server

    data = json.loads(
        server._call_tool(
            "batch",
            {"actions": [{"tool": "bad_tool", "args": {}}]},
        )
    )

    failure = data["results"][0]["result"]
    error_kind = failure.get("error_kind") or failure.get("error", "")
    assert "invalid_tool" in error_kind
    assert "next_action" in failure
    assert "allowed_tools" in failure["next_action"]


def test_ui_not_found_error_includes_next_action(monkeypatch) -> None:
    import computer_use.composite as composite
    import computer_use.mcp_server as server

    monkeypatch.setattr(
        composite,
        "click_by_text",
        lambda *args, **kwargs: {"error": "ui_not_found"},
    )

    data = json.loads(
        server._call_tool(
            "click_by_text",
            {"text": "__this_control_does_not_exist_12345__"},
        )
    )

    error_value = data.get("error_kind") or data.get("error", "")
    assert "ui_not_found" in error_value
    assert "next_action" in data
    assert "get_ui_snapshot" in data["next_action"] or "screenshot" in data["next_action"]


def test_fail_safe_error_includes_next_action(monkeypatch) -> None:
    import pyautogui

    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )

    def _raise_fail_safe(*args, **kwargs):
        raise pyautogui.FailSafeException("fail-safe triggered")

    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "click", _raise_fail_safe)

    data = json.loads(server._call_tool("click", {"x": 100, "y": 100}))

    error_value = data.get("error_kind") or data.get("error", "")
    assert "fail_safe" in error_value
    assert "next_action" in data


def test_coordinate_safety_block_error_includes_next_action(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module
    from computer_use import safety

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )

    def _raise_safety(*args, **kwargs):
        raise safety.SafetyError("mocked safety block")

    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "check_target_window", _raise_safety)

    data = json.loads(server._call_tool("click", {"x": 100, "y": 100}))

    error_value = data.get("error_kind") or data.get("error", "")
    assert "safety" in error_value.lower() or "mocked safety block" in error_value
    assert "next_action" in data
    assert "get_monitors" in data["next_action"] or "inspect_point" in data["next_action"]


def test_coordinate_value_error_includes_next_action(monkeypatch) -> None:
    import computer_use.mcp_server as server
    import computer_use.ui_automation as uia_module

    info = uia_module.ControlInfo(
        name="",
        control_type="",
        class_name="",
        process_name="",
        is_password=False,
        rect=None,
        center=None,
    )

    def _raise_coordinate_value_error(*args, **kwargs):
        raise ValueError("coordinates out of monitor bounds")

    monkeypatch.setattr(server, "inspect_point", lambda x, y: info)
    monkeypatch.setattr(server, "click", _raise_coordinate_value_error)

    data = json.loads(server._call_tool("click", {"x": 100, "y": 100}))

    assert "coordinates" in data["error"].lower() or "bounds" in data["error"].lower()
    assert "next_action" in data
    assert "get_monitors" in data["next_action"] or "inspect_point" in data["next_action"]
