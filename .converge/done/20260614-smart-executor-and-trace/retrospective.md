# Retrospective

## Convergence Summary

- artifact: docs/plans/active/smart-executor-and-trace.md
- rounds: 3
- final_verdict: 可执行
- final_reviewer: ses_13aa37264ffe32VYbAoqFOyYzk

## Issues Resolved

### Round 1
1. `batch` 增加 condition/loop/variable 与"最简键鼠宏"原则冲突 → 移除，仅保留确定性顺序执行。
2. `click_text`/`open_menu` 的 OCR/视觉回退与"不提供 OCR"约定冲突 → 删除 OCR 回退，复合工具仅依赖 UIA。
3. `run_task_plan` 与 `batch` 边界不清 → 明确 `run_task_plan` 是任务级入口，强制生成 trace+report，无 LLM。
4. UID/handle 状态管理机制缺失 → 明确 snapshot-scoped 自包含句柄，无持久映射，失效返回 `stale_uid`。
5. trace 路径硬编码 `~/.kimi-code/` → 改为 `~/.computer-use/traces/`，可配置。
6. trace_id 生命周期模糊 → 前置定义 Trace Schema，明确单工具/batch/run_task_plan 的 trace_id 策略。

### Round 2
- docs/pitfalls.md:47 仍推荐 OCR → 更新为"MCP 不提供 OCR，由上层模型看图决策"。
- docs/audit-checklist.md PaddleOCR 审计项 → 标注为历史项/视觉工具说明。
- UID 表述 → 统一为 snapshot-scoped 自包含句柄。
- trace_dir 与 screenshot_dir/log_dir 不一致 → 在计划中说明独立评估。

## Outstanding Suggestions (Non-Blocking)

- `click_by_text` 与 `click(target_name=...)` 的精确语义可在实现文档/API 中进一步细化。
- `run_task_plan` 的"预定义模板"与直接工具调用的层级可在实现时收敛。
- pitfalls.md 中两段 UIA 回退内容未来可合并。

## Key Decisions

- MCP server 不引入 LLM，只做确定性执行。
- 不引入 OCR/视觉回退；自定义绘制控件由上层多模态模型看图决策。
- `batch` 是确定性执行快捷键，不是工作流引擎。
- `run_task_plan` 是任务级入口，强制生成结构化 trace 和 report。
- trace 默认路径中性化：`~/.computer-use/traces/`。

## Next Step

进入阶段实施：先定义 Trace Schema，再实现 snapshot 与 trace 记录。
