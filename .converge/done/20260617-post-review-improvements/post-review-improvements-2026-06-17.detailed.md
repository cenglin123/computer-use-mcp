---
status: active
mixed_dpi_exclusion_ack: pending
---

# Post-Review 改进计划（2026-06-17）

> **For agentic workers:** 本计划按优先级分阶段实施。每个 Task 完成后应能独立提交并通过测试。

## 背景

外部评审对 `computer-use-mcp` 给出 B+/A- 综合评价，指出项目已在架构设计、安全分层、审计模型和 Agent 协作文档上具备优势，但在**真实 GUI 集成测试**、**首次使用体验**、**mcp_server 可维护性**和**混合 DPI 支持**等方面存在明显短板。

本计划将评审建议转化为可执行的改造任务，并明确已有能力（如 doctor UIA 检查、截图敏感窗口 redaction）不需要重复建设。

---

## 范围

**本计划共包含 5 个 Task。**

**包含：**

- 真实 GUI 集成测试骨架与首批闭环测试。
- `allowed_commands` 首次使用体验优化。
- 将 `mcp_server.py` 中静态的 MCP tool schemas 提取到独立模块 `computer_use/tools/schemas.py`。
- 文档补全：说明当前已实现的 redaction、UIA 检查能力。
- 全量回归与归档。

**不包含：**

- 混合 DPI 多显示器支持（技术风险高，需单独立项）。
- 替换 pyautogui 为更低层 Windows API（超出当前 sprint 范围）。
- 操作取消/超时机制（需要 Runner 架构改造，单独立项）。
- 异常吞没较多：需要系统性 trace/logging 改造，超出本 sprint 范围。
- 危险命令正则可能绕过：当前为黑名单策略；迁移到白名单策略需要设计评审，超出本 sprint 范围。
- 安全规则 fuzz 测试：当前以参数化单元测试覆盖主要边界；fuzz 测试需要额外框架与 CI 支持，超出本 sprint 范围。
- 独立 OCR 工具 / 视觉 fallback 引擎的实现：当前由多模态模型直接读取截图 + UIA 不可用时回退到坐标操作；引入独立 OCR 或视觉引擎需要额外依赖与架构评审，超出本 sprint 范围。

---

## 文件结构与职责

- Create: `tests/manual/test_notepad_smoke.py`
  - 首个真实 GUI smoke 测试：启动 notepad → 截图 → UIA 前台快照 → 再次截图，验证 screenshot 工具可重复执行并返回不同的有效文件路径。
- Create: `tests/manual/conftest.py`
  - 集成测试 fixture：用 `subprocess.Popen` 直接启动已知可执行文件并捕获 PID，测试结束后清理进程。
- Verify: `pytest.ini`
  - 确认已存在 `manual` marker；本计划复用该 marker，不新增 marker。
- Modify: `pyproject.toml`
  - 在 dev 依赖组中新增 `pytest-timeout>=2.0`，以支持 `@pytest.mark.timeout(60)`。
- Modify: `computer_use/launcher.py`
  - 增强 `launch_app` 在白名单为空时的错误提示，并指向配置示例。
- Create: `config.example.yaml`
  - 增加 `allowed_commands` 示例白名单。
- Create: `computer_use/tools/__init__.py`, `computer_use/tools/schemas.py`
  - 将 `mcp_server.py` 中静态的 `TOOLS` schema 列表及 schema 相关常量迁移到 `computer_use/tools/schemas.py`。
- Modify: `computer_use/mcp_server.py`
  - 从 `computer_use.tools.schemas` 导入 `TOOLS`；保留 `_call_tool`、`_dispatch_tool`、`_handle_tool_call`、`_batch_tool` 及 batch/composite 运行时逻辑不变。
- Modify: `docs/deployment.md`（Task 4 统一负责）
  - 说明 doctor 已检查 UIA，截图 redaction 已支持敏感窗口。
- Modify: `docs/pitfalls.md`（Task 4 统一负责）
  - 说明混合 DPI fail-fast 原因、allowed_commands 首次配置要求、视觉 fallback 现状。
