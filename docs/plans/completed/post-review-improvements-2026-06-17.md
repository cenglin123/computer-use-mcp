---
status: completed
mixed_dpi_exclusion_ack: "user 2026-06-20"
---

# Post-Review 改进计划（2026-06-17，简化版）

## 背景

外部评审指出 `computer-use-mcp` 在真实 GUI 集成测试、首次使用体验、`mcp_server` 可维护性方面存在明显短板。本计划将这些建议转化为可执行改造任务。

## 范围

**包含：**

- 真实 GUI 集成测试骨架与首批闭环测试。
- `allowed_commands` 首次使用体验优化。
- 将 `mcp_server.py` 中静态的 MCP tool schemas 提取到独立模块 `computer_use/tools/schemas.py`。
- 文档补全：说明当前已实现的 redaction、UIA 检查能力。
- 全量回归与归档。

**不包含：**

- 混合 DPI 多显示器支持（技术风险高，需单独立项）。
- 替换 pyautogui 为更低层 Windows API。
- 操作取消/超时机制（需 Runner 架构改造）。
- 系统性 trace/logging 改造（异常吞没问题）。
- 白名单策略迁移（当前为黑名单策略）。
- 安全规则 fuzz 测试。
- 独立 OCR 工具 / 视觉 fallback 引擎（当前由多模态模型读图 + 坐标回退）。

## 文件结构与职责

| 动作 | 文件 | 职责 |
|------|------|------|
| Create | `tests/manual/conftest.py` | manual 测试 fixture：启动真实 Windows 应用、准备临时 screenshot_dir、测试结束后清理进程与文件。 |
| Create | `tests/manual/test_notepad_smoke.py` | 首个真实 GUI smoke 测试：启动 notepad，验证 screenshot 工具可重复执行并返回有效文件路径，验证 UIA 前台快照返回控件列表。 |
| Modify | `tests/test_launcher.py` | 追加验证 `launch_app` 白名单为空时错误提示的 RED 测试。 |
| Modify | `tests/test_mcp_server.py` | 追加验证 schemas 模块导出以及 schema tool 名称与 dispatch key 对齐的测试。 |
| Verify | `pytest.ini` | 确认已存在 `manual` marker；复用该 marker，不新增 marker。 |
| Modify | `pyproject.toml` | 在 dev 依赖中新增 `pytest-timeout>=2.0` 与 `pywin32>=306`。 |
| Modify | `computer_use/launcher.py` | 将白名单拦截与敏感进程拦截的错误消息分离，并在白名单为空/未命中时指向配置示例。 |
| Create/Modify | `config.example.yaml` | 增加 `allowed_commands` 示例白名单。 |
| Create | `computer_use/tools/__init__.py` | tools 子包入口。 |
| Create | `computer_use/tools/schemas.py` | 静态 `TOOLS` schema 列表及 schema 相关常量。 |
| Modify | `computer_use/mcp_server.py` | 从 `computer_use.tools.schemas` 导入 `TOOLS` 和相关常量。 |
| Modify | `docs/deployment.md` | 说明 doctor UIA 检查与截图 redaction 现状。 |
| Modify | `docs/pitfalls.md` | 说明混合 DPI、allowed_commands 首次配置、视觉 fallback、集成测试副作用。 |
| Modify | `docs/overview.md` | 补充测试策略分层说明。 |
| Modify | `README.md` | 增加 manual 测试运行说明与 allowed_commands 配置提示。 |
| Modify | `CHANGELOG.md` | 记录最终变更。 |
| Move | `docs/plans/active/post-review-improvements-2026-06-17.md` | 验收后归档到 `docs/plans/completed/`。 |
| Modify | `docs/CURRENT.md` | 验收后更新为无进行中任务。 |

## Task 1：真实 GUI 集成测试骨架

- 创建 `tests/manual/conftest.py` 与 `tests/manual/test_notepad_smoke.py`。
- 复用现有 `manual` marker；确认 `pytest.ini` 中已配置；检查 CI 工作流是否使用 `-m "not manual"`。
- 在 `pyproject.toml` dev 依赖中新增 `pytest-timeout` 与 `pywin32`。
- 验证 UIA 缺失时测试自动跳过；`pywin32` 缺失时 fixture 不导致 collection 失败；测试失败时进程能可靠清理。

