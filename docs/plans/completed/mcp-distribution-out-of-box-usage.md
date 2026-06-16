# MCP Distribution Out-of-Box Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让用户安装并注册 Computer Use MCP 后，即使不了解本项目，也能通过 MCP 内置 prompts、工具契约、doctor、自检示例和文档入口获得正确使用路径，降低纯文本模型误用、盲点坐标、绕过安全层和 trace 误报的概率。

**Architecture:** 建立一份 `computer_use.guidance` 作为 agent 使用纪律的单一事实源，再向 MCP prompts、Skill、通用文档和 doctor 输出派生。MCP server 在 `tools/list` 之外注册 `prompts/list` 与 `prompts/get`，让支持 MCP prompts 的客户端安装后即可发现使用指南；不支持 prompts 的客户端仍可通过 README、`docs/agent-usage.md` 和 `skills/computer-use/SKILL.md` 获取同等指导。CLI 增加 `doctor`，安装后先验证环境、配置、显示器、可写目录、截图能力和模型能力提示，再进入真实 GUI 输入任务。

**Tech Stack:** Python 3.11+、MCP Python SDK、pytest、argparse、pathlib、现有 `computer_use.mcp_server` / `computer_use.cli` / `computer_use.config` / `computer_use.core` / `computer_use.snapshot` / `computer_use.trace`。

---

## 背景判断

公开分发后，用户的 MCP 客户端能力不一致：

- 有些客户端支持 Skill，有些只支持 MCP tools。
- 有些客户端支持 MCP prompts，有些不会主动读取仓库文档。
- 有些模型是多模态，有些是纯文本。
- 用户可能只完成 server 注册，就直接要求 agent “打开某个 GUI 并点击”。

因此不能把正确使用完全寄托在 `skills/computer-use/SKILL.md`。需要把指导下沉到 MCP 协议层、工具 schema、错误响应、安装自检和示例中。

## 范围

包含：

- MCP prompts：安装后可由客户端发现的 agent 使用指南。
- Guidance 单一事实源：避免 Skill、docs、prompts 内容漂移。
- CLI `doctor`：环境和配置自检，含良性目录可写探测。
- 工具 description 和错误响应的可执行 next action。
- README 与通用客户端示例：从安装到 smoke test 的最短路径。
- 自动化测试：确保 prompts、doctor、工具描述和文档入口不漂移。

不包含：

- 发布 PyPI/npm 包。
- 远程 HTTP MCP transport。
- 让纯文本模型具备视觉能力。
- 放宽主屏输入限制、密码输入特性或安全窗口检查。
- 自动修改用户 MCP 客户端配置。

## 文件结构与职责

- Create: `computer_use/guidance.py`
  - Agent 使用纪律的单一事实源；导出 prompt 定义、短提示、能力边界、doctor 提醒。
- Modify: `computer_use/mcp_server.py`
  - 注册 `list_prompts` / `get_prompt`；复用 `computer_use.guidance`；强化工具 description。
- Create: `computer_use/doctor.py`
  - 安装自检，含良性目录可写探测，不执行鼠标键盘输入。
- Modify: `computer_use/cli.py`
  - 增加 `doctor` 命令，并保持导入 CLI 不加载 `pyautogui`。
- Modify: `skills/computer-use/SKILL.md`
  - 保持与 guidance 的核心规则一致，并指向 MCP prompts。
- Modify: `docs/agent-usage.md`
  - 说明 prompts、Skill、通用提示词三种客户端接入方式。
- Modify: `README.md`
  - 注册后流程改为：安装 -> doctor -> 客户端 guidance -> read-only smoke -> GUI task。
- Modify: `docs/deployment.md`
  - 增加分发、自检和模型能力要求。
- Modify: `docs/api.md`
  - 记录 MCP prompts 契约。
- Modify: `docs/pitfalls.md`
  - 增加公开分发后的常见误用。
- Modify: `docs/overview.md`
  - 更新 guidance 单一事实源架构说明。
- Create: `examples/clients/generic-mcp.json`
  - 通用 MCP 客户端配置模板（用户必须替换为自己的绝对路径）。
- Create: `examples/clients/kimi-code.toml`
  - Kimi Code 配置模板（用户必须替换为自己的绝对路径）。
- Create: `examples/clients/agent-prompt.md`
  - 不支持 MCP prompts/Skill 的客户端可复制提示词。
- Modify: `STRUCTURE.md`
  - 补充 examples 与 agent guidance 入口。
- Modify: `CHANGELOG.md`
  - 记录最终变更。
- Test: `tests/test_mcp_prompts.py`
  - 验证 prompts 列表、内容和 MCP message 形状。
- Test: `tests/test_cli.py`
  - 验证 `doctor` 输出和 CLI 延迟导入。
- Test: `tests/test_mcp_server.py`
  - 验证关键工具 description 包含能力边界和 next action。

---

### Task 1: 建立 guidance 单一事实源

**Files:**
- Create: `computer_use/guidance.py`
- Test: `tests/test_mcp_prompts.py`

- [x] **Step 1: 写 RED 测试**

创建 `tests/test_mcp_prompts.py`，先验证计划中的 prompt 名称和核心内容：

