# Post-Review 改进计划（2026-06-17）

> **For agentic workers:** 本计划按优先级分阶段实施。每个 Task 完成后应能独立提交并通过测试。

## 背景

外部评审对 `computer-use-mcp` 给出 B+/A- 综合评价，指出项目已在架构设计、安全分层、审计模型和 Agent 协作文档上具备优势，但在**真实 GUI 集成测试**、**首次使用体验**、**mcp_server 可维护性**和**混合 DPI 支持**等方面存在明显短板。

本计划将评审建议转化为可执行的改造任务，并明确已有能力（如 doctor UIA 检查、截图敏感窗口 redaction）不需要重复建设。

---

## 范围

**包含：**

- 真实 GUI 集成测试骨架与首批闭环测试。
- `allowed_commands` 首次使用体验优化。
- `mcp_server.py` 按职责拆分为更小模块。
- 文档补全：说明当前已实现的 redaction、UIA 检查、OCR 能力。

**不包含：**

- 混合 DPI 多显示器支持（技术风险高，需单独立项）。
- 替换 pyautogui 为更低层 Windows API（超出当前 sprint 范围）。
- 操作取消/超时机制（需要 Runner 架构改造，单独立项）。

---

## 文件结构与职责

- Modify: `tests/integration/test_notepad_smoke.py`
  - 首个真实 GUI 集成测试：启动 notepad → 截图 → UIA 定位编辑区 → 输入文本 → 验证窗口标题/截图内容。
- Modify: `tests/integration/conftest.py`
  - 集成测试 fixture：启动/清理应用、重试策略、主屏坐标校验。
- Modify: `computer_use/launcher.py`
  - 增强 `launch_app` 在白名单为空时的错误提示，并指向配置示例。
- Modify: `config.example.yaml`
  - 增加 `allowed_commands` 示例白名单。
- Create: `computer_use/tools/__init__.py`, `computer_use/tools/schemas.py`, `computer_use/tools/dispatch.py`, `computer_use/tools/batch.py`, `computer_use/tools/composite.py`
  - 拆分 `mcp_server.py` 的工具 schema、调用路由、batch、composite 逻辑。
- Modify: `computer_use/mcp_server.py`
  - 保留 server 生命周期和 prompt 注册，导入拆分后的模块。
- Modify: `docs/deployment.md`
  - 说明 doctor 已检查 UIA，截图 redaction 已支持敏感窗口。
- Modify: `docs/pitfalls.md`
  - 说明混合 DPI fail-fast 原因、allowed_commands 首次配置要求、OCR 作为可选能力。
- Modify: `docs/overview.md`
  - 补充测试策略分层（单元/集成/性能）。
- Modify: `README.md`
  - 增加集成测试运行说明和 allowed_commands 配置提示。
- Modify: `CHANGELOG.md`
  - 记录最终变更。

---

### Task 1: 真实 GUI 集成测试骨架

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_notepad_smoke.py`
- Modify: `README.md`
- Modify: `docs/overview.md`
- Test: `tests/integration/test_notepad_smoke.py`

- [ ] **Step 1: 写 RED 测试**

创建 `tests/integration/test_notepad_smoke.py`：

```python
from __future__ import annotations

import json

import pytest


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_notepad_type_and_verify(integration_app):
    from computer_use import mcp_server

    app = integration_app("notepad")
    try:
        # 1. 截图
        shot = json.loads(mcp_server._call_tool("screenshot", {"monitor": 1}))
        assert shot["saved_path"]

        # 2. UIA 找到记事本编辑区
        snap = json.loads(
            mcp_server._call_tool(
                "get_ui_snapshot",
                {"scope": "foreground", "include_screenshot": False},
            )
        )
        assert snap["root"]

        # 3. 输入文本
        result = json.loads(
            mcp_server._call_tool(
                "type",
                {"text": "computer-use integration test"},
            )
        )
        assert "error" not in result

        # 4. 再次截图验证文本出现
        shot2 = json.loads(mcp_server._call_tool("screenshot", {"monitor": 1}))
        assert shot2["saved_path"] != shot["saved_path"]
    finally:
        app.close()
```

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_notepad_smoke.py -v
```

Expected: FAIL，`tests/integration/` 尚不存在或 fixture 未定义。

- [ ] **Step 3: 实现集成测试 fixture**

创建 `tests/integration/conftest.py`：

```python
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Generator

import pytest


@dataclass
class ManagedApp:
    proc: subprocess.Popen
    name: str

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


@pytest.fixture
def integration_app() -> Generator[callable, None, None]:
    launched: list[ManagedApp] = []

    def _launch(name: str) -> ManagedApp:
        from computer_use import launcher

        result = json.loads(
            launcher.launch_app(name)
        )
        if "error" in result:
            pytest.skip(f"cannot launch {name}: {result['error']}")
        # 等待窗口出现
        time.sleep(1)
        app = ManagedApp(proc=subprocess.Popen(["cmd", "/c", "start", name], shell=True), name=name)
        launched.append(app)
        return app

    yield _launch

    for app in launched:
        app.close()
```

