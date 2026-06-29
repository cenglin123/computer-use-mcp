# MCP 项目技能策展闭环

> 状态：draft | 创建：2026-06-30

## 背景

**已有能力**：
- `trace.py`：每次 MCP 工具调用写入 JSONL（步骤、工具、参数、截图、错误、耗时）
- `review.py`：确定性轨迹摘要（错误分布、重试数、耗时，第 91 行留有 `improvement_suggestions_placeholder`）
- `SKILL.md`：computer-use 的核心技能文件（252 行，手写）—— **Phase 1 不涉及 SKILL.md 结构的任何变更**
- `.agents/memory/MEMORY.md`：19 条手工沉淀的教训（编号 `#1`–`#19`）
- converge SKILL：已部署，可用于质量门控

**缺失**：轨迹收集后没有自动反馈回 MEMORY 的机制。当前 19 条教训全是手动写的——每次踩坑后人工总结并写入 MEMORY。重复错误模式、模糊教训、过时教训均无法被自动发现和修正。

**目标**：构建一个**自动化的轨迹→教训→MEMORY 更新的闭环**（Phase 1 仅针对 MEMORY.md；不依赖 RL 训练，用 converge 替代学习）。

## 核心设计

### 1. 架构概览

```
Task → trace.py → review_task (确定性摘要)
                        │
                        ▼ (积累 N 条轨迹后触发)
                 ┌─────────────────────────┐
                 │  curator.py (LLM CLI)   │
                 │  输入：轨迹 + 摘要       │
                 │       + 当前 MEMORY.md   │
                 │  输出：建议的操作(JSON)   │
                 │  insert/update/delete    │
                 │  按 MEMORY.md 编号标识    │
                 └────────┬────────────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │  Converge 门控   │
                 │  (标准审议)       │
                 │  R1: 忠实度      │
                 │  R2: 泛化性      │
                 │  R3: 无冗余/冲突 │
                 └────────┬─────────┘
                          │ 人工审批通过
                          ▼
                 写入 .agents/memory/MEMORY.md
                 (SKILL.md 变更 deferred)
```

### 2. LLM API 规范
| 参数 | 值 |
|------|-----|
| Provider | 由环境变量指定（`LLM_API_BASE`，默认推测为 OpenAI 兼容接口） |
| 默认模型 | 当前执行 MCP 的 Agent 模型（自动检测：优先取环境变量 `CURATOR_MODEL`，否则取推测值 `deepseek-v4-flash`） |
| 认证 | 环境变量 `LLM_API_KEY`（兼容 OpenAI / Anthropic / 本地接口，由 `LLM_API_BASE` 切换） |
| 超时 | 请求超时 60s，连接超时 10s |
| 重试策略 | HTTP 429/503 → 指数退避（初始 2s, 最大 30s, 最多 3 次）；其他错误直接失败 |
| 成本控制 | 每次 curator 运行前估算 token 成本并输出提示；单次运行预算上限 $0.50，超出时需用户确认 |
| 成本追踪 | 每次运行结果输出 `total_cost_estimate_usd` 字段；累计成本记录到 `~/.computer-use/curator_cost_log.jsonl` |
| 模型回退 | 不自动回退；如主模型不可用，操作员可手动指定 `--model` 参数切换。兜底推荐：`deepseek-v4-flash` |

### 3. 输出鲁棒性
curator.py 的 LLM JSON 输出需经过以下验证：
- **Schema 校验**：JSON 结构是否匹配 Phase 1 定义的 schema（使用 Pydantic 或 jsonschema 库）
- **索引有效性**：update/delete 操作的 `lesson_index` 是否在当前 MEMORY 条目范围内
- **证据完整性**：每条提议的 `evidence_trace_ids` 必须指向实际存在的 trace 文件
- **拒绝处理**：上述任一校验失败时，提议标记为 `invalid`，不阻断其他合法提议
- **连续失败处理**：连续 3 次 curator 运行输出均无法通过 schema 校验 → 跳过本轮运行，输出警告日志给操作员

