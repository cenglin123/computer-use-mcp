---
type: retrospective
object_slug: 20260616-mcp-contract-plan
generated_at: 2026-06-16T10:55:00Z
---

# Retrospective · 20260616-mcp-contract-plan

## 1. 结束模式

**评议（deliberate）模式渐近收敛**：Round 1 评议 verdict=阻断需修复（5 plan_defect）→ Executor 修订 plan → Round 2 评议 verdict=可执行（B1-B5 全 resolved）。用户在 Round 1 后显式选择"评议内 Executor 修订 plan"路径，对应终止-b（渐近通过）的轻量变体——评议模式不强制盲审（盲审是完整收敛主循环 gate）。

## 2. 阻断轨迹

R1=5 → R2=0，单调下降，一次修复即清零。

## 3. Antipattern 巡查

| Round | 类型 | 对象 | 触发结果 |
|-------|------|------|---------|
| 1 | environment_lock-in | plan（.venv\Scripts\python.exe + 绝对 trace 路径） | 检测到但裁定为 AGENTS.md 认可的项目约定，无需整改 |
| 2 | none_active | executor 修复（B1-B5） | 无 minimum_patch/solution_anchoring/report_hallucination 命中 |

## 4. Executor 路径依赖评估

- 反折中：B4 真切换到结构化 invalid_tool（非 ValueError+flag 折中）✓
- 方案锚定：无（无 reviewer 要求的结构性切换被打补丁敷衍）
- 最小补丁：B5 全文同步（screenshots/snapshots 语义在 Architecture/状态证据/Task4/Task6/Task8/验收/风险 逐处更新），非仅改 Task6 ✓

## 5. Reviewer 间 Verdict 分歧分布

| 轮次 | Verdict | 阻断数 | 归因分布 |
|-------|---------|--------|----------|
| R1 | 阻断需修复 | 5 | 全 plan_defect（1 implementation / 3 structural / 1 conceptual） |
| R2 | 可执行 | 0 | — |

两轮 verdict 不冲突：R1 发现缺陷、R2 验证修复，方向一致。

## 6. 降级影响评估

无降级。Reviewer（R1/R2）与 Executor 均为真实 fresh-context spawn（opencode Task tool），无 orchestrator_self 替代。boundary_check 全程 pass。

## 7. 经验教训

- **机制层面**：评议模式对"计划系统性误述测试基础设施"这类 plan_defect 高效——Round 1 reviewer 通过核对真实代码一次性定位 5 个缺陷（含 1 个命中的命名一致性 conceptual），Executor 按明确设计决定单轮修复，Round 2 验证清零。证实了评议"事实核对"维度的关键价值：计划引用的具体符号/helper 必须与现状一致，否则误导执行器。
- **对象层面**：issue 5（snapshots 目录二义性）虽标 conceptual，但其修复（按文件类型分流）可在单轮内解决，验证了 Orchestrator"conceptual 不必然升级完整收敛"的语义判定——当修复方向明确且不涉及方向性重构时，评议内闭环足够。
- **设计决定沉淀**：manifest 扁平为 source of truth + envelope 派生（`_attach_trace_manifest`）；screenshots/=PNG、snapshots/=JSON 的类型分流；诊断工具（retry_step/review_task）排除出 batch 但保留在 task step——这三个决定在 plan 中已固化为明确约定。

## 8. 后续建议

- **延后 suggestion（执行阶段处理）**：run_task_plan 的 `steps[].tool` Schema enum 未被任何 task 覆盖（验收标准首条提及但 Task2 S4 只给 batch.actions[].tool 加了 enum）。执行 Task2 S4 时顺手对 run_task_plan.steps[].tool 加 `"enum": list(TASK_STEP_TOOL_NAMES)`，或验收时接受"Task2 S6 运行时规范化已强制契约"的口径。reviewer 确认非阻断。
- 执行此计划时建议走 subagent-driven-development（plan 顶部已标注 REQUIRED SUB-SKILL），9 个 task 顺序执行。

## 9. Round 0 合同谈判评估

| 维度 | 评估 |
|------|------|
| 是否启用 | 否（跳过理由：评议默认入口；计划已含明确目标/范围/验收标准/风险，无需前置合同谈判） |
| contract 是否减少预期错位 | N/A（无 contract）——评议本身承担了对齐职能，R1 reviewer 用前置自检 5 问 + 事实核对替代了合同验收断言 |
| contract_amendment 触发次数 | 0 |
| contract 与 plan 的同步性 | N/A |

## 10. Rubrics 评估

N/A（Round 0 skipped，无 contract，无 rubric_dimensions）。

## 成本数据

| 阶段 | tokens | 时间 | agent 数 | 关键产出 |
|------|--------|------|----------|---------|
| R0 合同谈判 | — | — | 0 | skipped |
| R1 Reviewer | ≈中 | ≈2min | 1 | 5 blocking + 4 suggestion（逐条附真实代码证据） |
| R1 Executor | ≈中 | ≈3min | 1 | plan 5 处修订 + 4 suggestion 处置 + attempts.md |
| R2 Reviewer | ≈中 | ≈2min | 1 | B1-B5 resolved + 1 suggestion |
| **总计** | **≈中** | **≈10min** | **3** | plan 收敛至可执行 |

> 精确 token 计数不可得（opencode Task tool 不返回 token），填估算。

## Rule Activity

| rule | triggered | zero_streak | status |
|------|-----------|-------------|--------|
| boundary_guard | false | 1 | active |
| reviewer_boundary_audit | false | 1 | active |
| intent_drift_check | false | 1 | active |
| gate_l1 | false | 1 | active |
| design_review_trigger | false | 1 | active |
| blind_recheck | false | 1 | active（评议模式不触发） |
