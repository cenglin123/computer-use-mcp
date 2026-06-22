---
type: retrospective
object_slug: 20260622-runtime-permission-whitelist
generated_at: "2026-06-22T01:50:00Z"
---

# Retrospective · 20260622-runtime-permission-whitelist

## 1. 结束模式
**收敛** — R2 独立 Reviewer verdict = 可执行，6 个 escalated issues 全部 resolved。

## 2. 阻断轨迹
R1(ultraverge评议, 3并行)={6 阻断} → Executor修复 → R2(收敛)={0 阻断}，单调下降。

## 3. Antipattern 巡查
| Round | 类型 | 对象 | 触发结果 |
|-------|------|------|---------|
| R1-R1 | data_tool_coupling | _BUILTIN_DEFAULT_COMMANDS 硬编码 | R1 修复：移至 config.py 单一源 |
| R1-R1 | environment_lock-in | Windows .exe 在安全模块中硬编码 | 已移除（统一到配置层） |
| R1-R1 | identity_crisis | whitelist vs grant/permission 术语分裂 | suggestion 级别，未阻断 |

## 4. Executor 路径依赖评估
无 over_compromise / solution_anchoring / minimum_patch 触发。Executor 逐条修复，未出现敷衍模式。

## 5. Reviewer 间 Verdict 分歧分布
| 轮次 | Verdict | 阻断数 | 归因分布 |
|------|---------|--------|---------|
| R1-R1 | 阻断需修复 | 4 | 全部 plan_defect |
| R1-R2 | 阻断需修复 | 3 | 全部 plan_defect |
| R1-R3 | 阻断需修复 | 5 | 全部 plan_defect |
| R2 | 可执行 | 0 | N/A |

## 6. 降级影响评估
Inner loop 降级为 orchestrator 逐条验收（OpenCode task tool 不支持 Continue）。6 条 fix 中 3 条可机械验证（代码顺序、单一源、子类定义），3 条需语义验证（consume 集成、regex 替换、opt-out flag）。语义验证由 orchestrator 完成，可信度略低于独立 Reviewer 验证，但 R2 独立 Reviewer 的 escalated_issues_verification 已对全部 6 条做独立确认。

## 7. 经验教训
1. **并行 Reviewer 交叉命中率**：3/3 Reviewer 命中 check_target_window 顺序和双重默认命令，验证了 ultraverge 多条独立视角对安全关键 bug 的捕获价值
2. **计划代码块风险**：plan 内嵌的伪代码在多处存在假设（如 `_extract_window_class_from_error` 未定义），执行时仍需补全——建议标注 `非规范`
3. **术语一致性是深层信号**：whitelist vs exception vs grant/permission 的术语分裂在 R1 被标记为 identity_crisis，是模块边界不够清晰的症状

## 8. 后续建议
- **高优先级**：设计审查发现的 `_extract_window_class_from_error` 缺失需在执行前补全
- **中优先级**：config.yaml 写入改用 ruamel.yaml 以保留注释
- **低优先级**：统一命令匹配算法（`_match_command` + `_static_whitelist_check` 去重）

## 9. Round 0 合同谈判评估
| 维度 | 评估 |
|------|------|
| 是否启用 | 否（跳过理由：用户直接 ultraverge 评审，跳过 contract negotiation） |
| contract 是否减少预期错位 | N/A |
| contract_amendment 触发次数 | N/A |

## 10. Rubrics 评估
未启用（无 contract → 无 rubric dimensions）。

## 11. 设计审查后修订

### 修订 1
- **触发来源**：用户要求 "进一步修订计划"（design review highlights）
- **触发时间**：R2 收敛完成后
- **输入摘要**：设计审查发现 3 个 highlights + 6 个维度 concerns
- **影响范围**：SafetyError 子类定义、mcp_server.py 错误处理、consume helper、Known Limitations 节、Self-Review Checklist
- **修正项**：
  1. `SensitiveProcessError`/`SensitiveWindowError` 携带 `process_name`/`class_name` 属性
  2. `_allowed_commands()` Task 2 stub → Task 5 正式版交叉引用
  3. `key_sequence` → `key_combo` 工具名修正
  4. `consume_window_exception(None,None)` 文档化 trade-off
  5. `yaml.safe_dump` 注释丢失标注
  6. 新增 "Known Limitations" 节（线程安全、匹配重复、工具感知）
- **结论变化**：无方向变化，6 项修正均为 plan 内微调
## 12. 设计审查摘要
1. **`yaml.safe_dump` 破坏注释**：permanent 写入会丢失用户 config.yaml 注释 — 建议 ruamel.yaml 或独立文件
2. **`consume_window_exception(None,None)` 过度消费**：多窗口工作流中第一个交互消耗所有 one-shot token
3. **`_extract_window_class_from_error` 未定义**：结构化错误响应的 class_name/process_name 字段无提取来源

用户决策：待确认后进入执行阶段。

## 成本数据
| 阶段 | agent 数 | 关键产出 |
|------|----------|---------|
| R1 评议 (ultraverge) | 3 (并行) | 6 阻断问题清单 |
| R1 修复 (Executor) | 1 | plan 修订（6 fixes） |
| R2 收敛 | 1 | escalated_issues_verification + 可执行 verdict |
| 设计审查 | 1 | design-review.md |
| **总计** | **6 agent** | — |
