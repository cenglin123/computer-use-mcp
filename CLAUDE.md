# AI 协作规范

<!-- AGENTS.md 是主副本。编辑后运行：python scripts/agent_links.py repair -->
> 本文件会被 AI 框架自动加载并始终驻留在上下文中，因此必须保持精简。
> 只放行为规则和信息指针，不放可从代码或其他文档获取的事实描述。

## 项目概述

`computer-use` 是一个本地 MCP 服务器 + 调试 CLI，让 AI Agent 能截取屏幕、控制鼠标和键盘，以完成 Windows GUI 自动化任务。

## 同步声明

`AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 内容必须保持一致；读取时选择其一即可。**只编辑 AGENTS.md**，另两个由脚本同步。

- 检查：`python scripts/agent_links.py check`
- 修复：`python scripts/agent_links.py repair`
- 强制覆盖（确认另两份可被 AGENTS.md 覆盖后）：`python scripts/agent_links.py repair --force`

本项目使用 copy 模式。

## 信息导航

- 文档总索引：[STRUCTURE.md](STRUCTURE.md)
- 系统主线与设计决策：[docs/overview.md](docs/overview.md)
- MCP 工具约定：[docs/api.md](docs/api.md)
- 部署与配置：[docs/deployment.md](docs/deployment.md)
- 已知环境陷阱：[docs/pitfalls.md](docs/pitfalls.md)
- 文档一致性审计：[docs/audit-checklist.md](docs/audit-checklist.md)
- 当前任务状态：[docs/CURRENT.md](docs/CURRENT.md)
- 项目记忆索引：[.agent/memory/MEMORY.md](.agent/memory/MEMORY.md)
- 复杂任务计划：`docs/plans/`（按需要时在 `active/` 下创建计划文件）
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

## 项目记忆

- **用户**：中文交互；偏好先规划再执行，重要任务走 converge 评审；关注工具执行效率与安全性。
- **项目上下文**：通用 Windows GUI 自动化 MCP；核心为 `pyautogui` + 可选 `uiautomation`；无 OCR；截图只返回路径，`batch.final_screenshot` 默认关闭；默认状态根目录 `~/.computer-use/`。
- **关键教训**：优先模型视觉、UIA 和 Shell 启动；自绘界面回退视觉定位；等待优先事件工具，必要时 `sleep`；长任务用原生 `batch`；MCP 只做键鼠宏和观察；桌面图标用 `LVM_GETITEMPOSITION`；直接调用客户端暴露的 `computer-use` 工具，不写 Python 包装 `_call_tool`。
- **详细记忆**：[.agent/memory/MEMORY.md](.agent/memory/MEMORY.md)

> 每次更新 `.agent/memory/` 后，同步维护本节摘要。

## 行为规则

### Compact 恢复（上下文压缩后强制执行）

若你的上下文中包含 "continued from a previous conversation"（compact 恢复信号），在继续任何实质性工作前：

1. 读取 `docs/CURRENT.md` — 确认当前任务状态
2. 读取 `.agent/memory/MEMORY.md` — 恢复项目记忆与用户画像
3. 上述步骤完成前，**禁止执行写操作、禁止做出有副作用的判断**

> compact 后 Agent 丢失大量上下文，必须先恢复关键状态。

### 硬约束（不可违反）

- **不碰构建产物**：`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.egg-info/`、`dist/`、`build/` 是生成物，非任务要求不修改。
- **密钥不入库**：只放环境变量或 `.env`，不硬编码。
- **输入设备安全**：`computer_use/core.py` 直接控制真实鼠标/键盘。任何改动必须通过 `safety.py` 的坐标检查和目标窗口检查，禁止绕过。
- **不绕过 hook**：`.githooks/pre-commit` 启用时，lint 或同步检查失败先修复，不要用 `--no-verify` 跳过。
- **完工必检**：任务完成后必须执行末尾的"完工检查清单"，不可跳过，不可先回复用户再补。

### 默认偏好（有充分理由可偏离）

- **先读后改**：修改任何文件前先读取，理解现有逻辑再动手。
- **风格跟随**：Python 代码遵循已有风格；`snake_case`、4 空格缩进、`from __future__ import annotations`。
- **Occam**：如无必要，勿增实体；新增文件、脚本、规则或流程前，先确认它解决的具体问题。
- **Bitter Lesson**：通用方法优于硬编码先验；优先复用 UIA、结构化工具和默认流程，谨慎增加任务枚举和关键词规则。
- **模式匹配与执行模式**：单会话能完成的小任务用直接执行模式；涉及跨模块、预计改动超过 5 个文件、或可能跨会话完成的任务，走**复杂任务闭环**。
- **复杂任务闭环（计划 → 审计 → 拍板 → 执行 → 验收）**：
  1. **计划**：在 `docs/plans/active/` 落盘具体方案（问题清单、影响文件、验收标准）。
  2. **审计**：用 subagent 审计计划，修正漏洞和遗漏。
  3. **拍板**：向用户呈现计划，确认后再执行。
  4. **执行**：严格按计划逐项修改，不发散。
  5. **验收**：用 subagent 审计执行结果，确认与计划一致。

  **升级触发**：连续 2 轮反复修同一问题或执行后仍出 bug 时，主动向用户提议切换到计划驱动工作流。
- **任务启动先读 CURRENT.md**：接到新任务时，先读取 `docs/CURRENT.md`。若存在未完成的上下文（任务状态非"无"），向用户确认是继续还是覆盖。
- **并行协作时**：把状态真相源放在计划文件，而不是塞进一个全局 CURRENT.md。
- **任务级选择模式**：项目默认倾向分阶段推进，但每个任务开始前仍要按复杂度、风险和是否并行重新判断采用哪种模式。
- **验证尽量换视角**：高风险改动优先由新上下文或 reviewer 视角复查，不把"执行者自检"等同于"已验证"。

## 测试要求

- 运行完整测试套件：`pytest tests/ -v`
- 改动后至少通过受影响模块的测试：`pytest tests/test_<module>.py -v`
- 手动验证：涉及鼠标/键盘的改动，先在安全环境用 `python -m computer_use` CLI 验证。

## 安全与配置

- `computer_use/core.py` 调用 `pyautogui` 操作输入设备；`safety.py` 负责坐标边界和目标进程校验。
- 本地配置通过 `config.yaml` 读取；敏感字段优先从环境变量覆盖。
- 运行测试前确保没有用户正在操作鼠标/键盘，避免测试输入干扰当前工作。

## 提交规范

使用 Conventional Commit 风格。

**及时提交**：完成一个功能阶段后主动暂存源码并提交，排除二进制生成物。

## 文档维护原则

**核心理念：只记代码里读不出来的东西。** 目录结构、函数签名、参数默认值不写入文档。

1. 设计决策写入 [docs/overview.md](docs/overview.md)；MCP 工具约定更新 [docs/api.md](docs/api.md)；部署或环境约束更新 [docs/deployment.md](docs/deployment.md)；环境陷阱写入 [docs/pitfalls.md](docs/pitfalls.md)。
2. 先更新对应 `docs/*.md`，再写 [CHANGELOG.md](CHANGELOG.md)。CHANGELOG 只记变更摘要。
3. 单个文档接近 300 行时按主题拆分，并在 [STRUCTURE.md](STRUCTURE.md) 补索引。
4. 需要走"复杂任务闭环"的任务，先在 `docs/plans/active/` 落盘计划，实施完成后移到 `docs/plans/completed/`。单会话小任务不必建计划。

**CHANGELOG 规则**

5. 日期节倒序排列，最新在前；同一天多次修改合并到同一个日期节，用 `###` 区分主题。
6. 写入前**不要读全文**；使用 `titles --limit 5` 看标题树，`show --date` 或 `--match` 读局部，`add --title --body` 追加。
7. 当前任务状态写入 [docs/CURRENT.md](docs/CURRENT.md)，不要写进 CHANGELOG。
8. 只写"改了什么、为什么改、有什么迁移影响"，不贴代码，不重复 `docs/` 中已经存在的设计说明。

**定期审计**

9. 每 ~20 次任务或每月，运行 `python scripts/audit.py check` 做机械检查。发现 `[DEAD]` / `[DRIFT]` / `[UNDOC]` / `[ORPHAN]` / `[BROKEN]` 项时，读取 [docs/audit-checklist.md](docs/audit-checklist.md) 逐项裁决。

## 完工检查清单

文档没跟上会让下次对话基于过时信息决策。**每次任务完成后必须逐项走完清单，再向用户报告完成。**

- [ ] **验证**：改动功能是否正常？至少运行相关 pytest 并通过；GUI 改动在安全环境手动验证。
- [ ] **复查视角**：高风险或跨模块任务是否经新上下文或 reviewer 复查？未做到时在计划或回复中说明。
- [ ] **架构文档**：是否涉及架构变更？如是，更新 `docs/` 下对应文件。
- [ ] **CHANGELOG**：是否值得记录？如是，用 `python scripts/changelog.py add ...` 插入到当天日期节。
- [ ] **同步一致性**：本文件若被编辑，运行 `python scripts/agent_links.py check`；不一致时用 `python scripts/agent_links.py repair` 修复。
- [ ] **跳过条件**：纯格式修改、注释修改、同一会话内已记录的变更，可跳过文档更新（验证不可跳过）。
- [ ] **记忆自检**：本次对话是否产生值得沉淀的记忆（用户偏好、项目上下文、可复用教训）？如是，更新 `.agent/memory/` 对应文件并同步 AGENTS.md「项目记忆」内联摘要。