- Modify: `docs/overview.md`（Task 4 统一负责）
  - 补充测试策略分层（单元/集成/性能）。
- Modify: `README.md`（Task 4 统一负责）
  - 增加集成测试运行说明和 allowed_commands 配置提示。
- Modify: `CHANGELOG.md`（Task 4 统一负责）
  - 记录最终变更。

---

### Task 1: 真实 GUI 集成测试骨架

**Files:**
- Create: `tests/manual/conftest.py`
- Create: `tests/manual/test_notepad_smoke.py`
- Modify: `pytest.ini`
- Modify: `pyproject.toml`
- Test: `tests/manual/test_notepad_smoke.py`

- [ ] **Step 1: 写 RED 测试**

创建 `tests/manual/test_notepad_smoke.py`：

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

# UIA 是可选依赖；本集成测试需要 uiautomation 才能验证 get_ui_snapshot。
pytest.importorskip("uiautomation")


@pytest.mark.manual
@pytest.mark.timeout(60)
def test_notepad_launch_and_screenshot(manual_app):
    from computer_use import mcp_server

    app = manual_app("notepad")
    try:
        # 当前实现中 screenshot 工具 schema 包含 `save_path` 参数，且 `_dispatch_tool` 会校验
        # `save_path` 必须位于配置的 `screenshot_dir` 之下（`computer_use.mcp_server` screenshot 工具 handler）。
        # Fixture 通过 monkeypatch 将 `screenshot_dir` 指向临时目录，满足校验。

        # 当前实现中 `_call_tool` 返回 JSON 字符串；若返回类型未来变更，需同步调整测试。

        # 1. 截图到 fixture 提供的临时目录
        shot_path = Path(app.screenshot_dir) / "shot1.png"
        shot = json.loads(
            mcp_server._call_tool(
                "screenshot", {"monitor": 1, "save_path": str(shot_path)}
            )
        )
        saved1 = Path(shot["saved_path"])
        assert str(saved1) == str(shot_path)
        assert saved1.exists() and saved1.stat().st_size > 0

        # 2. 验证 UIA 返回了控件列表
        # 当前实现中 `computer_use.snapshot.get_ui_snapshot` 返回字典包含 `controls` 键；本断言依赖该实现。
        snap = json.loads(
            mcp_server._call_tool(
                "get_ui_snapshot",
                {"scope": "foreground", "include_screenshot": False},
            )
        )
        assert snap["controls"]

        # 3. 再次截图，验证 screenshot 工具可重复执行并返回不同文件
        shot2_path = Path(app.screenshot_dir) / "shot2.png"
        shot2 = json.loads(
            mcp_server._call_tool(
                "screenshot", {"monitor": 1, "save_path": str(shot2_path)}
            )
        )
        saved2 = Path(shot2["saved_path"])
        assert str(saved2) == str(shot2_path)
        assert saved2.exists() and saved2.stat().st_size > 0
        assert saved1 != saved2
    finally:
        app.close()
```

> **⚠️ 安全提示**：本测试启动真实 Windows 应用并截图。运行集成测试时必须确保没有用户正在操作键盘/鼠标，避免干扰前台窗口。

> **依赖说明**：`@pytest.mark.timeout(60)` 需要 `pytest-timeout`。请在 dev 依赖中安装 `pytest-timeout`，或在 `pytest.ini` 注册 `timeout` marker；亦可换用其他超时机制。fixture 使用 `psutil`（已在主依赖中）和 `win32gui`（由 `pywin32` 提供）做跨语言窗口匹配。

> **测试接口说明**：集成测试直接调用 `mcp_server._call_tool` 作为内部测试钩子，以在不启动完整 MCP server 的情况下直接验证 tool handler 行为。这是可接受的，因为测试重点是各工具在真实 GUI 环境下的行为，而非 MCP 协议传输层。

- [ ] **Step 2: 添加 pytest-timeout 到 dev 依赖**

在 `pyproject.toml` 的 `[project.optional-dependencies]` dev 组中追加：

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-timeout>=2.0",
    "pywin32>=306",
]
```