注意：fixture 需要处理 notepad 的真实启动。如果 `launch_app` 返回的是成功状态而非 subprocess，需要调整 fixture。

- [ ] **Step 4: 标记集成测试并配置跳过**

在 `pytest.ini` 中增加：

```ini
markers =
    integration: requires real Windows GUI environment
```

默认 CI 可跳过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -v
```

- [ ] **Step 5: 运行集成测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_notepad_smoke.py -v
```

Expected: PASS（在真实 Windows 桌面环境）。

- [ ] **Step 6: 提交**

```powershell
git add tests/integration/ README.md docs/overview.md pytest.ini
git commit -m "test: add real GUI integration smoke test with notepad"
```

---

### Task 2: 优化 allowed_commands 首次使用体验

**Files:**
- Modify: `computer_use/launcher.py`
- Create/Modify: `config.example.yaml`
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Test: `tests/test_launcher.py`

- [ ] **Step 1: 写 RED 测试**

在 `tests/test_launcher.py` 追加：

```python
def test_launch_app_empty_allowed_list_shows_config_hint() -> None:
    from computer_use import launcher

    result = json.loads(launcher.launch_app("notepad.exe"))

    assert result["status"] == "blocked"
    assert "allowed_commands" in result["error"].lower()
    assert "config.example.yaml" in result["error"] or "config.yaml" in result["error"]
```

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_launcher.py -k empty_allowed_list -v
```

Expected: FAIL，当前错误消息不含配置提示。

- [ ] **Step 3: 修改 launcher 错误消息**

在 `computer_use/launcher.py` 的 `launch_app` 失败分支中：

```python
error = (
    "Application launcher blocked: notepad.exe is not in allowed_commands. "
    "Add allowed app names to config.yaml (see config.example.yaml) to enable launch_app."
)
```

- [ ] **Step 4: 提供配置示例**

创建或更新 `config.example.yaml`：

```yaml
allowed_commands:
  - notepad.exe
  - calc.exe
  - mspaint.exe
```

- [ ] **Step 5: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_launcher.py -v
git add computer_use/launcher.py config.example.yaml tests/test_launcher.py docs/deployment.md docs/pitfalls.md
git commit -m "feat: improve launch_app first-time error message and config example"
```

---

### Task 3: 拆分 mcp_server.py

**Files:**
- Create: `computer_use/tools/__init__.py`
- Create: `computer_use/tools/schemas.py`
- Create: `computer_use/tools/dispatch.py`
- Create: `computer_use/tools/batch.py`
- Create: `computer_use/tools/composite.py`
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 写 RED 测试**

在 `tests/test_mcp_server.py` 追加：

```python
def test_mcp_server_imports_refactored_tool_modules() -> None:
    from computer_use.tools import schemas, dispatch, batch, composite

    assert schemas.TOOLS
    assert callable(dispatch.dispatch_tool)
    assert callable(batch.handle_batch)
    assert callable(composite.click_by_text)
```

- [ ] **Step 2: 运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k refactored_tool_modules -v
```

Expected: FAIL，`computer_use.tools` 尚不存在。

- [ ] **Step 3: 创建 tools 子包**

创建 `computer_use/tools/__init__.py`：

```python
from __future__ import annotations

from computer_use.tools.batch import handle_batch
from computer_use.tools.composite import click_by_text, fill_form, open_menu, scroll_until
from computer_use.tools.dispatch import dispatch_tool
from computer_use.tools.schemas import TOOLS

__all__ = ["TOOLS", "dispatch_tool", "handle_batch", "click_by_text", "fill_form", "open_menu", "scroll_until"]
```

创建 `computer_use/tools/schemas.py`：将 `mcp_server.py` 中 `TOOLS` 列表、`TextContent` 等 schema 相关定义迁移至此。

创建 `computer_use/tools/dispatch.py`：将 `_call_tool`、`_dispatch_tool`、`_failure_for_result`、`_dispatch_pointer_tool`、`_handle_tool_call` 等调用路由迁移至此。

创建 `computer_use/tools/batch.py`：将 `_batch_tool`、`_normalize_nested_tool_name` 等 batch 逻辑迁移至此。

创建 `computer_use/tools/composite.py`：将 `click_by_text`、`open_menu`、`fill_form`、`scroll_until` 等 composite 工具迁移至此。

- [ ] **Step 4: 修改 mcp_server.py 使用新模块**

在 `mcp_server.py` 中：

```python
from computer_use.tools import TOOLS, dispatch_tool, handle_batch
from computer_use.tools.schemas import ...  # 按需导入
```

删除已迁移的函数定义，保留 server 生命周期、`serve()`、prompt 注册。

- [ ] **Step 5: 运行测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/tools/ computer_use/mcp_server.py tests/test_mcp_server.py
git commit -m "refactor: split mcp_server tool schemas, dispatch, batch and composite into subpackage"
```

