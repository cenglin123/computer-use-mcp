---
type: retrospective
object_slug: 20260616-mcp-distribution-out-of-box-usage
generated_at: 2026-06-17T01:00:00+08:00
---

# Retrospective · 20260616-mcp-distribution-out-of-box-usage

## 1. 结束模式

**终止-b 渐近通过**：用户授权继续修复后，Round 8 fresh reviewer 返回 `verdict: 可执行`，零阻断问题。收敛经历 8 轮（含 1 轮盲审复核），超过默认 `max_outer_loops=5`。

## 2. 阻断轨迹

R1=8 → R2=4 → R3=7 → R4=0 → 盲审=5 → R5=2 → R6=1 → R7=3 → R8=0

整体趋势：从 8 个阻断问题最终收敛到 0。R3 和 R7 出现反弹，原因是 reviewer 引入了新的审查维度（代码库实际状态审计、TOML 转义、overview.md 更新）。

## 3. Antipattern 巡查

| Round | 类型 | 对象 | 触发结果 |
|-------|------|------|---------|
| R1 | environment_lock-in | examples/clients/generic-mcp.json / kimi-code.toml 硬编码绝对路径 | 修复为占位符模板 |
| R1 | minimum_patch | `_get_prompt` 代码片段不完整 | 修复为完整实现 |
| R1 | false_generality | `generic-mcp.json` 名实不符 | 修复为模板说明 |
| R3 | minimum_patch | Task 3 遗漏 mouse_down/up/drag 等真实输入工具 | 修复为统一覆盖 |
| R5 | past_commitment_anchoring | Task 7 测试仍基于旧 README header | 修复为与新结构对齐 |
| 盲审 | archaeology_leftover | 计划中出现“本轮审计结果：名称一致”等修复痕迹 | R5 executor 删除 |
| 盲审 | environment_lock-in | doctor 硬编码 config 键 | 通过审计确认 schema 后接受 |
| R7 | data_tool_coupling | README 品牌词位置测试 | 修复为更鲁棒的 onboarding header 检查 |

## 4. Executor 路径依赖评估

- **反折中（over_compromise）**：未触发。Executor 在 BR-3 上选择了明确策略（依赖权威，移除静默 fallback），而非妥协共存。
- **方案锚定（solution_anchoring）**：R7 reviewer 指出 Task 6 深度绑定手动 JSON-RPC；但计划保留了该方案，因为这是 stdio MCP 的最小可执行路径，且 server 实际使用 stdio。
- **最小补丁（minimum_patch）**：触发多次（R1, R3），均已修复。

## 5. Reviewer 间 Verdict 分歧分布

| 轮次 | Verdict | 阻断数 | 归因分布 |
|------|---------|--------|---------|
| R1 | 阻断需修复 | 8 | plan_defect x8 |
| R2 | 阻断需修复 | 4 | plan_defect x4 |
| R3 | 阻断需修复 | 7 | plan_defect x7 |
| R4 | 可执行 | 0 | — |
| 盲审 | 阻断需修复 | 5 | pending x5 |
| R5 | 阻断需修复 | 2 | plan_defect x2 |
| R6 | 阻断需修复 | 1 | plan_defect x1 |
| R7 | 阻断需修复 | 3 | plan_defect x3 |
| R8 | 可执行 | 0 | — |

## 6. 降级影响评估

无降级。所有 Reviewer/Executor 均通过 opencode `task` 子代理执行，模型档位 inherit。

## 7. 经验教训

- **代码库状态审计必须在计划中显式化**：R3/R7 反复出现“未审计代码库实际状态”类问题。未来计划应把审计步骤作为独立 Step 0，并要求记录实际名称清单。
- **示例文件的可移植性容易被低估**：硬编码路径、TOML 转义、JSON 字符串格式等小问题会直接影响“开箱可用”。
- **单一事实源架构需要文档同步**：引入 guidance.py 单一事实源时，必须同步更新 overview.md，否则架构约定不可见。
- **盲审复核能有效发现考古层和一致性缺口**：盲审查出的 BR-1/BR-2/BR-3/BR-5 都是主循环 reviewer 未覆盖的视角。

## 8. 后续建议

- 执行该计划时，务必先完成每个 Task 的 Step 0 审计步骤，并记录实际名称清单。
- 执行后再次运行 `python scripts/audit.py check` 和 `python scripts/agent_links.py check`。
- 考虑把 Round 8 的 4 条 suggestion（文档逐字段落、cli.py 控制流回退、config schema 审计、smoke test 非 JSON stdout 处理）作为执行阶段的小幅增强，但不阻塞计划通过。

## 9. Round 0 合同谈判评估

| 维度 | 评估 |
|------|------|
| 是否启用 | 否（用户直接请求 ultraverge review） |
| 未启用理由 | 用户明确使用 ultraverge 关键词触发全量流程 |
| contract_amendment 触发次数 | 0 |

## 10. Rubrics 评估

| 维度 | 评估 |
|------|------|
| 使用的维度 | 无显式 contract/rubric；使用前置自检 5 问 + DR1-DR7 |
| 未使用/总高分的维度 | — |
| rubric_gap 触发次数 | 0 |
| 跨轮分数趋势 | 不适用 |

## 盲审复核

```yaml
blind_recheck:
  status: fail_then_resolved
  traces_reported: 2
  rounds_used: 1
  findings_count: 5
  escalated_to_main_loop: true
```

盲审 5 条 findings 中，R5 主循环 reviewer 判定 2 条仍阻断（BR-2, BR-3），3 条已解决（BR-1, BR-4, BR-5）。阻断项在 R5 修复后解决。

## Rule Activity

| rule | triggered | zero_streak | status |
|------|-----------|-------------|--------|
| boundary_guard | true | 0 | active |
| reviewer_boundary_audit | false | 8 | active |
| intent_drift_check | false | 8 | active |
| gate_l1 | false | 8 | active |
| design_review_trigger | false | 8 | active |
| blind_recheck | true | 0 | active |
