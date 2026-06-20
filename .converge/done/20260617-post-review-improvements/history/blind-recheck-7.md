# Blind Recheck 7 · 20260617-post-review-improvements

## Trigger

Seventh blind recheck after BR6 amendments.

## Reviewer

Blind recheck reviewer (ses_12501158affeYtjuFXXNmi255L)

## Verdict

阻断需修复

## Blocking Issues

1. **结构性**：Task 1 集成测试调用 `get_ui_snapshot` 并断言 `snap["controls"]`，但该工具依赖可选的 `uiautomation`；项目设计允许 UIA 缺失时仅 warning 并回退到坐标操作。集成测试在 UIA 未安装环境会失败，与“UIA 可选”矛盾。
   - Fix: 在测试模块顶部使用 `pytest.importorskip("uiautomation")`，使 UIA 缺失时测试自动跳过。

## Suggestions (non-blocking)

- 显式检查并更新 `.github/workflows/*.yml` 的 pytest 命令，否则“CI 默认跳过”无法落地。
- 在 pitfalls.md/README.md 中强调 `allowed_commands` 默认空列表会阻止所有应用启动。
- 明确混合 DPI 排除确认以何种形式留存。
- Task 4 CHANGELOG title 与 commit message 不一致，建议统一。

## Follow-up

Amended test to importorskip uiautomation, added CI config check step, unified CHANGELOG title and commit message. Proceed to blind recheck 8.
