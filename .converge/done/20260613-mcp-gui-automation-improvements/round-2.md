# Round 2 Review

## Verdict
<!-- 可执行 / 需修复 / 需重新设计 -->
可执行

## Round 1 Blocking Issues Resolution
For each of the 5 Round 1 blocking issues, state RESOLVED or STILL BLOCKS, with one sentence rationale.

1. **`click`/`move_to` 新增 `target_name` 后的接口约定不明确** — **RESOLVED**。计划第 59-79 行给出了新的 JSON schema 示例、`target_name` 与 `(x, y)` 至少提供其一的校验规则，以及先 UIA 定位并做控件级安全检查、再回退坐标的执行顺序。

2. **`find_control` 搜索范围与匹配语义未说明** — **RESOLVED**。计划第 46-57 行明确搜索为 descendants 遍历，定义了 `scope`（desktop/foreground/window）和 `match`（exact/contains/startswith）参数，并规定命中多个返回首个、未命中返回空结果。

3. **`wait_for_idle` 判定标准缺失** — **RESOLVED**。计划第 117-121 行将 `wait_for_idle` 降级为辅助能力，主推 `wait_for_window`/`wait_for_control`，并给出了采样窗口、CPU 阈值、连续采样次数和精确进程名匹配的具体定义。

4. **`run` 工具的白名单/安全策略不完整** — **RESOLVED**。计划第 96-101 行明确白名单来源为 `config.yaml` 的 `safety.allowed_commands`，使用 `shlex.split` 风格仅校验首个 token、参数透传、默认拒绝，并拦截 `&`、`|`、`;`、`$()`、反引号等 shell 元字符。

5. **UIA 定位后的安全检查流程未明确** — **RESOLVED**。计划第 76-78 行和第 145-148 行明确 `click`/`move_to` 解析控件后需将进程名、类名、控件类型传入 `check_target_window`，且 `find_control` 默认开启 `sensitive_check=True`。

## 前置自检 (Q1-Q5)

- **Q1 Identity**：PASS。文件是一份结构完整的实施计划，标题“MCP GUI 自动化执行效率改进计划”与内容一致。
- **Q2 Boundary Honesty**：PASS。第 215-219 行明确列出三项“不纳入本次范围”的内容，未发现隐蔽范围扩张。
- **Q3 Data Purity**：PASS。瓶颈基于真实的 HiBit Uninstaller 案例，关键指标（OCR 2-10 秒、整体耗时数分钟、目标 30 秒内）具体可验证。
- **Q4 Responsibility Boundary**：PASS。新增能力均落在 MCP 服务器侧（截图、UIA 工具、启动、等待），未推给客户端或模型。
- **Q5 Naming Consistency**：PASS。新工具名遵循 `snake_case`，`find_control`、`wait_for_window`、`launch_app` 等与现有风格一致；`type` 工具名与现有代码保持一致。

## 设计审查 (DR1-DR7)

- **DR1 Goal Clarity**：目标与验收标准清晰可测（UIA 定位、事件等待、应用启动、整体任务 <30 秒、测试覆盖率 ≥80%），“更快、更稳、更自然”的定性描述不影响执行。
- **DR2 Completeness**：覆盖了视觉理解、控件定位、应用启动、事件等待、OCR 预热、安全六个方面，并补充了测试策略章节；Round 1 提出的接口约定、搜索语义、白名单规则、`wait_for_idle` 标准等关键细节均已补齐。
- **DR3 Feasibility**：整体可行。`uiautomation` 查找控件、`Shell.Application` 启动桌面/开始菜单程序、UIA 事件等待在 Windows 上均可实现；`wait_for_idle` 已明确阈值和采样策略，降低了实现主观性。
- **DR4 Consistency**：与现有架构（`mcp_server.py` 注册工具、`safety.py` 统一校验、`ui_automation.py` 可选降级）和 AGENTS.md 风格一致；`inspect_point` 的现状描述已修正为“计划一并注册为 MCP 工具”。
- **DR5 Maintainability**：改动模块化（新增 `launcher.py`、扩展 `ui_automation.py`、补充 `safety.py`），测试策略明确分层（mock 单元测试、Shell 启动 mock、manual marker、CI 跳过），便于独立验证。
- **DR6 Extensibility**：`scope`/`match` 参数、UIA 工具族、`launcher.py` 抽象为后续扩展（更多等待条件、批量控件枚举、其他启动方式）预留了接口。
- **DR7 Risk Awareness**：风险表已覆盖 UIA 支持不足、名称歧义、白名单误拦截、等待超时、UIA 库未安装、`wait_for_idle` CPU 采样抖动、`run` 命令注入等风险，并给出缓解措施。

## New Blocking Issues (if any)
<!-- severity + attribution -->

无新阻塞性问题。

## Suggestions (non-blocking)

- **`launch_app` 名称匹配算法仍可细化**：计划提出“要求传入完整名称，返回匹配列表供确认”，但未明确是精确匹配、子串匹配还是大小写不敏感匹配，也未说明唯一匹配时是否直接启动、多匹配时返回何种结构。建议在实施 Phase 2 时确定具体算法和返回 JSON 格式。
- **`run` 工具的 Windows 命令解析**：`shlex.split` 默认按 POSIX 风格解析，Windows 路径中的反斜杠和引号可能产生意外拆分。建议实现时使用兼容 Windows 的解析逻辑（如 `shlex.split(..., posix=False)` 后再处理引号）。
- **`click`/`move_to` JSON schema 的互斥表达**：计划示例使用 `required: []`，实际实现时建议用 `anyOf` 或 `oneOf` 约束“`target_name` 或 `(x, y)` 至少一组”，使模型在调用前就能获得更准确的参数提示。
- **`wait_for_idle` 的保留必要性**：虽然已明确参数，但 CPU 空闲判断仍较脆弱。建议在 Phase 4/5 实现中评估是否能完全由 `wait_for_window`/`wait_for_control` 覆盖，从而移除该工具。
- **文档更新顺序**：本计划涉及 `docs/api.md` 更新，执行时请遵循 AGENTS.md 中“先更新对应 `docs/*.md`，再写 CHANGELOG”的顺序。

## Summary

修订后的计划已完整回应 Round 1 的全部 5 项阻塞性问题：接口约定、控件搜索语义、等待标准、`run` 白名单规则以及 UIA 定位后的安全检查流程均已明确。计划目标清晰、与现有架构一致、风险可控，且补充了分层的测试策略。未发现新的阻塞性问题，可以进入执行阶段。建议在实施 `launch_app` 和 `run` 命令解析时关注上述非阻塞性建议。
