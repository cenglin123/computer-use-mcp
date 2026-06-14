# Dynamic Workflow SKILL 复盘报告

> 报告人：本次 MCP GUI 自动化改进计划的执行 agent  
> 执行环境：Kimi Code CLI（非 Claude Code / Codex / opencode）  
> 任务规模：5 个实现 Phase + 2 轮 converge 验收，最终 145 个测试通过

## 一、执行背景

本次任务要求：

1. 执行已通过 converge 评审的 `docs/plans/active/mcp-gui-automation-improvements.md`；
2. 使用 **dynamic workflow SKILL** 调度整个执行阶段；
3. 完成后进行 converge 验收。

我按 SKILL 指引创建并维护了 `.workflow/20260613-execute-plan/state.json`，按顺序 spawn 了 5 个 implementer subagent，每轮执行后运行 pytest 作为质量门控，最后 spawn 验收 reviewer。

## 二、SKILL 宣称的能力

根据 SKILL 原文，dynamic workflow 的核心价值是：

> “把编排计划写进代码，而非留在对话上下文。脚本持有循环、分支和中间结果，主对话只保留最终答案。”

它提供四个抽象原语（Spawn / Wait / Continue / Identify）、scheduler.py / executor.py 的执行框架、以及“编排者责任清单”和“质量门控检查清单”。

## 三、实际使用情况

### 3.1 真正用到的部分

| 能力 | 是否使用 | 实际作用 |
|------|---------|---------|
| Spawn 原语 | ✅ | 通过 Kimi Code `Agent` 工具顺序 spawn 5 个 implementer 和 2 个 reviewer |
| Wait 原语 | ✅ | 每个 `Agent` 调用默认阻塞等待结果 |
| state.json 外化 | ✅ | 手动创建并更新 `.workflow/.../state.json` |
| 质量门控 | ✅ | 每 Phase 后运行 `pytest tests/ -v` |
| scheduler.py / executor.py | ❌ | 项目未提供，Kimi Code 也无法从脚本中调用 `Agent` 工具 |
| group/report/budget guard | ❌ | 未使用 |

### 3.2 实际执行流

实际上的控制流是：

```
Agent(Phase 1 implementer) → pytest → 手动更新 state.json
Agent(Phase 2 implementer) → pytest → 手动更新 state.json
...
Agent(Final acceptance reviewer) → 修复阻塞问题 → 再次 reviewer → 通过
```

这里的顺序和门控**完全依赖我（LLM）记住并执行**，没有任何外部脚本强制推进。

## 四、核心问题：SKILL 在当前环境下是“软约束”

### 4.1 没有硬调度能力

SKILL 宣称的“脚本持有循环、分支和中间结果”在 Kimi Code 中无法实现，因为：

- `Agent`/`AgentSwarm` 是 LLM 对话层的工具，**外部 Python 脚本无法调用**；
- 不存在一个 scheduler 进程能读取 state.json 后自动触发下一个 agent；
- 即使写了 `scripts/scheduler.py`，它也只能打印建议，下一步仍要 LLM 决定。

因此 state.json 的更新、phase 的推进、质量门控的运行，全部依赖**模型是否记得做**。这与 TODO list 没有本质区别，反而多了一个需要读写的外部文件。

### 4.2 看板价值 > 调度价值

在本次执行中，state.json 的实际价值主要是：

- **对外展示进度**：给用户一个清晰的 Phase 完成度看板；
- **事后审计**：记录每个 phase 的测试数字；
- **心理仪式感**：让执行看起来是“workflow 驱动”。

但它**没有防止任何错误**：例如我理论上可以跳过 Phase 3 直接做 Phase 4，state.json 不会阻止我；我也可以忘记更新它而继续执行。

### 4.3 与 TODO list 相比没有优势

Kimi Code 原生 `TodoList` 工具：

- 每次调用后系统会提醒更新；
- 自动显示在对话中，状态一目了然；
- 不需要额外文件 I/O；
- 同样是软约束，但维护成本更低。

相比之下，dynamic workflow 的 state.json 需要：

- 额外创建目录和文件；
- 每轮手动读取当前状态；
- 每轮手动写入新状态；
- 容易出现 state 与真实进度不一致。

