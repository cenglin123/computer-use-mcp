# MCP Distribution Out-of-Box Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户安装并注册 Computer Use MCP 后，即使不了解本项目，也能通过 MCP 内置 prompts、工具契约、doctor、自检示例和文档入口获得正确使用路径，降低纯文本模型误用、盲点坐标、绕过安全层和 trace 误报的概率。

**Architecture:** 建立一份 `computer_use.guidance` 作为 agent 使用纪律的单一事实源，再向 MCP prompts、Skill、通用文档和 doctor 输出派生。MCP server 在 `tools/list` 之外注册 `prompts/list` 与 `prompts/get`，让支持 MCP prompts 的客户端安装后即可发现使用指南；不支持 prompts 的客户端仍可通过 README、`docs/agent-usage.md` 和 `skills/computer-use/SKILL.md` 获取同等指导。CLI 增加只读 `doctor`，安装后先验证环境、配置、显示器、可写目录、截图能力和模型能力提示，再进入真实 GUI 输入任务。

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
- CLI `doctor`：只读环境和配置自检。
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
  - 只读安装自检，不执行鼠标键盘输入。
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
- Create: `examples/clients/generic-mcp.json`
  - 通用 MCP 客户端配置示例。
- Create: `examples/clients/kimi-code.toml`
  - Kimi Code 配置示例。
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

- [ ] **Step 1: 写 RED 测试**

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

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: FAIL，`computer_use.guidance` 尚不存在。

- [ ] **Step 3: 实现 `computer_use/guidance.py`**

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
            "Use get_monitors, get_ui_snapshot, find_control, review_task, list_tasks, "
            "get_task, and review_task_session only. Ask for a multimodal model when a task "
            "requires visual layout, icons, colors, or coordinate selection from a screenshot."
        ),
    ),
    GuidancePrompt(
        name="computer_use_safety_checklist",
        title="Computer Use safety checklist",
        description="Checklist before sending real mouse or keyboard input.",
        text=_SAFETY,
    ),
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

- [ ] **Step 4: 运行测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add computer_use/guidance.py tests/test_mcp_prompts.py
git commit -m "feat: add computer-use agent guidance registry"
```

---

### Task 2: 将 guidance 暴露为 MCP prompts

**Files:**
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_prompts.py`

- [ ] **Step 1: 写 RED 测试**

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

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: FAIL，`mcp_server.PROMPTS` / `_get_prompt` 尚不存在。

- [ ] **Step 3: 实现 MCP prompt 对象与 helper**

在 `computer_use/mcp_server.py` 中导入：

```python
from mcp.types import GetPromptResult, Prompt, PromptMessage
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
    text = guidance.prompt_text(name)
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

如果未知 prompt，捕获 `KeyError` 并抛 `ValueError(f"Unknown prompt: {name}")`。

- [ ] **Step 4: 在 `serve()` 注册 MCP prompt handlers**

在 `serve()` 内 `list_tools` / `call_tool` 旁增加：

```python
    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return PROMPTS

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
        del arguments
        return _get_prompt(name)
```

- [ ] **Step 5: 运行 prompt 测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_prompts.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/mcp_server.py tests/test_mcp_prompts.py
git commit -m "feat: expose computer-use guidance as mcp prompts"
```

---

### Task 3: 强化工具描述与错误 next action

**Files:**
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 写工具描述漂移守卫**

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

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "distribution_critical_tool_descriptions" -v
```

Expected: FAIL，现有描述还没有覆盖所有关键词。

- [ ] **Step 3: 修改关键工具 description**

只修改公开分发关键工具，不重写全量工具表：

- `screenshot`：加入 “Requires a multimodal model or client image reader; text-only models cannot interpret the PNG path.”
- `click` / `move_to` / `type` / `key_combo` / `press_key`：加入 “This sends real Windows input; observe and verify first.”
- `batch`：加入 “Use after observing the UI; do not use for blind clicking.”
- `start_task`：加入 “Use the returned task_id on subsequent calls for auditability.”
- `review_task_session`：加入 “Use returned task evidence as the source of truth.”

- [ ] **Step 4: 给常见错误响应补 next_action**

在不改变 error_kind 的前提下，给以下错误结果追加 `next_action`：

- `ui_not_found`：`"Call get_ui_snapshot or screenshot, then retry with a better target."`
- `invalid_tool`：`"Use one of allowed_tools; do not include MCP namespace prefixes in nested batch/run_task_plan steps."`
- `fail_safe`：`"Confirm cursor/remote-control state, then re-observe before sending input."`
- coordinate / safety block：`"Call get_monitors and inspect_point before retrying."`

若当前错误由异常字符串构造，优先保持原 error 字段不变，只增加结构化建议字段。

- [ ] **Step 5: 写 next_action 测试**

```python
def test_invalid_tool_error_includes_next_action() -> None:
    import computer_use.mcp_server as server

    data = json.loads(
        server._call_tool(
            "batch",
            {"actions": [{"tool": "bad_tool", "args": {}}]},
        )
    )

    failure = data["results"][0]["result"]
    assert failure["error"] == "invalid_tool"
    assert "next_action" in failure
    assert "allowed_tools" in failure["next_action"]