`pywin32` 为集成测试 fixture 的 `win32gui` 调用提供依赖。

然后重新安装 dev 依赖：

```powershell
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

- [ ] **Step 3: 运行并确认 RED**

```powershell
./.venv/Scripts/python.exe -m pytest tests/manual/test_notepad_smoke.py -v
```

Expected: FAIL，`tests/manual/` 尚不存在或 fixture 未定义。

- [ ] **Step 4: 实现集成测试 fixture**

创建 `tests/manual/conftest.py`：

```python
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Generator

import computer_use.mcp_server
import psutil
import pytest
import pyautogui


try:
    import win32gui
except Exception:  # pragma: no cover
    win32gui = None


@dataclass
class ManagedApp:
    proc: subprocess.Popen
    name: str
    screenshot_dir: str

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    import logging
                    logging.warning(
                        "Failed to terminate started process pid=%s after terminate+kill",
                        self.proc.pid,
                    )
        # 清理本次测试生成的截图文件
        for path in Path(self.screenshot_dir).glob("*"):
            path.unlink(missing_ok=True)


def _find_window_by_process(process_name: str, timeout: float = 10.0):
    if win32gui is None:
        pytest.skip("win32gui (pywin32) is not available")
    deadline = time.time() + timeout
    process_name = process_name.lower()
    while time.time() < deadline:
        for window in pyautogui.getAllWindows():
            try:
                hwnd = window._hWnd
                _, pid = win32gui.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                if proc.name().lower() == process_name:
                    return window
            except Exception:
                continue
        time.sleep(0.2)
    return None