```python
from __future__ import annotations


def test_guidance_prompt_registry_contains_distribution_prompts() -> None:
    from computer_use import guidance

    names = {prompt.name for prompt in guidance.PROMPTS}

    assert names == {
        "computer_use_guidance",
        "computer_use_visual_task",
        "computer_use_text_only_limits",
        "computer_use_safety_checklist",
    }


def test_guidance_mentions_multimodal_and_no_pyautogui_bypass() -> None:
    from computer_use import guidance

    text = guidance.prompt_text("computer_use_guidance")

    assert "multimodal" in text.lower()
    assert "text-only" in text.lower()
    assert "Do not bypass" in text
    assert "pyautogui" in text
    assert "start_task" in text
    assert "batch" in text
    assert "review_task_session" in text
```

- [x] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: FAIL，`computer_use.guidance` 尚不存在。

- [x] **Step 3: 实现 `computer_use/guidance.py`**

创建：

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidancePrompt:
    name: str
    title: str
    description: str
    text: str


_CORE_BOUNDARY = """Computer Use MCP controls the real Windows desktop.

Visual GUI tasks require a multimodal model or a client that can open local PNG screenshots returned by the screenshot tool. A text-only model must not attempt screenshot-based clicking; it may use structured UIA, task, trace, and audit tools.

Do not bypass MCP safety with ad-hoc pyautogui scripts or private implementation imports.
"""

_STANDARD_LOOP = """Operate with this loop:
1. Use start_task(goal=...) for auditable user tasks.
2. Observe before acting with screenshot, get_ui_snapshot, find_control, wait_for_window, or wait_for_control.
3. Prefer UIA/semantic targeting over raw coordinates.
4. Use coordinates only after confirming screenshot pixels and monitor bounds.
5. Use batch for short mechanical sequences.
6. Verify after each meaningful state change.
7. Use review_task_session(task_id) and finish_task(task_id, summary=...) when done.
"""

_SAFETY = """Safety rules:
- Treat mouse and keyboard tools as real user input.
- Stop and re-observe after safety_block, fail_safe, timeout, ui_not_found, or invalid_tool.
- Use returned trace_path, artifact_root, artifacts, task_id, and review tools as the source of truth.
- Do not infer task state by scanning ~/.computer-use/traces.
"""

PROMPTS: tuple[GuidancePrompt, ...] = (
    GuidancePrompt(
        name="computer_use_guidance",
        title="Computer Use MCP operating guidance",
        description="Full guidance for safely operating Windows GUI applications through Computer Use MCP.",
        text=f"{_CORE_BOUNDARY}\n{_STANDARD_LOOP}\n{_SAFETY}",
    ),
    GuidancePrompt(
        name="computer_use_visual_task",
        title="Computer Use visual GUI task loop",
        description="Use for multimodal agents performing screenshot-based Windows GUI tasks.",
        text=f"{_CORE_BOUNDARY}\n{_STANDARD_LOOP}",
    ),
    GuidancePrompt(
        name="computer_use_text_only_limits",
        title="Computer Use text-only model limits",
        description="Use when the current model cannot inspect screenshots.",
        text=(
            "If you are a text-only model, do not attempt screenshot-based clicking. "
            "Use get_monitors, get_ui_snapshot, find_control, wait_for_window, wait_for_control, "
            "start_task, finish_task, review_task, list_tasks, get_task, and review_task_session. "
            "Ask for a multimodal model when a task requires visual layout, icons, colors, "
            "or coordinate selection from a screenshot."
        ),
    ),
    GuidancePrompt(
        name="computer_use_safety_checklist",
        title="Computer Use safety checklist",
        description="Checklist before sending real mouse or keyboard input.",
        text=_SAFETY,
    ),
)

MODEL_CAPABILITY_WARNING: str = (
    "Visual GUI tasks require a multimodal model or a client that can read local PNG screenshots."
)

DOCTOR_NEXT_STEPS: tuple[str, ...] = (
    "Run: python -m computer_use monitors",
    "Register the MCP server in your client",
    "Load MCP prompt computer_use_guidance when supported",
    "Run a read-only smoke test before sending mouse or keyboard input",
)


def list_prompt_metadata() -> list[dict[str, str]]:
    return [
        {
            "name": prompt.name,
            "title": prompt.title,
            "description": prompt.description,
        }
        for prompt in PROMPTS
    ]


def prompt_text(name: str) -> str:
    for prompt in PROMPTS:
        if prompt.name == name:
            return prompt.text
    raise KeyError(name)
```

- [x] **Step 4: 运行测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: PASS。

- [x] **Step 5: 提交**

```powershell
git add computer_use/guidance.py tests/test_mcp_prompts.py
git commit -m "feat: add computer-use agent guidance registry"
```

---

### Task 2: 将 guidance 暴露为 MCP prompts

**Files:**
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_prompts.py`

- [x] **Step 0: 审计 MCP SDK 版本约束**

读取 `pyproject.toml` 的 `dependencies` 行，确认 `mcp` 的最低版本声明是否满足 `>=1.0.0`（或实际支持 `list_prompts` / `get_prompt` 的最低版本）。本任务以 `pyproject.toml` 中的依赖声明为准：若声明已满足要求，则无需修改依赖；若声明低于要求，先将依赖升级到 `mcp>=1.0.0` 再继续。不在运行时做 prompts 支持的兼容性回退。

