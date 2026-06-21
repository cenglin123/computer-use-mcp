# 计划:规范化复盘报告(便于分发后收集用户反馈)

## 背景与目标

MCP 分发后,用户会遇到各种场景/问题。需要让用户在执行 MCP 的窗口里一句"总结一下复盘报告""复盘一下执行经过",agent 就能**根据当前会话已有执行信息**整理出一份**规范化**复盘报告,存到 `~/.computer-use/` 下固定位置,便于统一收集回流、指导我们调整。

关键诉求:**规范化**(格式统一可批量解析)+ **方便收集**(位置/命名固定)+ **信息足够**(maintainer 不必反复追问就能定位问题)。

## 核心设计决策(请评议拍板)

### 决策 1:工具 vs 纯指引 —— 推荐"混合(新增 MCP 工具)"

- **纯指引**:让 host agent 自己用框架的文件工具写 `.md`。轻,但**位置/格式必然漂移**(不同 model/客户端各写各的),且依赖 host 有写文件权限——与"规范化、方便收集"相悖。
- **混合(推荐)**:新增 MCP 工具 `save_review`。**agent 负责叙述/分析**(它独占会话的"思维过程"上下文),**工具负责标准化封装**:统一位置、统一命名、自动附带元数据与证据(时间戳、MCP 版本、`doctor` 环境快照、由 `task_id` 解析出的 trace/task 证据路径),返回落盘路径。既保留 agent 的丰富叙述,又锁死规范与可收集性,且不依赖 host 文件权限。

### 决策 2:输出格式 —— 仅 `.md`(YAML frontmatter 即机读)

- 仅 `.md` 单文件,头部 YAML frontmatter 承载结构化元数据。
- 无需 `.json` sidecar:frontmatter 即可被脚本解析聚合,且与项目现有约定一致(`docs/problems/bugfix/*.md` 使用同模式)。双份文件增加同步成本与文件计数,收益微薄。
- 若将来批量聚合需求明确(日收集 >50 份),可加脚本从 `.md` frontmatter 批量提取,不需要回溯加 `.json`。

### 决策 3:存放位置 —— 推荐 `~/.computer-use/reviews/`(扁平 + 时间戳命名)

- 与现有 `screenshots/`、`traces/`、`tasks/` 平级,新增 `reviews/`。
- 文件名:`review_<UTC时间戳>[_<task_id>].md`(扁平目录,低频,便于一键打包发送;不做日期分区以简化收集)。
- 通过 config 增加 `review_dir`,默认 `~/.computer-use/reviews/`,可被 `COMPUTER_USE_CONFIG`/环境覆盖(与其它 dir 一致)。

### 决策 4:是否自动附 `doctor` 环境快照 —— 推荐是

- `doctor` 输出平台/依赖/能力/目录可写性,**不含密钥**;但含用户名等路径信息。对"用户自愿反馈"场景可接受。评议确认隐私边界。

## 问题清单与影响文件

### A. 新增 `save_review` 工具实现