### 4.4 文档假设与 Kimi Code 能力不匹配

SKILL 大量引用 `scripts/scheduler.py`、`scripts/executor.py`、`.workflow/` 目录，并强调“非 CC 框架用户”才需要。但 Kimi Code：

- 不是 Claude Code，没有原生的 Workflow API；
- 也不是 opencode/codex CLI，无法让外部脚本调用 agent；
- 有原生 `Agent`/`AgentSwarm` 工具，但它们是 LLM 层的能力，不能被脚本编排。

SKILL 没有说明在 Kimi Code 这种“有 Agent 工具但无脚本调度能力”的环境下应该如何降级使用，导致我难以判断哪些部分必须遵守、哪些可以省略。

## 五、对比：SKILL 宣称 vs 实际

| 维度 | SKILL 宣称 | 本次实际 |
|------|-----------|---------|
| 状态由脚本持有 | ✅ 是 | ❌ 由 LLM 维护 JSON 文件 |
| 下一步自动决定 | ✅ 是 | ❌ LLM 决定 |
| 质量门控自动执行 | ✅ 编排者责任 | ⚠️ LLM 手动运行 pytest |
| 防止跳过 phase | ✅ 隐含 | ❌ 无法防止 |
| 维护成本 | 低（代码驱动） | 中（额外 JSON + 手动同步） |
| 对执行效率的提升 | 高 | 不明显，甚至略分散注意力 |

## 六、建议

### 6.1 针对 SKILL 本身的建议

1. **明确区分“硬约束 workflow runtime”与“软约束 workflow 模板”**
   - 如果框架没有外部 scheduler 能力，应直接说明："在 Kimi Code 等环境中，本 SKILL 退化为手动编排模板，无法强制调度。"

2. **增加 Kimi Code 适配章节**
   - 说明 Kimi Code 的 `Agent`/`AgentSwarm` 无法被脚本调用；
   - 给出最小可行用法：用 `TodoList` 做状态跟踪 + 用 `Agent` 顺序执行 + 每步后主动运行验证命令。

3. **减少不必要的 artifact 要求**
   - 在无法强制调度时，不必要求创建 `.workflow/state.json`；
   - 或者将其定位为“可选审计日志”而非“状态机”。

4. **强化质量门控的实战模板**
   - 提供可直接复制的门控脚本/命令（如 `pytest tests/ -v`）；
   - 说明门控失败后如何回滚/重试。

### 6.2 针对 Kimi Code 用户的建议

在 Kimi Code 中，dynamic workflow 的核心收益可以保留为：

- **Phase 拆分**：把大任务拆成多个独立 subagent 任务；
- **质量门控**：每 Phase 后运行相关测试；
- **验收闭环**：最后 spawn 独立 reviewer。

但不必维护 state.json。更轻量的模式是：

```
TodoList 跟踪 phase 状态
  ↓
Agent(Phase N implementer)
  ↓
Bash(质量门控：pytest / lint / compile)
  ↓
更新 TodoList
  ↓
循环直到全部完成
  ↓
Agent(独立 acceptance reviewer)
```

## 七、结论

本次执行最终成功（145 passed，验收通过），但成功主要来自于：

- 清晰的前期计划；
- Kimi Code 原生 Agent 工具的子任务拆分；
- 每 Phase 后的 pytest 质量门控；
- 最终独立 reviewer 的 converge 验收。

**dynamic workflow SKILL 在本次 Kimi Code 环境下并未提供额外的硬约束或自动调度能力**。它更像是一个“如何组织多 agent 任务”的指导原则，而其具体落地（state.json、scheduler.py）在当前环境下属于 overhead，维护收益不明显。

如果 SKILL 的目标是让所有支持 Agent 的框架都能获得 workflow 能力，那么它需要针对“脚本无法调用 agent”的环境给出明确降级策略；否则用户会像我一样，多维护了一个好看的看板，却没有获得真正的调度控制力。

---

**附件**

- 执行状态：`.workflow/20260613-execute-plan/state.json`
- 首次验收报告：`.workflow/20260613-execute-plan/acceptance-review.md`
- 最终验收报告：`.workflow/20260613-execute-plan/acceptance-review-final.md`
- 执行回顾：`.workflow/20260613-execute-plan/retrospective.md`
