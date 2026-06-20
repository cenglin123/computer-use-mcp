---
type: retrospective
object_slug: 20260620-mcp-accuracy-perf
generated_at: 2026-06-20T11:55:00+08:00
---

# Retrospective · 20260620-mcp-accuracy-perf

## 1. 结束模式

**收敛**（终止-a 严格首轮通过的变体——经历 5 轮 + 2 次盲审后达成）。R5 fresh reviewer verdict=可执行 + blind recheck 2 verdict=可执行（零阻断）。

## 2. 阻断轨迹

R1=1(implementation, API设计歧义) → R2=escalated resolved + 1(structural, MCP分发绕过review.py) → R3=可执行 → blind1=fail(1 archaeology) → R4=1(implementation, archaeology残留line206) → R5=可执行 → blind2=pass

单调下降（每轮解决上轮问题），非振荡。R3→blind1 和 R4→R5 是两次"可执行后被盲审/更深审查发现问题"，属正常收敛深度递进。

## 3. Antipattern 巡查

| Round | 类型 | 对象 | 触发结果 |
|-------|------|------|---------|
| R1 | false_generality | 标题暗示功能性改进 | suggestion, executor 修正标题预期 |
| R1 | environment_lock-in | 绝对路径硬编码 | suggestion, executor 改环境变量引用 |
| blind1 | archaeology_leftover | 3处"已确定/或等价"措辞 | blocking, executor 重写 |
| R4 | archaeology_leftover | line206 "而非口头等价" | blocking, executor 重写 |
| R5/blind2 | (none) | — | 无反模式 |

## 4. Executor 路径依赖评估

- **minimum_patch**：未触发。R1 executor 修复彻底（不只在 API 设计层修补，而是补充了已有函数引用）。R2 executor 发现 MCP 分发层问题后完整重写了 Track C 相关章节。
- **solution_anchoring**：未触发。executor 在统一方案上选择了删除平行实现（彻底方案），而非在旧函数内打补丁。
- **over_compromise**：未触发。
- **report_hallucination**：未触发。所有 executor 报告的修改经独立 reviewer 验证属实。

## 5. Reviewer 间 Verdict 分歧分布

| 轮次 | Verdict | 阻断数 | 归因分布 |
|------|---------|--------|---------|
| R1 | 阻断需修复 | 1 | plan_defect:1 |
| R2 | 阻断需修复 | 1(+escalated resolved) | plan_defect:1 |
| R3 | 可执行 | 0 | — |
| blind1 | 阻断需修复 | 1 | pending→plan_defect |
| R4 | 阻断需修复 | 1 | plan_defect:1 |
| R5 | 可执行 | 0 | — |
| blind2 | 可执行 | 0 | — |

归因一致：所有 blocking 最终归因为 plan_defect（计划文档缺陷），无 executor_limit。这符合预期——收敛对象是 plan 文档，所有问题都是 plan 本身的问题。

## 6. 降级影响评估

无降级。全程使用 opencode task 工具 Spawn 独立 agent（reviewer + executor），reviewer_backend 均为 opencode。boundary_check 每轮 pass。

预算 gate tier: auditable-only（opencode 无 PreToolUse hook 绑定）。预算执行由 Orchestrator 手动 reserve/settle 驱动，无 hook 强制。这在会话开始时已记录。

## 7. 经验教训

**机制层面**：
1. **盲审的价值再次验证**：R3 给了"可执行"，但 blind1 发现了 3 处 archaeology_leftover——这是主循环 reviewer（看得到修复历史）容易忽略的，因为它们"知道为什么要写这些措辞"。盲审的空白视角是检测考古层的最佳工具。
2. **archaeology 清理需要全文扫描**：executor 修了盲审点名的 3 处，但 R4 发现了第 4 处（line 206）。清理反模式不能只修被点名的位置，需要全文扫描同类措辞。
3. **Plan 收敛的典型问题域**：(a) API 设计未定（多选留白）；(b) 代码现状假设错误（MCP 分发路径）；(c) 散文层考古残留。前两类是结构问题，第三类是质量纪律问题。