### 4. 轨迹数据隐私与安全
- **需注意**：trace 数据可能包含敏感信息（窗口标题、文件路径、错误消息、用户输入文本）
- **包含的字段**：`tool_name`, `args`（仅参数名和类型，不传敏感值如密码/密钥字段）、`error_kind`、`retry_count`、`duration_ms`
- **排除的字段**：`args` 中标记为 `sensitive: true` 的值字段、完整 `type_text` 内容（仅传字符数）
- **清理措施**：发送给 LLM 前，对 `args` 中可能包含路径/文件名的字段做路径正则脱敏（`C:\Users\*\...` 替换为 `<USER_DIR>\...`）
- **操作员注意**：converge 审查阶段，操作员需要确认没有敏感数据泄露至 reviewer prompt

## 关键设计决策

### 1. Curator 形态：prompt-based LLM，不训练模型
- 一个独立的 Python 脚本 `scripts/curator.py`，调用 LLM API 读取轨迹并提议教训
- 不支持 RL 训练（成本不可行），改用 converge 在推理期保证输出质量
- curator 角色借鉴 SkillOS 的 insert / update / delete 语义，但输出标识符适配 MEMORY.md 的编号体系（见 §输出格式）

### 2. 成功/失败信号：三层递进
| 层 | 信号来源 | 可靠性 |
|----|---------|--------|
| 第一层（已有） | `error_kind` 非空、`retry_count > 0` | ✅ 硬信号 |
| 第二层（需实现） | LLM-as-judge 读完整轨迹判断任务是否成功 | ⚠️ 软信号 |
| 第三层（理想） | 环境验证（文件是否存在、窗口是否出现） | ✅ 硬信号，但需逐个任务定制 |

首期：先用第一层 + `finish_task` 是否被调用作为成功/失败判据。

### 3. 触发机制：纯 CLI 命令（无守护进程/无文件监听）
- 形态：`python scripts/curator.py --trace-dir <path> [--count N] [--threshold T]`
- CLI 为有意简化设计：不设守护进程、无文件监听器、无 MCP server hook
- 默认配置：batch_threshold N=5（积累触发）、error_threshold T=3（异常触发）
- N 和 T 可通过 CLI 参数或 `config.yaml` 覆盖，不硬编码
- curator 跨多条轨迹分析模式，而非逐条反应（类似 SkillOS 的任务分组思路）

### 4. 与 converge 的关系
curator 输出不是最终产物——必须走 converge **标准审议（standard deliberation）** 审计才能写入 MEMORY.md。

**编排者**：人类操作员。curator.py 输出 JSON 后，操作员手动（或通过脚本）将提议注入 converge 的 standard deliberation 工作流。converge 不自动批准。

**审议维度（converge rubric）**：
- **忠实度**（Fidelity）：每条提议教训必须引用至少一条轨迹步骤作为证据。converge reviewer 核查引用的步骤是否确实支持该教训。
- **泛化性**（Generalization）：教训不应过度绑定具体窗口名/屏幕坐标/时间戳。reviewer 标记过度具体的教训并建议泛化。
- **无冗余/冲突**（Non-redundancy）：新教训不应与现有 MEMORY 条目重复或矛盾。reviewer 检查语义重叠。

**审批产出**：converge 通过后，diff 形式的 MEMORY.md 修改清单由操作员确认，然后由 `scripts/curator.py --apply` 或独立脚本写入 MEMORY.md。

## 实现步骤

### Phase 1：基础 curator 脚本
- [ ] `scripts/curator.py`：读取指定 trace_dir 下最近的 N 条轨迹，调用 LLM，输出 JSON 格式的教训提议
- [ ] curator prompt：参考 SkillOS 论文的 prompt 结构（见「参考」节），适配 MCP 场景
- [ ] 输出 JSON schema：