- [x] **Step 1: 写 RED 测试**

在 `tests/test_mcp_prompts.py` 追加：

```python
def test_mcp_prompt_objects_are_registered() -> None:
    from computer_use import mcp_server

    names = {prompt.name for prompt in mcp_server.PROMPTS}

    assert "computer_use_guidance" in names
    prompt = next(item for item in mcp_server.PROMPTS if item.name == "computer_use_guidance")
    assert "Windows GUI" in prompt.description


def test_get_prompt_result_contains_text_message() -> None:
    from computer_use import mcp_server

    result = mcp_server._get_prompt("computer_use_guidance")

    assert result.description
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert "Computer Use MCP" in result.messages[0].content.text
```

- [x] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: FAIL，`mcp_server.PROMPTS` / `_get_prompt` 尚不存在。

- [x] **Step 3: 实现 MCP prompt 对象与 helper**

在 `computer_use/mcp_server.py` 中导入：

```python
from mcp.types import GetPromptResult, Prompt, PromptMessage, TextContent
from computer_use import guidance
```

增加：

```python
PROMPTS: list[Prompt] = [
    Prompt(
        name=item["name"],
        description=item["description"],
        arguments=[],
    )
    for item in guidance.list_prompt_metadata()
]


def _get_prompt(name: str) -> GetPromptResult:
    try:
        text = guidance.prompt_text(name)
    except KeyError as exc:
        raise ValueError(f"Unknown prompt: {name}") from exc
    metadata = next(item for item in guidance.list_prompt_metadata() if item["name"] == name)
    return GetPromptResult(
        description=metadata["description"],
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=text),
            )
        ],
    )
```

未知 prompt 在 `guidance.prompt_text(name)` 处抛出 `KeyError`，`_get_prompt` 显式捕获后转译为 `ValueError(f"Unknown prompt: {name}")`；`get_prompt` handler 直接调用 `_get_prompt` 即可。

- [x] **Step 4: 在 `serve()` 注册 MCP prompt handlers**

在 `serve()` 内 `list_tools` / `call_tool` 旁直接注册 prompts。由于 Step 0 已确认 `pyproject.toml` 要求 `mcp>=1.0.0`，此处不捕获 `AttributeError` 做静默回退；若装饰器不存在，说明依赖未按声明安装，应让启动失败以暴露环境错误。

```python
    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return PROMPTS

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
        del arguments
        return _get_prompt(name)
```

- [x] **Step 5: 运行 prompt 测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: PASS。

- [x] **Step 6: 提交**

```powershell
git add computer_use/mcp_server.py tests/test_mcp_prompts.py
git commit -m "feat: expose computer-use guidance as mcp prompts"
```

---

### Task 3: 强化工具描述与错误 next action

**Files:**
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [x] **Step 0: 前置审计：确认代码库实际命名**

在写测试或改实现前，先读取以下文件并记录实际命名；若发现计划中的工具名/函数名与代码不一致，用实际名称替换 Step 1–Step 5 与 Task 6 中的对应名称。

- `computer_use/mcp_server.py`：
  - 工具表 `TOOLS` 中的工具名。
  - 内部函数名。
  - monkeypatch 目标实际存在且可被替换：`server.click`、`server.check_target_window`。
  - `_call_tool` 返回结构：Python dict 还是 JSON 字符串；错误结果中 `error` 字段是 kind 字符串还是人类可读消息；是否存在 `error_kind` 字段。
- `computer_use/composite.py`：composite 工具名及其返回 `{"error": "ui_not_found"}` 的结构。
- `computer_use/runner.py`：`run_task_plan` 调用的内部函数名。

审计后应形成一份实际名称清单，再进入 Step 1。

- [x] **Step 1: 写工具描述漂移守卫**

在 `tests/test_mcp_server.py` 追加：

```python
def test_distribution_critical_tool_descriptions_include_usage_guidance() -> None:
    by_name = {tool.name: tool for tool in TOOLS}

    assert "multimodal" in by_name["screenshot"].description.lower()
    assert "text-only" in by_name["screenshot"].description.lower()
    assert "real" in by_name["click"].description.lower()
    assert "observe" in by_name["batch"].description.lower()
    assert "task_id" in by_name["start_task"].description
    assert "source of truth" in by_name["review_task_session"].description.lower()
```