```

- [ ] **Step 6: 运行聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "distribution_critical_tool_descriptions or next_action or invalid_tool" -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```powershell
git add computer_use/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: make tool guidance actionable for distributed clients"
```

---

### Task 4: 增加只读 `doctor` 安装自检

**Files:**
- Create: `computer_use/doctor.py`
- Modify: `computer_use/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 写 RED 测试**

在 `tests/test_cli.py` 追加：

```python
def test_cli_doctor_outputs_read_only_json_without_input_device_import(
    tmp_path, monkeypatch, capsys
) -> None:
    sys.modules.pop("pyautogui", None)
    sys.modules.pop("computer_use.core", None)

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

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -k doctor -v
```

Expected: FAIL，`doctor` 命令尚不存在。

- [ ] **Step 3: 实现 `computer_use/doctor.py`**

实现只读检查：

```python
from __future__ import annotations

import importlib.util
import platform
from pathlib import Path
from typing import Any

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
    checks.append(_check("uiautomation", importlib.util.find_spec("uiautomation") is not None, "uiautomation importable", warning=True))

    config = load_config()
    for key in ("log_dir", "screenshot_dir", "trace_dir", "task_dir"):
        path = Path(config[key])
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
            "detail": "Visual GUI tasks require a multimodal model or a client that can read local PNG screenshots.",
        }
    )

    status = "failed" if any(item["status"] == "failed" for item in checks) else "ok"
    return {
        "status": status,
        "checks": checks,
        "next_steps": [
            "Run: python -m computer_use monitors",
            "Register the MCP server in your client",
            "Load MCP prompt computer_use_guidance when supported",
            "Run a read-only smoke test before sending mouse or keyboard input",
        ],
    }
```

不要在模块级导入 `computer_use.core` 或 `pyautogui`。

- [ ] **Step 4: 在 CLI 增加 `doctor` 命令**

在 `main()` 的 argparse 初始化处增加：

```python
sub.add_parser("doctor", help="Run read-only installation diagnostics as JSON")
```

在进入 `cs = get_coordinate_system()` 前处理：

```python
    if args.cmd == "doctor":
        from computer_use import doctor

        result = doctor.run_doctor()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] != "failed" else 1
```

- [ ] **Step 5: 运行 CLI 测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/doctor.py computer_use/cli.py tests/test_cli.py
git commit -m "feat: add read-only installation doctor"
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

- [ ] **Step 1: 创建客户端示例**

`examples/clients/generic-mcp.json`：

```json
{
  "mcpServers": {
    "computer-use": {
      "command": "C:\\\\Project\\\\computer-use-mcp\\\\.venv\\\\Scripts\\\\python.exe",
      "args": ["-m", "computer_use.mcp_server"]
    }
  }
}
```

`examples/clients/kimi-code.toml`：

```toml
[mcp.servers.computer-use]
command = "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "computer_use.mcp_server"]
```

`examples/clients/agent-prompt.md`：

```markdown
# Computer Use MCP Agent Prompt

Load the MCP prompt `computer_use_guidance` if your client supports MCP prompts.
If not, use the guidance below.

Visual GUI tasks require a multimodal model or client-side local PNG reading. Text-only models must not perform screenshot-based clicking.

Operate with: observe -> semantic/UIA targeting -> action -> verify -> trace/task review.
Do not bypass MCP safety with pyautogui scripts.
```

- [ ] **Step 2: README 改造为安装后路径**

将 README 中注册后流程改成：

```markdown
## First run

1. Run `python -m computer_use doctor`.
2. Register the MCP server in your client.
3. If your client supports MCP prompts, load `computer_use_guidance`.
4. If your client supports Skills, load `skills/computer-use/SKILL.md`.
5. Run read-only smoke tools first: `get_monitors`, `get_ui_snapshot`, `review_task_session` on an explicit task.
6. Only then perform real mouse/keyboard tasks.
```

- [ ] **Step 3: 更新 API / deployment / pitfalls**

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