- 新增 `computer_use/review_report.py`(独立于现有只读 `review.py`,避免读写混层):`save_review(report_markdown, outcome, task_id=None, client=None, model=None) -> dict`。
  - 参数校验:
    - `report_markdown` 非空,最大 500KB(base64 不会出现在正文中,纯文本 500KB 对复盘报告足够宽松);超限返回 `{saved: false, error: "report_markdown exceeds max length"}`。
    - `outcome` **枚举受控**:`{"succeeded", "partial", "failed", "unknown"}`之一,用于批量聚合;传入非法值时回退 `"unknown"`。
  - 组装元数据:`created_at`(UTC ISO)、`mcp_version`(`importlib.metadata.version`,失败回退 "unknown",日志记录原因)、`outcome`、`client`、`model`、`task_id`。
  - 证据富集:有 `task_id` 时调用 `review.review_task_session(task_id, detail=False)` 取摘要 + 各 trace 的 `artifact_manifest` 路径,写入元数据(失败安全降级,不阻断落盘)。注意:SKILL 流程中 agent 可能已自行调过 `review_task_session(detail=true)` 获取详细证据,此处的 detail=false 调用是为工具层自动附加,不重复消耗 trace 能力。
  - 环境快照:调用 `doctor.run_doctor()` 取精简字段(平台、依赖、能力、版本),嵌入元数据。注明 `doctor_captured_at: <ISO timestamp>`——快照采集于报告生成时刻,并非会话执行时刻,避免"版本漂移"误导排障。
  - 多次调用的去重:同一 `task_id` 的二次调用覆盖先前文件(后写往往更好);无 `task_id` 的调用每次生成独立时间戳文件。
  - 落盘:`.md`(YAML frontmatter 元数据 + agent 正文)到 `review_dir`。
  - 返回 `{saved: true, review_path, review_dir}`;异常返回 `{saved: false, error}`,绝不抛未捕获异常。
  - 隐私说明:每个 `.md` 末尾追加 `<!-- This report was auto-generated. Contains paths, environment snapshot, and dependency info. Review before sharing. -->` 注释行,避免用户不经审查直接转发。
- `computer_use/config.py`:新增 `review_dir` 默认与目录创建。

### B. 注册工具

- `computer_use/tools/schemas.py`:新增 `Tool(name="save_review", ...)`。描述写明:
  - 用途:将复盘报告规范化为 `.md` 文件存入固定位置,自动附加元数据与环境快照。
  - `outcome` 参数为枚举 `["succeeded", "partial", "failed", "unknown"]`。
  - `report_markdown` 最大 500KB。
  - **提示**:此工具与 `review_task`/`review_task_session` 不同(后两者是读 trace 数据的确定性摘要),`save_review` 是写复盘报告。
- `computer_use/tool_contract.py`:**不**加入 `ATOMIC_AND_COMPOSITE_TOOL_NAMES`(它是顶层反馈工具,不应作为 batch/task 嵌套步骤);与 `review_task` 同类。
- `computer_use/mcp_server.py`:`_dispatch_tool` 加 `save_review` 分支。
- `computer_use/tools/schemas.py`(而非 mcp_server.py):将 `save_review` 加入 `_TASK_CONTEXT_EXCLUDED_TOOLS`(`_TASK_CONTEXT_EXCLUDED` 集定义在 schemas.py 第 15 行),使其**不受 `missing_task_id` 守卫约束**(复盘是元操作,可在有/无 active task 时独立调用)。

### C. SKILL 指引(触发 + 模板)

- `skills/computer-use/SKILL.md`(改后 `Copy-Item` 同步 `.agents/`):新增 "Retrospective Reports" 小节:
  - **触发**:用户说"复盘/总结复盘报告/复盘执行经过"等时,执行此流程。
  - **采集**:从当前会话叙述执行经过;若本会话有 `task_id`,先 `review_task_session(task_id, detail=true)` 取结构化证据。
  - **模板**(标准化章节,分必填/选填):
    - **必填**:任务目标 / 执行时间线(关键步骤与工具调用,非全部 enumerate) / 结果(从 `succeeded`/`partial`/`failed` 选) / 失败与现象(含 `error_kind`,失败/partial 时必填) / 证据路径;
    - **选填**(不适用时写 N/A):有效之处 / 根因假设 / 改进建议 / 客户端+模型(如实传参,不可靠时填 `None`,工具层回退 `"unknown"`) / 备注。
  - **落盘**:调用 `save_review(report_markdown=<填好的模板>, outcome=<succeeded|partial|failed|unknown>, task_id=..., client=..., model=...)`,把返回的 `review_path` 告知用户,提示：
    - 可将该文件通过聊天窗口发送、附加到 GitHub Issue、或邮件附件反馈给维护者。
    - 文件中包含用户名/路径等环境信息,分享前可预览脱敏。
  - Tool Quick Reference 表补 `save_review` 一行。

### D. 文档

