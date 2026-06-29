# SkillOS 论文参考笔记

> 创建：2026-06-30 | 来源：arXiv:2605.06614v1 [cs.AI], May 2026

## 引用

**SkillOS: Learning Skill Curation for Self-Evolving Agents**  
Siru Ouyang, Jun Yan, Yanfei Chen, Rujun Han, Zifeng Wang, Bhavana Dalvi Mishra, Rui Meng, Chun-Liang Li, Yizhu Jiao, Kaiwen Zha, Maohao Shen, Vishy Tirumalashetty, George Lee, Jiawei Han, Tomas Pfister, Chen-Yu Lee  
Google Cloud AI Research / University of Illinois Urbana-Champaign / MIT  
<https://arxiv.org/abs/2605.06614>

## 与本项目的关系

SkillOS 是本项目 curator 脚本的核心参考。我们沿用其 **frozen executor + curator** 的分离架构、**task grouping** 思路、**insert/update/delete** 操作语义，但将 curator 从 "RL 训练的小模型" 替换为 "prompt + converge 审计的 LLM CLI 脚本"。

---

## 关键架构

### 分离设计

- **Frozen Agent Executor**（$\pi_L$）：冻结权重，用 BM25 从 SkillRepo 检索相关技能，结合技能执行任务
- **Trainable Skill Curator**（$\pi_S$）：观察 executor 的轨迹 + 自判对错 + 检索到的技能，输出结构化函数调用 `{insert_skill, update_skill, delete_skill}`

### 技能格式（本项目的对应物：MEMORY.md）

```
YAML frontmatter:
  name: <技能名>
  description: <一句话描述，用于未来检索>

Markdown 正文:
  # Workflow
  # When NOT to Use
  ... (curator 可自主生成新 section)
```

### 任务分组（Training Instance Construction）

不逐条训练——把相关任务串成一组。早期任务更新 SkillRepo，晚期相关任务评估更新效果。训练信号来自下游任务表现，而非单条轨迹。

---

## Curator Prompt 骨架（摘自 Figure 7）

```
# Role
You are an expert with a sophisticated skills curator. Our overall goal is to
accomplish agent tasks. Your primary task is to convert past experiences of
agent task execution into reusable, general skills, so that they can benefit
and inspire future tasks.

# Input Data
1. Task Description: The task to be accomplished.
2. Past Skills: A list of previously stored relevant skills, each with a
   skill name (identifier) and content.
3. Agent Trajectory: The step-by-step execution trace.
4. Result: Whether the agent successfully completed the task or not.

# Critical Constraints
- Skill Format: Extract and store important information as skills using
  following Markdown format strictly.
- No Specifics: Avoid problem-specific details. Remove specific
  numbers/names. Replace with variables/concepts.
- No Hallucination: Do not invent facts.
- Each skill must be Atomic, modular, and reusable.

# Action Guidelines
1. Analyze the agent trajectory and its result.
2. If trajectory is correct, extract reusable knowledge.
   If incorrect, identify failure point and extract skills to fix.
3. Compare extracted skills with past skills. Determine whether to
   insert, update, or delete.

# Available Tools (Figure 8)
new_skill_insert(skill_name: str, content: str)
skill_update(skill_name: str, new_name?: str, new_content?: str)
skill_delete(skill_name: str)
```

---

## LLM-as-Judge Prompt 骨架（摘自 Figure 13）

```
# Role
You are an expert judge evaluating whether an agent successfully completed
a task.

# Input
1. Task description
2. Full interaction trace (alternating observations and actions)

# Criteria
- Every condition stated in the task must hold at the end of the trace.
- If the trace is ambiguous about whether every required condition is
  satisfied → verdict = false.
- Partial completion = failure.

# Output
{
  "verdict": "success" | "failure" | "ambiguous",
  "confidence": 0.0-1.0,
  "rationale": "one or two sentences citing specific observations",
  "evidence_step": <integer step index, or -1 if failure>
}
```

---

## 复合奖励（公式 1）

$$r = r_{task} + \lambda_f r_{fc} + \lambda_u r_{cnt} + \lambda_c r_{comp}$$

| 分量 | 含义 | 本项目对应 |
|------|------|-----------|
| $r_{task}$ | 组内后续任务的平均成功率 | curator 的 batch 模式跨轨迹分析 |
| $r_{fc}$ | 函数调用合法性 | curator JSON schema 校验 |
| $r_{cnt}$ | 技能内容质量（外部 judge 打分） | converge reviewer 的忠实度/泛化性评分 |
| $r_{comp}$ | 技能库精炼度（惩罚照抄轨迹） | MEMORY.md 条目不应是轨迹的逐字拷贝 |

超参：$\lambda_f = 1.0, \lambda_u = 0.1, \lambda_c = 0.05$

---

## 关键实证发现

1. **小模型定向训练 > 大模型直接用**：8B Qwen3-8B 经 RL 训练后策展效果超过直接用 Gemini-2.5-Pro
2. **训练初期 insert 为主，中后期 update 上升**（Figure 4）：curator 逐渐从"疯狂积累"转变为"精炼打磨"
3. **技能内容随训练自主演化出新 section**（Figure 5）：如 `# Retry Logic`、`# Alternative` 等
4. **任务分组是最关键设计**（Table 3 消融）：去掉分组退化为随机序列 → 成功率跌幅最大
