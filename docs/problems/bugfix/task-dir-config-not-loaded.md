---
id: bugfix-task-dir-config-not-loaded
type: bugfix
title: task_dir 配置项未被加载导致任务会话写入默认目录
status: fixed
severity: medium
scope:
  - config
  - audit
modules:
  - computer_use.config
  - computer_use.task_session
tags:
  - task-dir
  - config
  - audit
  - task-session
symptoms:
  - 设置 COMPUTER_USE_CONFIG 后 trace_dir 生效但 task_dir 仍写入默认用户目录
error_signatures:
  - list_tasks 返回默认目录中的历史任务
related_files:
  - computer_use/config.py
  - tests/test_config.py
  - config.yaml
verification:
  level: automated
  kind: unit-test
  path: tests/test_config.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_config.py -v
created_at: 2026-06-16
updated_at: 2026-06-16
---

# task_dir 配置项未被加载导致任务会话写入默认目录

## 现在的行为

手工 MCP 验证使用临时 `COMPUTER_USE_CONFIG` 指定 `trace_dir` 和 `task_dir` 时，trace 写入临时目录，但业务 task 仍写入 `~/.computer-use/tasks/`。随后 `list_tasks` 返回默认目录中的历史任务数量，而不是临时验证目录中的任务数量。

## 预期的行为

`config.yaml` 中的 `task_dir` 应与 `trace_dir` 一样由 `load_config()` 读取。业务任务会话、locator 和 task 审计查询都应使用配置中的 `task_dir`，便于测试、部署和备份隔离。

## 复现方式

1. 创建临时配置文件，包含自定义 `trace_dir` 和 `task_dir`。
2. 设置 `COMPUTER_USE_CONFIG` 指向该文件。
3. 调用 `start_task`、带 `task_id` 的无破坏性工具、`finish_task`。
4. 在新进程中调用 `list_tasks` 或 `get_task`。
5. 观察到 task 数据仍位于默认 `~/.computer-use/tasks/`。

该问题可稳定复现；根因在配置加载层。

## 原因是什么

`task_session.task_dir()` 会读取 `load_config().get("task_dir", 默认目录)`，但 `computer_use.config._DEFAULTS` 和 `_load_config()` 没有声明或加载 `task_dir`。因此即使 YAML 写了 `task_dir`，最终配置字典也没有该键，调用方只能回退到默认目录。

## 怎么修复的

- 在 `_DEFAULTS` 中增加 `task_dir: ~/.computer-use/tasks`。
- 在 `_load_config()` 初始配置和 YAML 覆盖逻辑中加载 `task_dir`。
- 在 `config.yaml` 示例配置中补充 `task_dir`。
- 在 `tests/test_config.py` 中覆盖默认值、显式配置和环境变量配置三条路径。

## 验证结果

已执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```

结果：`4 passed`。

## 风险和后续

本次修复只补配置加载，不迁移已经写入默认目录的历史 task。误写入的本次手工验证 task 已按明确 ID 清理；其他历史审计数据不做自动处理。