- `docs/api.md`:`save_review` 工具约定 + 输出结构 + 证据/环境富集说明。
- `docs/deployment.md`:`reviews/` 位置、收集方式(把 `~/.computer-use/reviews/` 下文件发回);「持久化与备份」补一条 `reviews/`。
- `CHANGELOG.md`:当天节追加。

### E. 测试

- `tests/`:`save_review` 单测(mock `doctor`/`review_task_session`):无 task_id 也能落盘;有 task_id 富集证据;`.md` 包含正确 YAML frontmatter;元数据含 version/created_at/outcome/doctor_captured_at;证据富集失败时安全降级仍落盘;空 `report_markdown` 报错;`report_markdown` 超 500KB 报错;非法 `outcome` 回退 `"unknown"`;同一 `task_id` 二次调用覆盖旧文件。
- dispatch 路由测试 + `test_tools_listed` 更新 + `save_review` 在 `_TASK_CONTEXT_EXCLUDED_TOOLS`(active task 下无 task_id 不被拒)。

## 验收标准

- [ ] 用户无 task_id 时也能成功生成报告(复盘不强依赖业务任务会话)。
- [ ] 有 task_id 时报告自动带 trace/task 证据路径与会话摘要;同一 task_id 二次调用覆盖旧文件。
- [ ] 仅 `.md` 单文件,带 YAML frontmatter,落在 `~/.computer-use/reviews/`,命名含时间戳。无 `.json` 文件产生。
- [ ] `outcome` 受控为 `succeeded`/`partial`/`failed`/`unknown`;非法值回退 `"unknown"`。
- [ ] `report_markdown` 超 500KB 返回明确错误,不落盘。
- [ ] 富集(doctor/评审)任一失败都安全降级,主报告仍落盘。
- [ ] doctor 快照标注 `doctor_captured_at: <timestamp>`,表示采集于报告生成时刻而非会话执行时刻。
- [ ] `.md` 末尾含隐私说明注释,提示用户名/路径/依赖等信息。
- [ ] `save_review` 不受 `missing_task_id` 守卫约束;不进 batch/task 嵌套白名单。
- [ ] `pytest tests/` 全绿;SKILL 双副本一致;新增单测覆盖上述分支。
- [ ] 报告不含密钥;不包含环境变量和 config.yaml 内容。
- [ ] reviewer 视角:工具注册三处一致、dispatch 路由正确、模版分必填/选填不与现有规则冲突。

## 不做(范围外)

- 不做自动上传/联网回传(仅本地落盘 + 用户手动反馈;联网回传涉及隐私与网络,另立项)。
- 不做报告的 GUI 查看器。
- 不改现有 review_task / review_task_session 行为(仅复用)。
- 不在 batch/run_task_plan 内联调用 save_review。

## 评议确认记录

> ultraverge 评议结论,三项均采纳。

| 决策 | 方案初提 | 评议结论 | 说明 |
|------|----------|----------|------|
| 1. 工具 vs 纯指引 | 工具(混合) | **工具(混合)** | 工具锁格式,agent 写叙事。一致通过 |
| 2. `.md`+`.json` 双份 | 双份 | **仅 `.md`** | YAML frontmatter 即可机读,无需双份维护。多数裁决(2:1) |
| 3. doctor 环境快照 | 包含 | **包含+隐私标注** | 需在末尾加隐私说明 + 标注 `doctor_captured_at` 防版本漂移 |
| 4. 扁平 vs 日期分区 | 扁平 | **扁平** | 低频场景下扁平足够,一键打包方便。一致通过 |

### 其他采纳建议

- `outcome` 改为枚举 `{succeeded, partial, failed, unknown}`(用于批量聚合)
- `report_markdown` 最大 500KB,超限拒绝
- `review_report.py` 独立于 `review.py`(读写混层不推荐)
- 10 节模板缩减:分必填 5 节 / 选填 5 节,选填不适用写 N/A
- 同一 `task_id` 二次调用覆盖旧文件
- `_TASK_CONTEXT_EXCLUDED_TOOLS` 引用修正为 schemas.py(非 mcp_server.py)
- 命名澄清:save_review 在 schema description 中明确与 review_task/review_task_session 不同