**对象层面**：
1. **MCP 分发层的"影子实现"**：`_review_task_session_result` 绕过 review.py 是一个典型的"平行实现"反模式——计划作者假设 MCP 工具委托到 Python 函数，但实际上存在一个私有助手绕过了它。这类假设需要代码验证。
2. **Plan 作为收敛对象的特点**：Plan 文档的可执行性不仅取决于"方案是否正确"，还取决于"措辞是否自足"。一个对 fresh executor 完全透明的 plan 才是可执行的。

## 8. 后续建议

1. **落地执行时**：执行者应特别注意 blind2 的 S1 suggestion（line 207 "已确认"措辞）和 S2（tool_contract.py 分类）。这些不阻断但值得在实现时清理。
2. **测试驱动**：计划推荐执行顺序 C→B→A→D。Track C 的 MCP 等价性验证（line 226）是关键验收点——它同时验证了"删除 _review_task_session_result"和"detail 参数透传"两个改动。
3. **R3 reviewer 的两条 suggestion**（MCP 响应形态迁移 + try/except 处理）是实施细节，executor 落地时应参考。

## 9. Round 0 合同谈判评估

| 维度 | 评估 |
|------|------|
| 是否启用 | 否（跳过理由：计划已为每条主线定义验收标准） |
| contract 是否减少预期错位 | N/A（跳过） |
| contract_amendment 触发次数 | 0 次 |
| contract 与 plan 的同步性 | N/A |

跳过 Round 0 是合理的——计划的每条主线都有"验收"小节，相当于内嵌的合同断言。R1 的 blocking 不是"验收标准缺失"而是"API 设计未做决策"（有验收但验收引用了未定义的机制）。

## 10. Rubrics 评估

N/A（未使用 Rubrics 评分——跳过 Round 0，未定义维度）。

## blind_recheck

```yaml
blind_recheck:
  status: pass
  traces_reported: 0
  rounds_used: 2
  findings_count: 0
  escalated_to_main_loop: false
```

blind1 发现 3 处 archaeology（escalated → 修复 → R4 发现第4处 → 修复 → R5 可执行 → blind2 pass）。blind2 零阻断。

## 成本数据

| 阶段 | tokens | 时间 | agent 数 | 关键产出 |
|------|--------|------|----------|---------|
| R1 Reviewer | ~8K | ~2min | 1 | API设计歧义 blocking |
| R1 Executor | ~6K | ~2min | 1 | Track C API 落定 + 5 suggestions |
| R2 Reviewer | ~8K | ~2min | 1 | escalated resolved + MCP dispatch blocking |
| R2 Executor | ~5K | ~2min | 1 | MCP 分发统一方案 |
| R3 Reviewer | ~8K | ~2min | 1 | verdict=可执行 |
| blind1 | ~6K | ~2min | 1 | archaeology_leftover blocking |
| R3/4 Executor | ~4K | ~1min | 1 | archaeology 清理 |
| R4 Reviewer | ~7K | ~2min | 1 | line206 archaeology blocking |
| R4 Executor | ~3K | ~1min | 1 | 3处措辞修正 |
| R5 Reviewer | ~7K | ~2min | 1 | verdict=可执行 |
| blind2 | ~6K | ~2min | 1 | verdict=可执行 (pass) |
| **总计** | **≈68K** | **≈20min** | **11** | 计划收敛完成 |

## Rule Activity

| rule | triggered | zero_streak | status |
|------|-----------|-------------|--------|
| boundary_guard | false | 1 | active |
| reviewer_boundary_audit | false | 1 | active |
| intent_drift_check | false | 1 | active |
| gate_l1 | false | 1 | active |
| design_review_trigger | false | 1 | active |
| blind_recheck | true | 0 | active |
| budget_gate | true | 0 | active |

blind_recheck 触发并成功（blind1 发现问题 → 修复 → blind2 pass），验证了盲审机制的必要性。追踪机制执行成本约 0（rule_frequency 字段在每轮 state 更新时顺带维护，无额外 spawn）。