- [x] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "distribution_critical_tool_descriptions" -v
```

Expected: FAIL，现有描述还没有覆盖所有关键词。

- [x] **Step 3: 审计并修改关键工具 description**

先审计 `tests/test_mcp_server.py`：搜索对 `tool.description` 的精确全文断言（如 `assert tool.description == "..."`）。若存在，先改为关键字/子串断言（如 `assert "multimodal" in tool.description.lower()`），避免修改 description 后既有测试失败。当前测试仅做 schema/枚举/关键字检查，未发现精确 description 全文断言；审计通过后可继续修改 description。

只修改公开分发关键工具，不重写全量工具表：

- `screenshot`：加入 “Requires a multimodal model or client image reader; text-only models cannot interpret the PNG path.”
- `click`、`move_to`、`type`、`key_combo`、`press_key`、`mouse_down`、`mouse_up`、`drag`、`key_down`、`key_up`、`scroll`：加入 “This sends real Windows input; observe and verify first.”
- `batch`：加入 “Use after observing the UI; do not use for blind clicking.”
- `start_task`：加入 “Use the returned task_id on subsequent calls for auditability.”
- `review_task_session`：加入 “Use returned task evidence as the source of truth.”

- [x] **Step 4: 给常见错误响应补 next_action**

在不改变 error_kind 的前提下，给以下错误结果追加 `next_action`。

注入点映射：

- `invalid_tool`：在 `mcp_server.py` 的 `_batch_tool` 中，当内层 `tool` 名称不在 `allowed_tools` 时构造错误结果；保持 `error_kind="invalid_tool"` 和 `error` 字段不变，仅新增 `next_action`。
- `ui_not_found`：当前真正返回 `{"error": "ui_not_found"}` 的是 composite tools：`click_by_text`、`open_menu`、`fill_form`、`scroll_until`。在 `_dispatch_tool` 中这些工具调用返回后，若 `result.get("error") == "ui_not_found"`，注入 `next_action` 再 `json.dumps`；保持 `error_kind="ui_not_found"` 和 `error` 字段不变。
  - 注意：`mcp_server.py` 的 `_dispatch_pointer_tool` 控制未找到分支返回的是普通错误消息，被 `_failure_for_result` 映射为 `error_kind="unknown"`，不是 `ui_not_found` 的来源，不要在该处注入。
  - 可选统一做法：在 `_failure_for_result` 中，当 `error_kind="unknown"` 且原错误消息包含 "not found" / "Control" 时，一并注入 `next_action`，但计划以 composite tools 处直接注入为主。
- `fail_safe`：在 `mcp_server.py` 的 `_call_tool` 捕获 `FailSafeException` 的异常处理分支中，构造错误结果时注入；保持 `error_kind="fail_safe"` 和 `error` 字段不变。
- coordinate / safety block：在 `mcp_server.py` 的 `_call_tool` 中，为 `SafetyError` 以及**坐标/边界相关**的 `ValueError`（如坐标越界、`Point` 转换失败）构造错误结果时注入 `next_action`；其他非坐标类 `ValueError`（如 duration、batch step budget 等参数校验）不应注入该 `next_action`。保持原有 `error_kind` 和 `error` 字段不变。

文案：

- `ui_not_found`：`"Call get_ui_snapshot or screenshot, then retry with a better target."`
- `invalid_tool`：`"Use one of allowed_tools; do not include MCP namespace prefixes in nested batch/run_task_plan steps."`
- `fail_safe`：`"Confirm cursor/remote-control state, then re-observe before sending input."`
- coordinate / safety block：`"Call get_monitors and inspect_point before retrying."`

若当前错误由异常字符串构造，优先保持原 error 字段不变，只增加结构化建议字段。

- [x] **Step 5: 写 next_action 测试**

```python
import json

import pyautogui

import computer_use.mcp_server as server


def test_invalid_tool_error_includes_next_action() -> None:
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


def test_ui_not_found_error_includes_next_action() -> None:
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
    def _raise_fail_safe(*args, **kwargs):
        raise pyautogui.FailSafeException("fail-safe triggered")

    monkeypatch.setattr(server, "click", _raise_fail_safe)

    data = json.loads(server._call_tool("click", {"x": 100, "y": 100}))

    error_value = data.get("error_kind") or data.get("error", "")
    assert "fail_safe" in error_value
    assert "next_action" in data


def test_coordinate_safety_block_error_includes_next_action(monkeypatch) -> None:
    from computer_use import safety

    def _raise_safety(*args, **kwargs):
        raise safety.SafetyError("mocked safety block")

    monkeypatch.setattr(server, "check_target_window", _raise_safety)

    data = json.loads(server._call_tool("click", {"x": 100, "y": 100}))

    error_value = data.get("error_kind") or data.get("error", "")
    assert "safety" in error_value.lower() or "mocked safety block" in error_value
    assert "next_action" in data
    assert "get_monitors" in data["next_action"] or "inspect_point" in data["next_action"]


def test_coordinate_value_error_includes_next_action(monkeypatch) -> None:
    def _raise_coordinate_value_error(*args, **kwargs):
        raise ValueError("coordinates out of monitor bounds")

    monkeypatch.setattr(server, "click", _raise_coordinate_value_error)

    data = json.loads(server._call_tool("click", {"x": 100, "y": 100}))

    assert "coordinates" in data["error"].lower() or "bounds" in data["error"].lower()
    assert "next_action" in data
    assert "get_monitors" in data["next_action"] or "inspect_point" in data["next_action"]
```

- [x] **Step 6: 运行聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "distribution_critical_tool_descriptions or next_action or invalid_tool or ui_not_found or fail_safe or safety_block" -v
```

Expected: PASS。

- [x] **Step 7: 提交**

```powershell
git add computer_use/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: make tool guidance actionable for distributed clients"
```

---

### Task 4: 增加 `doctor` 安装自检