---

### Task 4: 文档补全（说明已实现的 redaction/UIA/OCR）

**Files:**
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Modify: `docs/overview.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 更新 deployment.md**

在 doctor 节后追加：

```markdown
### 已有安全与可用性能力

- **UIA 检查**：`doctor` 会检查 `uiautomation` 是否可导入；缺失时标记为 warning，但 server 仍可启动（视觉任务回退到坐标操作）。
- **截图 redaction**：`core.py` 已实现敏感顶层窗口相交检测，截图时会用红色块覆盖敏感区域。该能力默认启用。
- **OCR 能力**：项目集成了可选的 PaddleOCR；若环境已安装，可通过 OCR 工具识别截图中的自定义绘制控件文本。
```

- [ ] **Step 2: 更新 pitfalls.md**

追加：

```markdown
### 首次使用 launch_app 被拦截

`launch_app` 默认使用 `allowed_commands` 白名单。如果白名单为空，任何应用启动都会被拦截。
解决方法：复制 `config.example.yaml` 为 `config.yaml`，按需要添加允许的应用名称。

### 混合 DPI 多显示器 fail-fast

当前版本为保障坐标精度，检测到混合 DPI 多显示器时会直接拒绝输入操作。临时解决方法是将外接显示器缩放比例设为与主屏相同；长期支持需等待后续立项。

### OCR 是可选依赖

若需要识别自定义绘制控件，请安装 PaddleOCR 相关依赖；未安装时 OCR 工具不可用，但不影响其他功能。
```

- [ ] **Step 3: 更新 overview.md 测试策略**

追加测试策略小节：

```markdown
### 测试分层

- **单元测试**：mock 覆盖 core/safety/ui_automation/mcp_server 逻辑。
- **集成测试**：`tests/integration/` 下使用真实 Windows 应用做端到端闭环验证。
- **性能/压力测试**：当前未覆盖，计划后续补充 trace 数量增长下的 locator 性能基准。
```

- [ ] **Step 4: 运行 audit 并提交**

```powershell
.\.venv\Scripts\python.exe scripts/agent_links.py check
.\.venv\Scripts\python.exe scripts/audit.py check
python scripts\changelog.py add --title "docs: 补全部署文档与已知陷阱" --body "说明 doctor 已检查 UIA、截图 redaction、OCR 可选能力，以及 launch_app 白名单首次配置要求。"
git add docs/deployment.md docs/pitfalls.md docs/overview.md CHANGELOG.md
git commit -m "docs: clarify existing redaction, uia check and ocr capabilities"
```

---

### Task 5: 全量回归与归档

**Files:**
- Move after acceptance: `docs/plans/active/post-review-improvements-2026-06-17.md` to `docs/plans/completed/`
- Modify: `docs/CURRENT.md`

- [ ] **Step 1: 全量验证**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe -m compileall -q computer_use
.\.venv\Scripts\python.exe scripts\agent_links.py check
.\.venv\Scripts\python.exe scripts\audit.py check
git diff --check
```

Expected: 全部通过。

- [ ] **Step 2: 归档计划**

```powershell
Move-Item docs\plans\active\post-review-improvements-2026-06-17.md docs\plans\completed\
```

更新 `docs/CURRENT.md` 为无进行中任务。

- [ ] **Step 3: 最终提交**

```powershell
git add docs/plans/completed/ docs/CURRENT.md
git commit -m "docs: archive post-review improvement plan"
```

---

## 验收标准

- `tests/integration/test_notepad_smoke.py` 在真实 Windows 环境通过。
- `launch_app` 在 `allowed_commands` 为空时给出包含配置示例路径的错误。
- `computer_use/tools/` 子包存在，`mcp_server.py` 不再包含工具 schema/dispatch/batch/composite 实现。
- `pytest tests/ -m "not integration"` 全部通过。
- `scripts/agent_links.py check` 和 `scripts/audit.py check` 通过。
- 文档明确说明 UIA 检查、redaction、OCR 的当前状态。

## 风险与取舍

- 真实 GUI 集成测试依赖 Windows 桌面环境，CI 中可能无法稳定运行；默认使用 `-m "not integration"` 跳过。
- mcp_server.py 拆分是重构，需确保所有 import 路径和 MCP tool 名称不变。
- 混合 DPI 和操作取消/超时未纳入本计划，需后续单独立项。