```json
{
  "proposals": [
    {
      "action": "insert" | "update" | "delete",
      "target": {
        // insert: 不指定 target，默认追加到列表末尾
        //         或指定 after_index: int（在某条目后插入）
        // update/delete: lesson_index: int（MEMORY.md 的 #N 编号）
        "lesson_index": null  | int,
        "after_index": null  | int
      },
      "content": "教训正文（markdown 段落）",
      "evidence_trace_ids": ["trace-uuid-1", "trace-uuid-2"],
      "rationale": "为什么这个教训应该被采纳"
    }
  ],
  "metadata": {
    "trace_count": 5,
    "curated_at": "2026-06-30T12:00:00Z",
    "model": "<运行时实际检测的模型标识符, e.g. deepseek-v4-flash>",
    "total_cost_estimate_usd": 0.15
  }
}
```

**索引漂移处理**：当单批次包含多个操作时，按以下规则处理以避免索引错位：
1. 先处理所有 `delete` 操作（从大到小索引顺序，避免重编号干扰）
2. 再处理所有 `update` 操作（按索引，此时索引已稳定指向最终条目）
3. 最后处理所有 `insert` 操作（按 `after_index` 排序，从后往前插入）

如果 `lesson_index` 超出当前 MEMORY 条目范围，该提议标记为 `invalid` 并提示人工处理，不做静默修正。

**输出文件路径**：curator 每次运行产生一个时间戳命名的 JSON 输出文件，默认路径为 `~/.computer-use/curations/<timestamp>.json`。可通过 `--output <path>` CLI 参数覆盖。`--apply` 模式默认读取 `~/.computer-use/curations/` 下最新的文件（按时间戳排序），也可通过 `--input <path>` 指定特定文件。

**MEMORY.md 解析说明**：curator 读取 MEMORY.md 时解析 `## 已验证的重要教训` 章节下的编号列表（`1. ...`, `2. ...`）。此为最佳努力（best-effort）markdown 解析，依赖以下假设：
- 教训条目位于指定标题下，格式为 `1. 内容`（标准 markdown 编号列表）
- 无嵌套列表或列表中间穿插非列表段落
- 索引按文档中出现顺序从 1 开始递增
解析失败时应中止运行并输出明确错误消息，而非静默跳过或损坏文件。**建议在 `--apply` 写回前人工审查 diff 结果**，因为编号列表的格式偏差可能导致写入位置错误。

### Phase 2：成功/失败信号
- [ ] 实现 LLM-as-judge：读完整轨迹 → 判断任务是否成功（参考 SkillOS 论文的 prompt 结构，见「参考」节）
- [ ] 将判断结果写入独立文件 `<trace_dir>/<trace_id>/judgment.json`，格式如下：
```json
{
  "trace_id": "uuid",
  "verdict": "success" | "failure" | "ambiguous",
  "confidence": 0.95,
  "reasoning": "任务成功创建了文件 xyz.docx 并验证了内容",
  "judged_at": "2026-06-30T12:00:00Z"
}
```

**依赖关系**：Phase 1 不依赖 Phase 2。Phase 1 的默认成功/失败信号使用已有的 `finish_task` 是否被调用 + `error_kind` 非空判断。Phase 2 仅作为可选的软信号增强，在 Phase 1 验证通过后再实现。

### Phase 3：触发与收敛集成
- [ ] CLI 入口：`python scripts/curator.py --trace-dir <path> [--count 5] [--error-threshold 3] [--apply]`
  - 不设守护进程、无文件监听器、无 git hook
  - 操作员手动运行，或在任务批量完成后通过脚本调用
- [ ] converge 集成流程：
  1. 操作员运行 `curator.py` 生成 `curator_output.json`
  2. 操作员将 JSON 导入 converge 标准审议工作流
  3. converge reviewer 按三维度（忠实度/泛化性/无冗余）审查
  4. 操作员根据 reviewer 意见确认或拒绝修改
  5. 通过后，操作员运行 `curator.py --apply` 将 approved diff 写入 MEMORY.md
  6. 操作员更新 CHANGELOG 并提交
- [ ] 回写 MEMORY.md：按 approve 的结果应用 insert/update/delete
  - 索引漂移规则参考 Phase 1 定义
  - 仅在 `--apply` 模式下执行实际写入；默认模式仅输出 JSON 供审查

