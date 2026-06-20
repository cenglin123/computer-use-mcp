# Blind Recheck 6 · 20260617-post-review-improvements

## Trigger

Sixth blind recheck after BR5 amendments.

## Reviewer

Blind recheck reviewer (ses_12507b9a4ffeTgNnlV4RUtWCK4)

## Verdict

阻断需修复

## Blocking Issues

1. **概念性**：Task 2 把通用 `_BLOCKED_ERROR` 改写为只针对空 `allowed_commands` 白名单的提示，并用于两处返回点；若第二处是敏感进程拦截，新消息会误导用户去配置白名单，而敏感进程本不该通过白名单放行。
   - Fix: 拆分为 `_NOT_ALLOWED_ERROR`（白名单未命中/为空）和 `_SENSITIVE_PROCESS_ERROR`（敏感进程/窗口拦截），并更新 RED 测试断言。

2. **结构性**：原始评审 P2 建议「引入视觉 fallback 和 OCR」在「范围 > 不包含」中完全缺失，仅在 pitfalls.md 和验收标准中零散提到 OCR 未提供。边界不诚实。
   - Fix: 在「不包含」中显式列出「独立 OCR 工具 / 视觉 fallback 引擎的实现」，并说明当前采用多模态模型读图 + 坐标回退。

## Suggestions (non-blocking)

- 在 plan frontmatter 或验收标准中把混合 DPI 排除确认作为前置 gate 显式列出。
- 确认 pyautogui 为主依赖并在 fixture 契约中说明。
- 在 Task 3 中补充 schema 提取只是 mcp_server 拆分第一步、后续拆分的粗略路线图。

## Follow-up

Amended Task 2 error messages, added OCR/visual-fallback exclusion to scope, added mixed DPI gate to acceptance criteria, added pyautogui dependency note, and added mcp_server split roadmap note. Proceed to blind recheck 7.