def _wait_and_activate_window(
    process_name: str, timeout: float = 10.0, interval: float = 0.5
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = _find_window_by_process(process_name, timeout=interval)
        if window:
            try:
                window.activate()
                return
            except Exception as exc:
                logging.warning("failed to activate window: %s", exc)
        time.sleep(interval)
    pytest.fail(
        f"Window for process '{process_name}' did not appear within {timeout}s"
    )


@pytest.fixture
def manual_app(monkeypatch) -> Generator[Callable, None, None]:
    launched: list[ManagedApp] = []
    _known_exes = {"notepad": "notepad.exe"}
    screenshot_dir = tempfile.mkdtemp(prefix="cu-manual-")
    original_load_config = computer_use.mcp_server.load_config

    monkeypatch.setattr(
        computer_use.mcp_server,
        "load_config",
        lambda: {**original_load_config(), "screenshot_dir": Path(screenshot_dir)},
    )

    def _launch(name: str) -> ManagedApp:
        exe = _known_exes.get(name.lower())
        if not exe:
            pytest.skip(f"unknown manual app: {name}")
        proc = subprocess.Popen([exe])
        # Register proc for cleanup immediately so teardown terminates it even if
        # window activation fails.
        app = ManagedApp(proc=proc, name=name, screenshot_dir=screenshot_dir)
        launched.append(app)
        try:
            _wait_and_activate_window(exe)
        except Exception:
            app.close()
            raise
        return app

    try:
        yield _launch
    finally:
        for app in launched:
            app.close()
        shutil.rmtree(screenshot_dir, ignore_errors=True)
```

**Fixture 契约**：

- 集成测试启动应用程序时直接使用 `subprocess.Popen` 以获得可靠的 PID，并避免双重启动。
- `launcher.launch_app` 的行为由 `tests/test_launcher.py` 中的单元测试覆盖；集成测试不调用它。
- fixture 仅验证请求的应用名称是否存在于已知可执行文件映射（`_known_exes`）中；未知名称调用 `pytest.skip`。
- `ManagedApp.close()` 仅终止 `subprocess.Popen` 启动的真实应用进程；若该进程在 `terminate()` 与 `kill()` 后仍无法结束，则记录警告，不会扩大清理范围。
- `_launch` 在调用 `subprocess.Popen` 后立即创建 `ManagedApp` 并加入 `launched` 列表，再尝试激活窗口；若窗口激活失败，teardown 仍能终止已启动的进程，避免 notepad 遗留。
- fixture 启动应用后，通过进程名（`notepad.exe`）而非窗口标题匹配目标窗口，以支持非英文版 Windows；找到后调用 `.activate()` 将其置为前台，10 秒超时失败则测试失败并给出明确提示。
- fixture 使用 `pyautogui.getAllWindows()` 枚举窗口；`pyautogui` 已是 `computer-use-mcp` 声明的主依赖，无需额外安装。
- fixture 对 `win32gui` 做可选导入保护：若 `pywin32` 未安装，`_find_window_by_process` 会调用 `pytest.skip`，避免在缺少 dev 依赖的环境因 collection 失败。
- fixture 为每个测试创建独立的临时 `screenshot_dir`，并通过 monkeypatch 将 `computer_use.mcp_server.load_config` 返回的 `screenshot_dir` 指向该临时目录，确保 screenshot 工具的 `save_path` 校验通过；测试代码将截图保存到 `app.screenshot_dir`，避免污染用户配置的截图目录；`ManagedApp.close()` 与 fixture teardown 会自动清理截图文件与临时目录。
- **当前实现中**：`computer_use.mcp_server._dispatch_tool` 在处理 `screenshot` 工具时会在调用时调用 `load_config()`，因此 monkeypatch `computer_use.mcp_server.load_config` 在测试运行时生效。
- **运行要求**：集成测试启动真实 Windows 应用并截图，必须在无用户操作输入设备的真实 Windows 桌面环境中运行。

- [ ] **Step 5: 使用现有 `manual` marker 并配置 CI 跳过**

项目已存在 `manual` marker 表示"需要真实 Windows 桌面环境且不应在 CI 运行"。本 Task 复用该 marker，不再新增 `integration` marker。

确认 `pytest.ini` 中已有：

```ini
markers =
    manual: tests that require a real Windows desktop environment and should not run in CI.
```

检查 `.github/workflows/*.yml`（或项目使用的 CI 配置文件）：

- 若存在 CI 工作流，将其 pytest 命令更新为：
  ```powershell
  ./.venv/Scripts/python.exe -m pytest tests/ -m "not manual" -v
  ```
- 若当前仓库尚未配置 CI 工作流，本步骤不产生文件变更；仅保留 marker 与跳过命令说明。

本地默认跳过 manual 测试：

```powershell
./.venv/Scripts/python.exe -m pytest tests/ -m "not manual" -v
```

- [ ] **Step 6: 运行集成测试**

```powershell
./.venv/Scripts/python.exe -m pytest tests/manual/test_notepad_smoke.py -v
```

Expected: PASS（在真实 Windows 桌面环境）。

- [ ] **Step 7: 提交**

```powershell
git add tests/manual/ pytest.ini pyproject.toml
git commit -m "test: add real GUI manual smoke test with notepad"
```

---

### Task 2: 优化 allowed_commands 首次使用体验

**Files:**
- Modify: `computer_use/launcher.py`
- Create/Modify: `config.example.yaml`
- Test: `tests/test_launcher.py`

> 说明：本 Task 只负责 launcher 错误消息与配置示例文件；相关跨项目文档由 Task 4 统一更新，避免职责重叠。

- [ ] **Step 1: 写 RED 测试**

在 `tests/test_launcher.py` 追加：

> **结构契约**：当前实现中 `computer_use.launcher.launch_app` 在白名单拦截时返回 `{"launched": False, "error": <str>}`。本 RED 测试期望该结构。

```python
def test_launch_app_empty_allowed_list_shows_config_hint(monkeypatch) -> None:
    from types import SimpleNamespace

    from computer_use import launcher
    from computer_use import safety

    # Ensure launch_app reaches the whitelist branch even without win32com.
    fake_shell = SimpleNamespace(
        Namespace=lambda folder_id: SimpleNamespace(Items=lambda: [])
    )
    fake_wscript = SimpleNamespace(
        CreateShortcut=lambda path: SimpleNamespace(TargetPath=None)
    )
    monkeypatch.setattr(launcher, "_get_shell_dispatch", lambda: fake_shell)
    monkeypatch.setattr(launcher, "_get_wscript_shell", lambda: fake_wscript)

    # Simulate that the launcher found a notepad shortcut.
    fake_item = type("FakeItem", (), {"Name": "Notepad", "InvokeVerb": lambda self, x: None})()
    monkeypatch.setattr(
        launcher,
        "_collect_lnk_items",
        lambda shell: [(fake_item, r"C:\fake\Notepad.lnk")],
    )
    # Resolve the shortcut to a notepad.exe path.
    monkeypatch.setattr(
        launcher,
        "_resolve_lnk_target",
        lambda lnk_path, wscript: r"C:\fake\notepad.exe",
    )
    # Empty allowed commands whitelist.
    monkeypatch.setattr(safety, "_allowed_commands", lambda: [])

    result = launcher.launch_app("notepad")

    assert result["launched"] is False
    assert "allowed_commands" in result["error"].lower()
    assert "config.example.yaml" in result["error"] or "config.yaml" in result["error"]
    # Sensitive-process block should use a distinct message.
    assert "sensitive" not in result["error"].lower()
```

> **测试隔离说明**：该测试必须固定 `allowed_commands` 状态并模拟快捷方式解析。通过 `monkeypatch` 将 `safety._allowed_commands` 替换为返回空列表，避免受本地 `config.yaml` 内容影响；同时 mock `launcher._collect_lnk_items` 和 `launcher._resolve_lnk_target`，避免依赖真实 Start Menu 内容，确保能命中 allowed_commands 为空的分支。当前实现中 `computer_use.safety._allowed_commands` 是可调用对象（函数），返回 list；monkeypatch 替换为 `lambda: []` 可生效。当前实现中 `computer_use.safety._allowed_commands` 在 `computer_use.safety.is_allowed_command` 调用时被动态调用，因此 monkeypatch 在测试运行时生效。

- [ ] **Step 2: 运行并确认 RED**

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_launcher.py -k empty_allowed_list -v
```

Expected: FAIL，当前错误消息不含配置提示。

- [ ] **Step 3: 修改 launcher 错误消息**

在 `computer_use/launcher.py` 中新增/更新两个错误常量，使白名单拦截与敏感进程拦截使用不同提示：

```python
_NOT_ALLOWED_ERROR = (
    "Target is not in allowed_commands whitelist. "
    "Add allowed app names to config.yaml (see config.example.yaml) to enable launch_app."
)

_SENSITIVE_PROCESS_ERROR = (
    "Target is in sensitive process list and cannot be launched."
)
```

修改 `launch_app` 两处拦截分支：

- `is_allowed_command(target_path)` 返回 `False` 时使用 `_NOT_ALLOWED_ERROR`。
- `check_target_window(...)` 抛出 `SafetyError` 时使用 `_SENSITIVE_PROCESS_ERROR`。

保持原有返回结构不变。

- [ ] **Step 4: 提供配置示例**

> 若 `config.example.yaml` 已存在，保留现有内容并追加示例条目，不要直接覆盖。

创建或更新 `config.example.yaml`：

```yaml
allowed_commands:
  - notepad.exe
  - calc.exe
  - mspaint.exe
```

- [ ] **Step 5: 运行测试并提交**

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_launcher.py -v
git add computer_use/launcher.py config.example.yaml tests/test_launcher.py
git commit -m "feat: improve launch_app first-time error message and config example"
```

---

### Task 3: 提取 MCP tool schemas 到独立模块

**Files:**
- Create: `computer_use/tools/__init__.py`
- Create: `computer_use/tools/schemas.py`
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_server.py`

**本 Task 明确不做的范围**：

- **不迁移** `_call_tool`、`_dispatch_tool`、`_handle_tool_call`、`_batch_tool` 及 composite/batch 运行时逻辑。
- **不拆分** 工具调用路由、batch 执行、composite adapter；这些保留在 `mcp_server.py` 原位置不变。
- 本 Task 只是将静态的 `TOOLS` schema 列表及紧密耦合的 schema 常量迁移到新模块，作为 `mcp_server.py` 模块化的第一步；后续拆分（tool handlers、batch/composite 运行时）将在本计划完成后另立项推进。

- [ ] **Step 1: 写 RED 测试**

在 `tests/test_mcp_server.py` 追加：

```python
def test_tool_schemas_module_exports_tools() -> None:
    from computer_use.tools import schemas

    assert len(schemas.TOOLS) > 0
    assert any(tool.name == "screenshot" for tool in schemas.TOOLS)
    assert schemas._MANIFEST_TOOL_NAMES
    assert schemas._TASK_MANAGEMENT_TOOLS
    assert schemas._TASK_CONTEXT_EXCLUDED_TOOLS
    assert schemas.MAX_SLEEP_DURATION
```


- [ ] **Step 2: 运行并确认 RED**

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_mcp_server.py -k tool_schemas_module_exports_tools -v
```

Expected: FAIL，`computer_use.tools.schemas` 尚不存在。

- [ ] **Step 3: 创建 tools 子包与 schemas 模块**

创建 `computer_use/tools/__init__.py`：

```python
from __future__ import annotations

from computer_use.tools.schemas import TOOLS

__all__ = ["TOOLS"]
```

创建 `computer_use/tools/schemas.py`：

- 将 `mcp_server.py` 中静态的 `TOOLS: list[Tool]` 列表完整迁移至此。
- 将 schema 定义紧密耦合的常量迁移至此：
  - `_MANIFEST_TOOL_NAMES`
  - `_TASK_MANAGEMENT_TOOLS`
  - `_TASK_CONTEXT_EXCLUDED_TOOLS`
  - `MAX_SLEEP_DURATION`（`sleep` tool 的 schema 上限，同时被 `_dispatch_tool` 复用）
- 将 `_attach_task_context_schemas()` 函数迁移至此，并在模块加载时调用，使 `TOOLS` 在导入时即附加 `task_id` schema。
- 保持 `mcp_server.py` 运行时所需的 `_NEXT_ACTION_*` 等常量不移动；不移动的其他辅助函数（如 `_error_kind_for_result`）也不移动。

`schemas.py` 应导入：

```python
from mcp.types import Tool
from computer_use.core import DEFAULT_MOVE_DURATION, VALID_MOUSE_BUTTONS
from computer_use.tool_contract import BATCH_ACTION_TOOL_NAMES, TASK_STEP_TOOL_NAMES
```

- [ ] **Step 4: 修改 mcp_server.py 使用 schemas 模块**

在 `mcp_server.py` 中：

```python
from computer_use.tools.schemas import (
    TOOLS,
    _MANIFEST_TOOL_NAMES,
    _TASK_CONTEXT_EXCLUDED_TOOLS,
    _TASK_MANAGEMENT_TOOLS,
    MAX_SLEEP_DURATION,
)
```

- 删除原 `mcp_server.py` 中的 `TOOLS` 列表定义、`_MANIFEST_TOOL_NAMES`、`_TASK_MANAGEMENT_TOOLS`、`_TASK_CONTEXT_EXCLUDED_TOOLS`、`MAX_SLEEP_DURATION`、`_attach_task_context_schemas()` 及调用。
- **保持 `_call_tool`、`_dispatch_tool`、`_handle_tool_call`、`_batch_tool`、`_dispatch_pointer_tool`、`_run_mouse_tool`、`_current_logical_position`、server 生命周期、`serve()`、prompt 注册等代码完全不变。**
- `_call_tool` 中仍使用 `_MANIFEST_TOOL_NAMES` 和 `_TASK_MANAGEMENT_TOOLS`（现在从 `schemas` 导入），无需修改逻辑。

- [ ] **Step 5: 运行测试**

```powershell
./.venv/Scripts/python.exe -m pytest tests/test_mcp_server.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/tools/ computer_use/mcp_server.py tests/test_mcp_server.py
git commit -m "refactor: extract MCP tool schemas to computer_use/tools/schemas"
```

---

### Task 4: 文档补全（说明已实现的 redaction/UIA）

**Files:**
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Modify: `docs/overview.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

> 说明：Task 4 是跨项目文档的唯一负责人。Task 1 不再修改 `README.md`。Task 2 只修改 launcher 与配置示例文件，不再写入 `docs/deployment.md` 或 `docs/pitfalls.md`。

- [ ] **Step 1: 更新 deployment.md**

在 doctor 节后追加：

```markdown
### 已有安全与可用性能力

- **UIA 检查**：`doctor` 会检查 `uiautomation` 是否可导入；缺失时标记为 warning，但 server 仍可启动（视觉任务回退到坐标操作）。
- **截图 redaction**：`core.py` 已实现敏感顶层窗口相交检测，截图时会用红色块覆盖敏感区域。该能力默认启用。
```

- [ ] **Step 2: 更新 README.md**

在 `README.md` 末尾追加：

```markdown
### 集成测试

`tests/manual/` 下的测试会启动真实 Windows 应用并发送真实鼠标/键盘输入。运行前请退出所有敏感应用，并确保没有用户正在操作键盘/鼠标。

CI 默认跳过集成测试：

    ./.venv/Scripts/python.exe -m pytest tests/ -m "not manual" -v

在真实 Windows 桌面环境可单独运行：

    ./.venv/Scripts/python.exe -m pytest tests/manual/ -v
```

- [ ] **Step 3: 更新 pitfalls.md**

追加：

```markdown
### 首次使用 launch_app 被拦截

`launch_app` 默认使用 `allowed_commands` 白名单。如果白名单为空，任何应用启动都会被拦截。
解决方法：复制 `config.example.yaml` 为 `config.yaml`，按需要添加允许的应用名称。

### 混合 DPI 多显示器 fail-fast

当前版本为保障坐标精度，检测到混合 DPI 多显示器时会直接拒绝输入操作。临时解决方法是将外接显示器缩放比例设为与主屏相同；长期支持需等待后续立项。

### 视觉 fallback

本项目不提供 OCR 工具；需要识别自定义绘制控件或截图中的文字时，由多模态模型直接读取截图完成。UIA 不可用时回退到坐标操作。

### 集成测试副作用

`tests/manual/` 下的测试会启动真实 Windows 应用并发送真实鼠标/键盘输入。运行前请退出所有敏感应用，并确保没有用户正在操作键盘/鼠标。
```

- [ ] **Step 4: 更新 overview.md 测试策略**

追加测试策略小节：

```markdown
### 测试分层

- **单元测试**：mock 覆盖 core/safety/ui_automation/mcp_server 逻辑。
- **集成测试**：`tests/manual/` 下使用真实 Windows 应用做端到端闭环验证。集成测试必须在无用户操作键盘/鼠标的真实 Windows 桌面环境中手动运行；CI 默认跳过。
- **性能/压力测试**：当前未覆盖，计划后续补充 trace 数量增长下的 locator 性能基准。
```

- [ ] **Step 5: 运行 audit 并提交**

```powershell
./.venv/Scripts/python.exe scripts/agent_links.py check
./.venv/Scripts/python.exe scripts/audit.py check
```

> 若终端为 Windows PowerShell 默认编码，先执行 `chcp 65001` 切换到 UTF-8，避免中文字符乱码。

```powershell
./.venv/Scripts/python.exe scripts/changelog.py add --title "docs: clarify existing redaction and uia check capabilities" --body "说明 doctor 已检查 UIA、截图 redaction、无 OCR 工具、launch_app 白名单首次配置要求，以及 README 集成测试运行说明。"
git add docs/deployment.md docs/pitfalls.md docs/overview.md README.md CHANGELOG.md
git commit -m "docs: clarify existing redaction and uia check capabilities"
```

---

### Task 5: 全量回归与归档

**Files:**
- Move after acceptance: `docs/plans/active/post-review-improvements-2026-06-17.md` to `docs/plans/completed/`
- Modify: `docs/CURRENT.md`

- [ ] **Step 1: 确认 P0 排除签收 Gate**

在执行任何代码变更前，确认评审建议中的 #1 P0 项「混合 DPI 多显示器支持」已明确排除并获得用户/维护者书面确认。

确认方式（任选其一，必须在 plan 中可追踪）：

- 在本 plan 文件顶部 frontmatter 中，将 `mixed_dpi_exclusion_ack: pending` 更新为 `mixed_dpi_exclusion_ack: "<signer> <date>"`。
- 或在 Task 5 最终提交消息中引用确认来源（issue/PR 评论链接、会议纪要路径）。

当前 frontmatter 已预留 `mixed_dpi_exclusion_ack: pending`，执行前必须替换为实际确认信息。

- [ ] **Step 2: 全量验证**

```powershell
./.venv/Scripts/python.exe -m pytest tests/ -m "not manual" -v
./.venv/Scripts/python.exe -m compileall -q computer_use
./.venv/Scripts/python.exe scripts/agent_links.py check
./.venv/Scripts/python.exe scripts/audit.py check
git diff --check
```

Expected: 全部通过。

> 在真实 Windows 桌面环境可单独运行 `pytest tests/manual/ -v`。

- [ ] **Step 3: 归档计划**

```powershell
New-Item -ItemType Directory -Path "docs/plans/completed" -Force
Move-Item docs/plans/active/post-review-improvements-2026-06-17.md docs/plans/completed/
```

更新 `docs/CURRENT.md` 为无进行中任务。

- [ ] **Step 4: 最终提交**

```powershell
git add docs/plans/completed/ docs/CURRENT.md
git commit -m "docs: archive post-review improvement plan"
```

---

## 验收标准

- `tests/manual/test_notepad_smoke.py` 在真实 Windows 环境、且无用户操作输入设备时通过。
- `launch_app` 在 `allowed_commands` 为空时给出包含配置示例路径的错误。
- `computer_use/tools/schemas.py` 存在且导出 `TOOLS`；`mcp_server.py` 从 `computer_use.tools.schemas` 导入 `TOOLS`，不再定义静态 `TOOLS` 列表。
- **本计划不拆分 `_call_tool`、`_dispatch_tool`、`_handle_tool_call`、`_batch_tool` 及 composite adapter；这些运行时逻辑仍保留在 `mcp_server.py`。**
- `pytest tests/ -m "not manual"` 全部通过。
- `scripts/agent_links.py check` 和 `scripts/audit.py check` 通过。
- 文档明确说明 UIA 检查、redaction 的当前状态；不声称 OCR 为已有能力。
- **前置 gate**：P0 项「混合 DPI 多显示器支持」排除已获用户/维护者书面确认；本计划执行后 2 周内须独立创建 `docs/plans/active/multi-dpi-support.md` 并启动设计评审。

## 风险与取舍

- 真实 GUI 集成测试依赖 Windows 桌面环境并生成截图；已使用临时 `screenshot_dir`、进程名窗口匹配、仅清理 fixture 自身启动的进程来缓解副作用，但仍需在无用户操作时运行。CI 中默认使用 `-m "not manual"` 跳过。
- `mcp_server.py` 的 schema 提取是低风险重构，不触及 `_call_tool`/`_dispatch_tool`/`_batch_tool` 运行时逻辑；只需确保 import 路径和 MCP tool 名称不变。
- 混合 DPI 支持需要重写坐标系与 monitor 检测逻辑，技术风险高、测试成本高，作为 P0 仍超出当前 sprint 容量，因此明确排除并计划后续单独立项。
- **P0 项排除确认**：评审建议中的 #1 P0 项「混合 DPI 多显示器支持」未纳入本计划范围。执行本计划前，需用户/维护者确认接受此项取舍；后续应在 2 周内独立创建 `docs/plans/active/multi-dpi-support.md` 计划并启动设计评审。