**Files:**
- Create: `computer_use/doctor.py`
- Modify: `computer_use/cli.py`
- Test: `tests/test_cli.py`

- [x] **Step 0: 审计 `computer_use/cli.py` 顶层导入**

读取 `computer_use/cli.py`，检查是否存在模块级导入：

- `import pyautogui`
- `import computer_use.core`
- `from computer_use import core`
- `from computer_use.core import ...`
- 任何直接触发 `pyautogui` / `core` 初始化的顶层代码

若存在，在 `main()` 内按命令分支延迟导入：

```python
if args.cmd in ("click", "move", "scroll", "type", "key", "screenshot", "size", "monitors"):
    # 仅在这些分支才导入 core / ui_automation / pyautogui
    from computer_use import core
    from computer_use.ui_automation import inspect_point
    import pyautogui
```

记录审计结论（如发现的具体导入行号）供 reviewer 复查；确认无顶层导入后再进入下一步。

- [x] **Step 1: 写 RED 测试**

在 `tests/test_cli.py` 追加：

```python
import subprocess
import sys



def test_doctor_module_import_does_not_load_pyautogui_or_core() -> None:
    """Verify that importing computer_use.doctor in a fresh process does not load pyautogui or computer_use.core."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import computer_use.doctor; "
            "import sys; "
            "print('pyautogui' in sys.modules, 'computer_use.core' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False False", result.stdout + result.stderr


def test_cli_doctor_outputs_json_without_input_device_import(
    tmp_path, monkeypatch, capsys
) -> None:
    sys.modules.pop("pyautogui", None)
    sys.modules.pop("computer_use.core", None)

    from computer_use import cli
    from computer_use import doctor

    monkeypatch.setattr(
        doctor,
        "run_doctor",
        lambda: {
            "status": "ok",
            "checks": [
                {"name": "python", "status": "ok"},
                {"name": "model_capability", "status": "warning"},
            ],
            "next_steps": ["Register the MCP server", "Load computer_use_guidance"],
        },
    )

    exit_code = cli.main(["doctor"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "ok"
    assert "pyautogui" not in sys.modules
    assert "computer_use.core" not in sys.modules
```

- [x] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -k doctor -v
```

Expected: FAIL，`doctor` 命令尚不存在。

- [x] **Step 3: 实现 `computer_use/doctor.py`**

实现环境和配置自检。为验证目录可写性，会执行一次**良性写探测**（`path.mkdir(parents=True, exist_ok=True)`），不发送鼠标或键盘输入，也不写入任何用户数据：

```python
from __future__ import annotations

import importlib.util
import platform
from pathlib import Path
from typing import Any

from computer_use import guidance
from computer_use.config import load_config


def _check(name: str, ok: bool, detail: str, *, warning: bool = False) -> dict[str, str]:
    if ok:
        status = "ok"
    elif warning:
        status = "warning"
    else:
        status = "failed"
    return {"name": name, "status": status, "detail": detail}


def run_doctor() -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    checks.append(_check("platform", platform.system() == "Windows", platform.platform()))
    checks.append(_check("mss", importlib.util.find_spec("mss") is not None, "mss importable"))
    checks.append(_check("Pillow", importlib.util.find_spec("PIL") is not None, "Pillow importable"))
    checks.append(_check("pyautogui", importlib.util.find_spec("pyautogui") is not None, "pyautogui importable"))
    checks.append(_check("uiautomation", importlib.util.find_spec("uiautomation") is not None, "uiautomation importable", warning=True))

    try:
        config = load_config()
    except Exception as exc:
        checks.append(_check("config_load", False, str(exc)))
        return {
            "status": "failed",
            "checks": checks,
            "next_steps": list(guidance.DOCTOR_NEXT_STEPS),
        }

    for key in ("log_dir", "screenshot_dir", "trace_dir", "task_dir"):
        path_value = getattr(config, key, None)
        if path_value is None and isinstance(config, dict):
            path_value = config.get(key)
        if path_value is None:
            checks.append(_check(key, False, f"config missing key: {key}"))
            continue
        path = Path(path_value)
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = path.is_dir()
        except Exception as exc:
            checks.append(_check(key, False, str(exc)))
        else:
            checks.append(_check(key, writable, str(path)))

    checks.append(
        {
            "name": "model_capability",
            "status": "warning",
            "detail": guidance.MODEL_CAPABILITY_WARNING,
        }
    )

    status = "failed" if any(item["status"] == "failed" for item in checks) else "ok"
    return {
        "status": status,
        "checks": checks,
        "next_steps": list(guidance.DOCTOR_NEXT_STEPS),
    }
```

实现要点：

- 不要在模块级导入 `computer_use.core` 或 `pyautogui`。
- 使用 `getattr(config, key, None)` 与 `config.get(key)` 的防御式访问，兼容 dict 与 dataclass/object；键缺失时记录 failed check 而非抛出异常。
- `guidance.MODEL_CAPABILITY_WARNING` 和 `guidance.DOCTOR_NEXT_STEPS` 来自单一事实源，避免 doctor 与 prompts/docs 漂移。

- [x] **Step 4: 在 CLI 增加 `doctor` 命令**

在 `main()` 的 argparse 初始化处增加：

```python
sub.add_parser("doctor", help="Run installation diagnostics and benign write probe as JSON")
```

在进入 `cs = get_coordinate_system()` 前处理：

```python
    if args.cmd == "doctor":
        from computer_use import doctor

        result = doctor.run_doctor()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] != "failed" else 1
