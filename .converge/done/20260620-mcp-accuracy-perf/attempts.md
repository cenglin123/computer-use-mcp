# Attempt Log · 20260620-mcp-accuracy-perf

## Round 1 attempt · issue 1
- source: converge_loop
- reviewer_backend: opencode
- Issue: 主线 C（复盘 detail/export）没有确定性的 API 设计。执行项 2 写"增加可选或默认的 steps 明细"——executor 无法判断 step detail 应该 (a) 始终包含在 review_task 的默认返回中、(b) 通过 opt-in 参数控制、还是 (c) 仅通过新增 `tasks export --detail` CLI 子命令暴露。Plan 完全没有提及已存在的 generate_deterministic_report(review.py:91) 和 trace.generate_report(trace.py:353-427)。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 落定 API 设计为 `review_task(detail: bool=False)` + `review_task_session(detail: bool=False)` 的 opt-in JSON steps；承认已有 markdown report 不改动；解释 markdown vs JSON 分工；更新验收标准和测试建议引用具体 `detail=True` 参数。
- Diff: 主线 C 整体重写；测试建议更新；验收标准更新
- R1 verdict: Accepted (R2 reviewer 确认 resolved)

## Round 1 attempt · suggestion 1-5 + antipatterns
- source: converge_loop
- reviewer_backend: opencode
- Issue: 5 条 suggestion（80k token 不可观测 / Kimi 模型专属 / guidance step 6 关系未说明 / P2 无根因 / api.md 或 overview.md 歧义）+ 2 条 antipattern（false_generality 标题 / environment_lock-in 绝对路径）
- Issue 归因（reviewer 判定）: plan_defect (suggestions, non-blocking)
- plan_amendment_required: true
- Approach: 背景段加范围说明修正标题预期；主线 A 加 pre-click 互补说明+指定 docs/api.md；主线 B 删除 80k token 条件改可观测信号+删除 Kimi 改模型无关；P2 标延期+加根因；相关文件拆分改动目标 vs 证据引用+环境变量引用
- Diff: 背景、主线 A/B/D、P2、根因表、相关文件等多处编辑
- R1 verdict: Accepted (R2 reviewer 确认 resolved)

## Round 2 attempt · issue 1 (new blocking)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Track C 的 session-level detail 在 MCP 层无法生效。MCP 分发路径（mcp_server.py:884）调用 _review_task_session_result(task_id)（mcp_server.py:414-426），该函数直接返回裸 task 元数据，不经过 review.py 聚合逻辑。review_task_session() 仅被 CLI 调用。mcp_server.py 和 tools/schemas.py 未在文件清单中。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将 mcp_server.py + tools/schemas.py 加入清单；新增"MCP 分发路径与统一"子节，落定方案：删除 _review_task_session_result，分发直接委托 review.review_task_session(detail=...)；执行项扩为 8 项；验收标准删除"或等价"兜底改为 MCP 等价性验证；测试建议新增 test_mcp_server.py
- Diff: 范围说明、Track C 新子节、执行项、验收标准、相关文件、测试建议
- R2 verdict: Accepted (pending R3 reviewer 独立验证)

## Blind Recheck 1 attempt · issue BR-1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: 计划中存在多处 A1 类修复痕迹（archaeology_leftover）——line 226 "无需再用'或等价'措辞兜底"、line 173 "API 设计决策（已确定，不再留多选）"、line 202 "统一方案（已确定，不留多选）"。暴露修复历史，对 fresh 读者不透明。
- Issue 归因: pending
- plan_amendment_required: false
- Approach: 重写 3 处措辞去除历史引用（"（已确定，不再留多选）"→删除括注；"或等价措辞兜底"→直接陈述验证内容）；执行项 4 收敛为单一路径（提升为独立 if 分支）；trace.py/task_session.py 移至"接口依赖"子节
- Diff: line 173 标题、line 202 标题、line 226 验收项、line 216 执行项 4、相关文件清单
- Blind verdict: Accepted (R4 fresh reviewer 确认 + attribution 落定 plan_defect; R5 + blind recheck 2 最终确认)
