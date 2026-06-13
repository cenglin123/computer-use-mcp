# CHANGELOG

<!--
- 日期节倒序排列，最新在前；同一天多次修改合并到同一个日期节，用 `###` 区分主题。
- 写入前不要读全文，用 `python scripts/changelog.py titles/show/add/recent` 操作。
- 当前工作状态写在 docs/CURRENT.md；CHANGELOG 只记录历史变更。
-->

## 2026-06-13

### click/move_to 支持平滑移动

#### 变更内容
- 为 click 和 move_to 增加 duration 参数（默认 0.2 秒），通过 pyautogui 的 duration 实现平滑移动，避免光标瞬移导致悬停菜单/下拉框关闭。MCP 工具 Schema、本地 CLI 和 core API 均支持自定义 duration。新增对应单元测试。

### 初始化 agent-first 文档体系

#### 变更内容
- 将项目复制到 C:/Project/computer-use 并初始化 git。建立 AGENTS.md / CLAUDE.md / GEMINI.md 同步体系，创建 STRUCTURE.md、docs/ 专题文档、CHANGELOG 和 plans 目录。迁移 README.md 并添加 AI Agent 协作指针。配置 pre-commit hook。详见 docs/plans/completed/initialization.md。