```

- [x] **Step 5: 运行 CLI 测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: PASS。

- [x] **Step 6: 提交**

```powershell
git add computer_use/doctor.py computer_use/cli.py tests/test_cli.py
git commit -m "feat: add installation doctor with benign write probe"
```

---

### Task 5: 提供分发示例和开箱流程文档

**Files:**
- Create: `examples/clients/generic-mcp.json`
- Create: `examples/clients/kimi-code.toml`
- Create: `examples/clients/agent-prompt.md`
- Modify: `README.md`
- Modify: `docs/agent-usage.md`
- Modify: `docs/deployment.md`
- Modify: `docs/api.md`
- Modify: `docs/pitfalls.md`
- Modify: `STRUCTURE.md`

- [x] **Step 1: 创建客户端示例模板**

以下文件为模板，不是可直接使用的配置。用户必须将 `<ABSOLUTE_PATH_TO_PROJECT>` 替换为自己克隆仓库的绝对路径。

`examples/clients/generic-mcp.json`：

```json
{
  "mcpServers": {
    "computer-use": {
      "command": "<ABSOLUTE_PATH_TO_PROJECT>\\.venv\\Scripts\\python.exe",
      "args": ["-m", "computer_use.mcp_server"]
    }
  }
}
```

`examples/clients/kimi-code.toml`：

```toml
[mcp.servers.computer-use]
command = '<ABSOLUTE_PATH_TO_PROJECT>\.venv\Scripts\python.exe'
args = ["-m", "computer_use.mcp_server"]
```

> 使用 TOML 单引号字面字符串（literal string）包裹路径，反斜杠会被原样保留，不需要写成 `\\`。

`examples/clients/agent-prompt.md`：

```markdown
# Computer Use MCP Agent Prompt

Load the MCP prompt `computer_use_guidance` if your client supports MCP prompts.
If not, use the guidance below.

Visual GUI tasks require a multimodal model or client-side local PNG reading. Text-only models must not perform screenshot-based clicking.

Operate with: observe -> semantic/UIA targeting -> action -> verify -> trace/task review.
Do not bypass MCP safety with pyautogui scripts.
```

- [x] **Step 2: README 改造为安装后路径**

在 README 中新增或替换为 **英文节标题 `## First run`**（允许在中文文档中保留英文标题，或在 `## First run` 后加括号中文说明）。该节必须包含以下关键短语（可直接使用英文）：

- `python -m computer_use doctor`
- `Register the MCP server`
- `computer_use_guidance`
- `skills/computer-use/SKILL.md`
- `get_monitors`
- `get_ui_snapshot`
- `review_task_session`
- `Generic MCP client` 或 `Generic MCP`
- `Kimi Code`

目标文本示例：

```markdown
## First run

1. Run `python -m computer_use doctor`.
2. Register the MCP server in your client.
   - Generic MCP client: see `examples/clients/generic-mcp.json`.
   - Kimi Code: see `examples/clients/kimi-code.toml`.
3. If your client supports MCP prompts, load `computer_use_guidance`.
4. If your client supports Skills, load `skills/computer-use/SKILL.md`.
5. Run read-only smoke tools first: `get_monitors`, `get_ui_snapshot`, `review_task_session` on an explicit task.
6. Only then perform real mouse/keyboard tasks.
```

若原 README 存在 `## Register with an MCP Client` 或 `## Agent guidance` 等旧节，可将其内容合并到 `## First run` 或在其后保留为子说明，但首屏流程必须以 `## First run` 呈现。

- [x] **Step 3: 更新 API / deployment / pitfalls**

`docs/api.md`：

- 新增 “MCP prompts” 小节，列出四个 prompt 名称和用途。
- 说明 prompts 是分发层指导，不替代工具 schema 和安全检查。

`docs/deployment.md`：

- 增加 `doctor` 命令。
- 增加 “安装后 smoke test”。
- 明确纯文本模型不得执行视觉 GUI 任务。

`docs/pitfalls.md`：

- 增加 “安装 MCP 不等于模型具备看图能力”。
- 增加 “客户端不支持 prompts/Skill 时必须复制 `docs/agent-usage.md` 或 `examples/clients/agent-prompt.md`”。

`docs/agent-usage.md`：

- 顶部说明优先级：MCP prompts > Skill > 复制 prompt。
- 保持与 `computer_use.guidance` 的核心循环一致。

`docs/overview.md`：

- Modify: docs/overview.md — 记录 guidance 单一事实源、MCP prompts、doctor 派生关系。

`STRUCTURE.md`：

- 增加 `docs/agent-usage.md` 和 `examples/clients/` 入口。

- [x] **Step 4: 文档检查**

```powershell
python scripts\audit.py check
python scripts\agent_links.py check
```

Expected: PASS。

- [x] **Step 5: 提交**

```powershell
git add README.md docs examples STRUCTURE.md
git commit -m "docs: document out-of-box client onboarding"
```

