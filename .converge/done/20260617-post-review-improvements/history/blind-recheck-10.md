# Blind Recheck 10 · 20260617-post-review-improvements

## Trigger

Tenth blind recheck after BR9 amendments.

## Reviewer

Blind recheck reviewer (ses_124e7abbeffe3lol1m2fuGt05s)

## Verdict

阻断需修复

## Blocking Issues

1. **结构性**：项目已存在 `manual` marker 表示需要真实 Windows 桌面环境，本 plan 又新增语义重叠的 `integration` marker，未做调和；CI 跳过命令 `-m "not integration"` 无法阻止现有的 `manual` 测试运行，造成约定混乱。
   - Fix: 复用现有 `manual` marker，将 plan 中所有 `@pytest.mark.integration` 与 `-m "not integration"` 替换为 `manual`；不再新增 marker。

## Suggestions (non-blocking)

- P0 混合 DPI 排除 gate 已在验收标准列出，但 artifact 尚无 frontmatter 占位；建议在 plan 顶部增加 frontmatter 字段。

## Follow-up

Replaced `integration` marker with existing `manual` marker throughout the plan, updated pytest.ini step to confirm existing marker, and added frontmatter with `mixed_dpi_exclusion_ack: pending`. Proceed to blind recheck 11.