## Task 2：优化 allowed_commands 首次使用体验

- 在 `computer_use/launcher.py` 中为白名单拦截与敏感进程拦截提供不同错误消息。
- 白名单为空/未命中时的消息应指向 `config.example.yaml`。
- 创建/更新 `config.example.yaml`，加入示例白名单。
- 在 `tests/test_launcher.py` 中补充先写失败的 RED 测试（Red-Green TDD），确保测试自包含、不依赖真实 Start Menu 或 win32com。

## Task 3：提取 MCP tool schemas 到独立模块

- 创建 `computer_use/tools/schemas.py`，迁移 `TOOLS` 列表及 schema 相关常量。
- 保持 `_call_tool`、`_dispatch_tool`、`_handle_tool_call`、`_batch_tool` 及 batch/composite 运行时逻辑不变。
- 修改 `mcp_server.py` 从 schemas 模块导入。
- 补充 `tests/test_mcp_server.py` 验证：
  - schemas 模块导出 `TOOLS` 及相关常量；
  - `TOOLS` 中每个 tool 的 `name` 在 `mcp_server.py` 中存在对应 dispatch handler，防止 schema 与 dispatch key 漂移。

## Task 4：文档补全

- 更新 `docs/deployment.md`：说明 doctor UIA 检查、截图 redaction。
- 更新 `README.md`：manual 测试运行说明、allowed_commands 配置提示。
- 更新 `docs/pitfalls.md`：首次使用 launch_app 被拦截、混合 DPI fail-fast、视觉 fallback、集成测试副作用。
- 更新 `docs/overview.md`：测试分层策略。

## Task 5：全量回归与归档

- 确认 P0 混合 DPI 排除已获用户/维护者书面确认（更新 frontmatter `mixed_dpi_exclusion_ack`）。
- 运行 `pytest tests/ -m "not manual"`、compileall、`scripts/agent_links.py check`、`scripts/audit.py check`、`git diff --check`。
- 使用 `scripts/changelog.py add` 记录变更；更新 `CHANGELOG.md`。
- 将计划归档到 `docs/plans/completed/`，更新 `docs/CURRENT.md`。

## 验收标准

- `tests/manual/test_notepad_smoke.py` 在真实 Windows 环境且无用户操作输入设备时通过。
- `launch_app` 在 `allowed_commands` 为空/未命中时给出指向配置示例的错误。
- `computer_use/tools/schemas.py` 存在且导出 `TOOLS`；`mcp_server.py` 从该模块导入。
- `tests/test_mcp_server.py` 验证 `TOOLS` 中每个 tool 名称在 `mcp_server.py` 中存在对应 dispatch handler，防止 schema 与 dispatch key 漂移。
- 不拆分 `_call_tool`、`_dispatch_tool`、`_handle_tool_call`、`_batch_tool` 及 composite adapter。
- `pytest tests/ -m "not manual"` 全部通过。
- `scripts/agent_links.py check` 与 `scripts/audit.py check` 通过。
- 文档明确说明 UIA 检查、redaction 现状，不声称 OCR 为已有能力。
- 前置 gate：P0 项「混合 DPI 多显示器支持」排除已获书面确认；本计划完成后 2 周内须创建后续计划并启动设计评审。

## 风险与取舍

- manual 测试依赖真实 Windows 桌面环境并生成截图；需使用临时目录、严格清理、避免用户操作时运行。
- schema 提取是低风险重构，不触及运行时逻辑；它只是 `mcp_server.py` 拆分的**第一步**，后续仍需另立项拆分 tool handlers、batch/composite 运行时。
- 混合 DPI 支持技术风险高、测试成本高，明确排除并计划单独立项。

## 变更日志

- 2026-06-18：由详细实现版简化为高层任务版，剥离具体代码片段，以减少 converge 轮次并聚焦于 scope、边界与验收标准。