### Phase 4：测试与验证
- [ ] **回放测试**：从历史 trace 中选取至少 10 条包含已知错误模式的轨迹（如重试链、超时、窗口未找到等），运行 curator。验收标准：curator 必须从中提取至少 **3 条可操作的教训**（actionable，即有具体改进建议而非泛泛描述），且每条教训必须引用实际 trace 步骤作为证据。
- [ ] **无假阳性验证**：在至少 5 条确认成功的轨迹上运行 curator，确认 curator 不会凭空编造不存在的教训（预期输出：proposals 为空或仅含低置信度推测，不含无证据支撑的虚构教训）。
- [ ] **Blind 测试**：使用旧版 MEMORY.md（例如移除最近 3 条手工沉淀的教训后），运行 curator 并检查输出是否捕捉到这些已被验证的教训。通过标准：至少 2/3 的被移除教训被 curator 重新发现，且不会提出与剩余条目矛盾的教训。
- [ ] **收敛验证**：上述测试中 curator 输出的 JSON 须通过 Phase 1 定义的 schema 校验和索引有效性检查。任何输出格式问题视为测试失败，需修复后才能进入生产使用。

## 不做的事

- ❌ 不训练 curator 模型（RL/GRPO 方案）
- ❌ 不改 MCP server 核心逻辑（curator 是外挂脚本）
- ❌ 不动 SKILL.md 的底层结构——**Phase 1 完全不涉及 SKILL.md**。SKILL.md 的结构变更（如为 lesson 条目增加结构化元数据）推迟到未来阶段。curator 的写入目标仅限于 `.agents/memory/MEMORY.md`。
- ❌ 不设守护进程或文件监听器——触发机制是独立 CLI 命令，由操作员手动调用
- ❌ 不实现自动批准——所有 MEMORY.md 修改必须经过 converge 审查 + 操作员确认

## 参考

- **SkillOS: Learning Skill Curation for Self-Evolving Agents** — Siru Ouyang, Jun Yan, Yanfei Chen, et al. (Google Cloud AI Research / UIUC / MIT). arXiv:2605.06614v1 [cs.AI], May 2026. https://arxiv.org/abs/2605.06614
    - 本计划的核心参考：frozen executor + trainable curator 的分离架构、任务分组构建训练实例、复合奖励设计。本计划将 curator 从 "RL 训练" 替换为 "prompt + converge 审计"，但任务分组思路、技能 Markdown 格式、insert/update/delete 操作语义直接沿用。
    - **论文笔记文件**：实现前需将论文笔记存放于 `<project_root>/docs/refs/skillos-notes.md`，内容应包含：
        - Figure 7 对应的 curator prompt 模板结构
        - Figure 13 对应的 LLM-as-judge prompt 模板结构
        - 任务分组 (task grouping) 的具体逻辑描述
        - insert/update/delete 操作的定义和约束
    - 若笔记文件不存在，curator prompt 设计应遵循以下自包含结构（摘自论文核心思路）：
        - **Curator prompt 骨架**：系统消息定义 curator 角色（分析轨迹 → 提炼可复用教训）；用户消息包含 N 条轨迹的 `review_task` 摘要 + 当前 MEMORY.md 全文；输出约束为 JSON 格式的 insert/update/delete 提议。
        - **LLM-as-judge prompt 骨架**：系统消息定义 judge 角色（判断任务是否成功）；用户消息包含完整轨迹步骤；输出 verdict ("success"|"failure"|"ambiguous") + confidence + reasoning。
- converge SKILL：https://github.com/cenglin123/converge-skill
- 项目当前 MEMORY：`.agents/memory/MEMORY.md`（19 条教训，编号 `#1`–`#19`）
- 占位符：`review.py:91` `improvement_suggestions_placeholder`——与 curator 的关系：后续版本 curator 可能消费此占位符的输出，Phase 1 不做此集成。
- 轨迹数据位置：trace 文件位于 `~/.computer-use/traces/`（由 `trace.py` 管理）