`STRUCTURE.md`：

- 增加 `docs/agent-usage.md` 和 `examples/clients/` 入口。

- [ ] **Step 4: 文档检查**

```powershell
python scripts\audit.py check
python scripts\agent_links.py check
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add README.md docs examples STRUCTURE.md
git commit -m "docs: document out-of-box client onboarding"
```

---

### Task 6: 增加只读 MCP smoke test

**Files:**
- Create: `tools/smoke_mcp_client.py`
- Modify: `docs/deployment.md`
- Test: `tests/test_cli.py` or new `tests/test_smoke_script.py`

- [ ] **Step 1: 创建 smoke 脚本**

`tools/smoke_mcp_client.py` 目标：不发送鼠标键盘输入，只验证 MCP server 能启动、列 tools、列 prompts，并可调用只读工具。

最小行为：

- 启动当前解释器：`python -m computer_use.mcp_server`
- 通过 MCP stdio 初始化。
- 调用 `tools/list`。
- 调用 `prompts/list`。
- 调用只读工具 `get_monitors`。
- 输出 JSON：`{"status": "ok", "tools": ..., "prompts": ...}`。

若 MCP SDK 的客户端 API 在当前版本不稳定，可先把脚本作为 `manual` 工具，仅在 docs 中声明；自动测试覆盖脚本可导入、参数解析和不会触发输入设备。

- [ ] **Step 2: 写脚本导入测试**

```python
def test_smoke_script_import_does_not_load_pyautogui() -> None:
    import importlib.util
    import sys
    from pathlib import Path

    sys.modules.pop("pyautogui", None)
    spec = importlib.util.spec_from_file_location(
        "smoke_mcp_client",
        Path("tools/smoke_mcp_client.py"),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert "pyautogui" not in sys.modules
```

- [ ] **Step 3: 文档接入**

在 `docs/deployment.md` 增加：

```powershell
python tools\smoke_mcp_client.py --server .\.venv\Scripts\python.exe --args -m computer_use.mcp_server
```

说明 smoke test 不点击、不输入，只验证协议和只读工具。

- [ ] **Step 4: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py tests/test_smoke_script.py -v
git add tools/smoke_mcp_client.py docs/deployment.md tests/test_smoke_script.py
git commit -m "test: add read-only mcp smoke check"
```

---

### Task 7: 增加分发质量验收测试

**Files:**
- Test: `tests/test_distribution_readiness.py`

- [ ] **Step 1: 创建分发就绪测试**

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
    assert "Kimi" not in readme.split("Register with an MCP Client", 1)[0]
```

- [ ] **Step 2: 运行并修复文档**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_distribution_readiness.py -v
```

Expected: PASS。

- [ ] **Step 3: 提交**

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

- [ ] **Step 1: 全量自动化验证**

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

- [ ] **Step 2: 手动只读 smoke**

```powershell
python -m computer_use doctor
python -m computer_use monitors
```

Expected:

- `doctor` 输出 JSON。
- 若环境可用，`status=ok`；如 UIA 可选依赖不可用，可为 warning。
- 命令不移动鼠标、不点击、不输入。

- [ ] **Step 3: MCP prompt 验收**

用 MCP Inspector 或当前测试 helper 验证：

- `prompts/list` 返回四个 prompt。
- `prompts/get computer_use_guidance` 返回包含多模态要求、text-only 限制、标准执行闭环和安全规则的文本。
- `tools/list` 的 `screenshot`、`click`、`batch`、`start_task`、`review_task_session` 描述包含关键使用纪律。

- [ ] **Step 4: CHANGELOG**

```powershell
python scripts\changelog.py add --title "feat: 提升 MCP 分发开箱可用性" --body "新增 MCP prompts、安装 doctor、只读 smoke、通用客户端示例和分发就绪测试，让用户注册 MCP 后可直接发现正确使用路径；强化工具描述和错误 next_action，降低纯文本模型误用与盲点操作风险。"
```

- [ ] **Step 5: 独立审计**

Reviewer 检查：

- 不支持 Skill 的客户端仍能通过 MCP prompts 或 docs prompt 获得指导。
- 纯文本模型限制在 prompts、README、deployment、agent usage 和 doctor 中均可见。
- `doctor` 与 smoke test 不导入或触发真实输入设备。
- 工具错误响应包含可执行 next action，不改变既有 error_kind。
- 没有放宽任何安全边界。

- [ ] **Step 6: 归档计划**

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
- `python -m computer_use doctor` 可运行，输出 JSON，只读，不触发鼠标键盘输入。
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
