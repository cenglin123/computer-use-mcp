# AI 协作规范

> 本文件会被 AI 框架自动加载并始终驻留在上下文中，因此必须保持精简。
> 只放行为规则和信息指针，不放可从代码或其他文档获取的事实描述。
> 编辑后运行：`python scripts/agent_links.py repair`

## 项目概述

`computer-use` 是一个本地 MCP 服务器 + 调试 CLI，让 AI Agent 能截取屏幕、控制鼠标和键盘，以完成 Windows GUI 自动化任务。

## 同步声明

`AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 内容必须保持一致；读取时选择其一即可。**只编辑 AGENTS.md**，另两个由脚本同步。

- 检查：`python scripts/agent_links.py check`
- 修复：`python scripts/agent_links.py repair`
- 强制覆盖：`python scripts/agent_links.py repair --force`

本项目使用 copy 模式。

## 信息导航

- 文档总索引：[STRUCTURE.md](STRUCTURE.md)
- 系统主线与设计决策：[docs/overview.md](docs/overview.md)
- MCP 工具约定：[docs/api.md](docs/api.md)
- 部署与配置：[docs/deployment.md](docs/deployment.md)
- 已知环境陷阱：[docs/pitfalls.md](docs/pitfalls.md)
- 文档一致性审计：[docs/audit-checklist.md](docs/audit-checklist.md)
- 复杂任务计划：[docs/plans/README.md](docs/plans/README.md)
- 当前任务状态：[docs/CURRENT.md](docs/CURRENT.md)
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

## 行为规则

### 硬约束

- **不碰构建产物**：`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.egg-info/`、`dist/`、`build/` 属于生成物，除非任务明确要求，否则不要修改。
- **密钥不入库**：`config.yaml` 可能包含敏感配置；本地密钥只放环境变量或 `.env`，不硬编码。
- **输入设备安全**：`computer_use/core.py` 直接控制真实鼠标/键盘。任何改动必须通过 `safety.py` 的坐标检查和目标窗口检查，禁止绕过。
- **不绕过 hook**：`.githooks/pre-commit` 启用时，lint 或同步检查失败先修复，不要用 `--no-verify` 跳过。
- **完工必检**：任务完成后必须执行末尾的“完工检查清单”，不可跳过，不可先回复用户再补。

### 默认偏好

- **先读后改**：修改任何文件前先读取，理解现有逻辑再动手。
- **风格跟随**：Python 代码遵循已有风格；`snake_case`、4 空格缩进、`from __future__ import annotations`。
- **Occam**：如无必要，勿增实体；新增文件、脚本、规则前，先确认它解决的具体问题。
- **Bitter Lesson**：通用方法优于硬编码先验；优先复用 UIA、结构化工具和默认流程，谨慎增加任务枚举和关键词规则。
- **模式匹配**：单会话能完成的小改动用直接执行；涉及跨模块、改动超过 5 个文件、或可能跨会话的任务，走复杂任务闭环。
- **复杂任务闭环**：在 `docs/plans/active/` 落盘计划 → 审计 → 用户确认 → 执行 → 验收。
- **任务启动先读 CURRENT.md**：若存在未完成的上下文，向用户确认是继续还是覆盖。
- **验证尽量换视角**：高风险改动优先由新上下文或 reviewer 复查，不把“执行者自检”等同于“已验证”。

## 测试要求

- 运行完整测试套件：`pytest tests/ -v`
- 改动后至少通过受影响模块的测试：`pytest tests/test_<module>.py -v`
- 手动验证：涉及鼠标/键盘的改动，先在安全环境用 `python -m computer_use` CLI 验证。

## 安全与配置

- `computer_use/core.py` 调用 `pyautogui` 操作全局输入设备；`safety.py` 负责坐标边界和目标进程校验。
- 本地配置通过 `config.yaml` 读取；敏感字段优先从环境变量覆盖。
- 运行测试前确保没有用户正在操作鼠标/键盘，避免测试输入干扰当前工作。

## 提交规范

使用 Conventional Commit 风格：`feat:` / `fix:` / `chore:` / `test:` / `docs:`。

**及时提交**：完成一个功能阶段后主动暂存源码并提交，排除二进制生成物。

## 文档维护原则

**核心理念：只记代码里读不出来的东西。** 目录结构、函数签名、参数默认值不写入文档。

1. 设计决策写入 [docs/overview.md](docs/overview.md)；MCP 工具约定更新 [docs/api.md](docs/api.md)；部署或环境约束更新 [docs/deployment.md](docs/deployment.md)；环境陷阱写入 [docs/pitfalls.md](docs/pitfalls.md)。
2. 先更新对应 `docs/*.md`，再写 [CHANGELOG.md](CHANGELOG.md)。CHANGELOG 只记变更摘要。
3. 单个文档接近 300 行时按主题拆分，并在 [STRUCTURE.md](STRUCTURE.md) 补索引。
4. 复杂任务先在 `docs/plans/active/` 落盘计划，完成后移到 `docs/plans/completed/`。

**CHANGELOG 规则**

5. 日期节倒序排列，最新在前；同一天多次修改合并到同一个日期节，用 `###` 区分主题。
6. 写入前**不要读全文**；使用 `python scripts/changelog.py titles/show/add/recent` 操作。
7. 当前任务状态写入 [docs/CURRENT.md](docs/CURRENT.md)，不要写进 CHANGELOG。

**定期审计**

8. 每 ~20 次任务或每月，运行 `python scripts/audit.py check`。发现 `[DEAD]` / `[DRIFT]` / `[UNDOC]` / `[ORPHAN]` / `[BROKEN]` 项时，读取 [docs/audit-checklist.md](docs/audit-checklist.md) 逐项裁决。

## 完工检查清单

- [ ] **验证**：改动涉及的功能是否仍能正常工作？至少运行相关 pytest 并通过；涉及 GUI 的改动在安全环境手动验证。
- [ ] **复查视角**：高风险或跨模块任务是否经过新上下文或 reviewer 复查？没有做到时，在计划或回复中说明。
- [ ] **架构文档**：是否涉及架构变更？如是，更新 `docs/` 下对应文件。
- [ ] **CHANGELOG**：是否值得记录？如是，用 `python scripts/changelog.py add ...` 插入到当天日期节。
- [ ] **同步一致性**：本文件若被编辑，运行 `python scripts/agent_links.py check`；不一致时用 `python scripts/agent_links.py repair` 修复。
- [ ] **跳过条件**：纯格式修改、注释修改、同一会话内已记录的变更，可跳过文档更新（验证不可跳过）。