---

### Task 6: 增加只读 MCP smoke test

**Files:**
- Create: `tools/smoke_mcp_client.py`
- Modify: `docs/deployment.md`
- Test: `tests/test_smoke_script.py`

- [x] **Step 1: 创建 smoke 脚本**

`tools/smoke_mcp_client.py` 目标：不发送鼠标键盘输入，只验证 MCP server 能启动、列 tools、列 prompts，并可调用只读工具 `get_monitors`（名称经 Task 3 Step 0 审计确认）。

命令行接口（argparse）：

```python
import argparse
import json
import subprocess
import sys
import time
from typing import Any


TIMEOUT_SECONDS = 30


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only MCP smoke test client.")
    parser.add_argument(
        "--server",
        default=sys.executable,
        help="Path to the Python interpreter used to launch the MCP server (default: sys.executable).",
    )
    parser.add_argument(
        "--args",
        nargs="*",
        default=["-m", "computer_use.mcp_server"],
        help="Arguments passed to --server to start the MCP server (default: -m computer_use.mcp_server).",
    )
    return parser
```

核心实现骨架：

```python
def _send(proc: subprocess.Popen, msg: dict[str, Any]) -> None:
    line = json.dumps(msg, ensure_ascii=False)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, expected_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        try:
            line = proc.stdout.readline()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"failed to read stdout: {exc}")
        if not line:
            time.sleep(0.05)
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON from server: {line!r}") from exc
        if msg.get("id") == expected_id:
            if "error" in msg:
                raise RuntimeError(f"server error: {msg['error']}")
            return msg.get("result", {})
    raise TimeoutError(f"did not receive response for id={expected_id} within {TIMEOUT_SECONDS}s")


def run(server: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.Popen(
        [server, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        _send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "computer-use-smoke", "version": "0.1.0"},
            },
        })
        init_result = _read_response(proc, 1)

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_result = _read_response(proc, 2)

        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "prompts/list"})
        prompts_result = _read_response(proc, 3)

        _send(proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "get_monitors", "arguments": {}},
        })
        monitors_result = _read_response(proc, 4)

        return {
            "status": "ok",
            "tools": tools_result.get("tools", []),
            "prompts": prompts_result.get("prompts", []),
            "monitors": monitors_result.get("content", []),
        }
    except Exception as exc:
        stderr = proc.stderr.read() if proc.stderr else ""
        return {"status": "failed", "error": str(exc), "stderr": stderr}
    finally:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:  # pragma: no cover
            pass


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run(args.server, args.args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

实现要点：

- 使用 `subprocess.Popen([server, *args], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)` 启动 server。
- 向 stdin 写入换行分隔的 JSON-RPC 消息：initialize、notifications/initialized、tools/list、prompts/list、tools/call(get_monitors)。
- 从 stdout 逐行读取，按 `id` 匹配响应。
- 超时 30 秒，超时或异常时 `proc.kill()`。
- 失败输出 `{"status": "failed", "error": ..., "stderr": ...}`；成功输出 `{"status": "ok", "tools": ..., "prompts": ..., "monitors": ...}`。
- 脚本不调用任何鼠标/键盘工具，只读验证。

- [x] **Step 2: 写脚本导入测试**

```python
def test_smoke_script_import_does_not_load_pyautogui() -> None:
    import importlib.util
    import sys
    from pathlib import Path

    sys.modules.pop("pyautogui", None)
    script_path = Path(__file__).resolve().parents[1] / "tools" / "smoke_mcp_client.py"
    spec = importlib.util.spec_from_file_location(
        "smoke_mcp_client",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert "pyautogui" not in sys.modules
```

- [x] **Step 3: 文档接入**

在 `docs/deployment.md` 增加：

```powershell
python tools\smoke_mcp_client.py --server .\.venv\Scripts\python.exe --args -m computer_use.mcp_server
```

说明 smoke test 不点击、不输入，只验证协议和只读工具。

- [x] **Step 4: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py tests/test_smoke_script.py -v
git add tools/smoke_mcp_client.py docs/deployment.md tests/test_smoke_script.py
git commit -m "test: add read-only mcp smoke check"
```

---

### Task 7: 增加分发质量验收测试

**Files:**
- Test: `tests/test_distribution_readiness.py`

- [x] **Step 1: 创建分发就绪测试**

`tests/test_distribution_readiness.py`：

```python
from __future__ import annotations

from pathlib import Path


def test_distribution_guidance_entrypoints_exist() -> None:
    required = [
        Path("README.md"),
        Path("docs/agent-usage.md"),
        Path("skills/computer-use/SKILL.md"),
        Path("examples/clients/agent-prompt.md"),
    ]

    for path in required:
        assert path.exists(), path


def test_docs_reference_mcp_prompt_name() -> None:
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            Path("README.md"),
            Path("docs/agent-usage.md"),
            Path("docs/deployment.md"),
        ]
    )

    assert "computer_use_guidance" in docs
    assert "multimodal" in docs.lower() or "多模态" in docs
    assert "doctor" in docs


def test_examples_do_not_hardcode_kimi_as_only_client() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Generic MCP" in readme or "Generic MCP client" in readme
    # README Step 2 rewrites post-registration flow as a "First run" section.
    # Accept English "First run", Chinese "快速开始", or "Get started" as the onboarding header.
    before_first_run = readme
    for header in ("First run", "快速开始", "Get started"):
        if header in readme:
            before_first_run = readme.split(header, 1)[0]
            break
    assert "Kimi" not in before_first_run
```

- [x] **Step 2: 运行并修复文档**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_distribution_readiness.py -v
```

Expected: PASS。

- [x] **Step 3: 提交**

```powershell
git add tests/test_distribution_readiness.py README.md docs examples
git commit -m "test: guard distribution guidance entrypoints"
```

---

### Task 8: 终验、归档和变更记录

**Files:**
- Modify: `CHANGELOG.md`
- Move after acceptance: `docs/plans/active/mcp-distribution-out-of-box-usage.md` to `docs/plans/completed/`
- Modify: `docs/CURRENT.md`

- [x] **Step 1: 全量自动化验证**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe -m compileall -q computer_use
python scripts\agent_links.py check
python scripts\audit.py check
git diff --check
```

Expected:

- pytest 全部通过；真实截图测试按既有环境变量规则 skip。
- compileall 通过。
- agent links 和 audit 通过。
- diff check 无空白错误。

- [x] **Step 2: 手动只读 smoke**

```powershell
python -m computer_use doctor
python -m computer_use monitors
```

Expected:

- `doctor` 输出 JSON。
- 若环境可用，`status=ok`；如 UIA 可选依赖不可用，可为 warning。
- 命令不移动鼠标、不点击、不输入。

- [x] **Step 3: MCP prompt 验收**

用 MCP Inspector 或当前测试 helper 验证：

- `prompts/list` 返回四个 prompt。
- `prompts/get computer_use_guidance` 返回包含多模态要求、text-only 限制、标准执行闭环和安全规则的文本。
- `tools/list` 的 `screenshot`、`click`、`batch`、`start_task`、`review_task_session` 描述包含关键使用纪律。

- [x] **Step 4: CHANGELOG**

```powershell
python scripts\changelog.py add --title "feat: 提升 MCP 分发开箱可用性" --body "新增 MCP prompts、安装 doctor、只读 smoke、通用客户端示例和分发就绪测试，让用户注册 MCP 后可直接发现正确使用路径；强化工具描述和错误 next_action，降低纯文本模型误用与盲点操作风险。"
```

- [x] **Step 5: 独立审计**

Reviewer 检查：

- 不支持 Skill 的客户端仍能通过 MCP prompts 或 docs prompt 获得指导。
- 纯文本模型限制在 prompts、README、deployment、agent usage 和 doctor 中均可见。
- `doctor` 与 smoke test 不导入或触发真实输入设备。
- 工具错误响应包含可执行 next action，不改变既有 error_kind。
- 没有放宽任何安全边界。

- [x] **Step 6: 归档计划**

Reviewer 通过后：

```powershell
Move-Item docs\plans\active\mcp-distribution-out-of-box-usage.md docs\plans\completed\
```

更新 `docs/CURRENT.md` 为无进行中任务。

---

## 验收标准

- 用户安装并注册 MCP 后，支持 MCP prompts 的客户端能发现 `computer_use_guidance`。
- 不支持 prompts 的客户端能在 README 首屏流程中看到 `docs/agent-usage.md` / `examples/clients/agent-prompt.md`。
- 支持 Skill 的客户端能继续加载 `skills/computer-use/SKILL.md`。
- `python -m computer_use doctor` 始终输出 JSON（包括 `load_config()` 异常时返回 `{"status": "failed", ...}`），不触发鼠标键盘输入；会执行良性目录可写探测。
- 文档默认流程包含 `doctor`、只读 smoke、模型能力要求和真实输入风险。
- `screenshot` 工具描述明确多模态/本地 PNG 能力要求。
- 输入类工具描述明确真实 Windows 输入和先观察后执行。
- `batch` 描述明确不能盲点，应用于已观察后的短动作序列。
- 常见失败结果包含 `next_action`，指导 agent 下一步重新观察或改用 allowed tools。
- 完整测试、compileall、audit、agent links、diff check 通过。

## 风险与取舍

- MCP prompts 并非所有客户端支持，因此不能替代 README、Skill 和通用 prompt。
- `doctor` 无法自动判断远端模型是否真正多模态，只能显式警告并给 smoke 路径。
- 强化 tool description 会增加 `tools/list` 上下文长度，需只改关键工具，避免全量冗长。
- smoke test 若使用 MCP client SDK 可能受 SDK 版本影响；先保证只读、可手动运行，再逐步增强自动化覆盖。
- 单一 guidance 源可减少漂移，但 Skill 和 docs 的自然语言仍需人工维护；用分发就绪测试守住关键短语和入口。

## 执行建议

优先顺序：

1. Task 1-2：先把 MCP prompts 打通，这是“安装 MCP 即可发现指导”的核心。
2. Task 4：再加 `doctor`，让用户知道环境是否可用。
3. Task 3/5/7：强化分发文案、错误 next action 和防漂移测试。
4. Task 6：最后补 MCP smoke，避免被 SDK 细节拖慢主线。
