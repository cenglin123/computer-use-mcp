# Blind Recheck 5 · 20260617-post-review-improvements

## Trigger

Fifth blind recheck after R20 amendment.

## Reviewer

Blind recheck reviewer (ses_1250fa431ffeGSPoL8z9PmOHQV)

## Verdict

阻断需修复

## Blocking Issues

1. **结构性**：Task 3 Step 4 的 `mcp_server.py` 导入示例遗漏 `_TASK_CONTEXT_EXCLUDED_TOOLS`，而 plan 已要求迁移该常量；未改动的 `_attach_task_context_schemas()` 在 `mcp_server.py` 中仍引用它，将导致 NameError。
   - Fix: 在导入示例中加入 `_TASK_CONTEXT_EXCLUDED_TOOLS`。

2. **架构性**：混合 DPI 多显示器支持作为原始评审 #1 P0 项被排除，plan 未提供用户/维护者签认或后续立项承诺，scope 缺口未闭环。
   - Fix: 在「风险与取舍」节追加 P0 项排除确认与 2 周内单独立项的承诺。

## Suggestions (non-blocking)

- Task 1 `_find_window_by_process` 使用裸 `except Exception` 可能吞掉真实错误。
- Task 3 RED 测试断言私有常量 `_MANIFEST_TOOL_NAMES` 等存在性，偏脆弱。
- Task 4 CHANGELOG 命令使用中文 title，需确认项目提交规范。

## Follow-up

Amend plan import example and risk section, then run blind recheck 6.
