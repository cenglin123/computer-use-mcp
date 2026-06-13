# 初始化 agent-first 文档体系

> 创建时间：2026-06-13
> 状态：✅ completed
> 模式：直接执行
> 协调人：Kimi Code

## 目标

为 `computer-use` 项目建立面向 AI Agent 的文档体系，使后续 Agent 会话能快速理解项目边界、行为规则和文档导航。

## 阶段划分

### 阶段 1：项目复制与 git 初始化
- **目标**：将原项目复制到 `C:/Project/computer-use` 并初始化 git。
- **涉及文件**：`C:/Project/computer-use/*`
- **验证标准**：`git status` 显示所有文件已 staged。
- **状态**：✅ completed

### 阶段 2：生成 AGENTS.md 及同步副本
- **目标**：基于项目实际信息生成 `AGENTS.md`，并同步到 `CLAUDE.md` / `GEMINI.md`。
- **涉及文件**：`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- **验证标准**：`python scripts/agent_links.py check` 返回 0。
- **状态**：✅ completed

### 阶段 3：创建 STRUCTURE.md 与 docs/ 专题文档
- **目标**：创建文档总索引和专题文档（overview/api/deployment/pitfalls/audit-checklist/CURRENT）。
- **涉及文件**：`STRUCTURE.md`, `docs/*.md`
- **验证标准**：`audit.py` 无死链，STRUCTURE 索引完整。
- **状态**：✅ completed

### 阶段 4：迁移 README.md
- **目标**：在保留原 README 内容的基础上，添加文档索引和 AI Agent 协作指针。
- **涉及文件**：`README.md`
- **验证标准**：README 仍包含原快速开始、工具列表、安全说明，并新增文档索引。
- **状态**：✅ completed

### 阶段 5：配置 pre-commit hook 与静态自检
- **目标**：配置 `.githooks/pre-commit`，运行 `audit.py` 做静态自检。
- **涉及文件**：`.githooks/pre-commit`
- **验证标准**：`python scripts/audit.py check` 退出码为 0（允许出生档案 [MISS]）。
- **状态**：✅ completed

## 决策记录

- 2026-06-13：选择“中型”文档体系。理由：项目虽为单一 Python 包，但涉及安全约束、MCP 协议、长期维护，需要完整的 docs/ 层级和 plans 目录。
- 2026-06-13：保留 `docs/api.md`，但将其主题改为“MCP 工具约定”，因为本项目无 HTTP API，但有 MCP tool 接口约定。

## 风险与遗留

- 当前 `pyautogui` 使用全局输入设备，Agent 与用户光标会冲突。已记录在 `docs/pitfalls.md`，长期解决方案需独立 VM / RDP 会话。
