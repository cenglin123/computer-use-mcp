# Round 1 Review

## Verdict
<!-- One of: 可执行 / 需修复 / 需重新设计 -->
需修复

## 前置自检 (Q1-Q5)

- **Q1 Identity**：PASS。文件明确是一份实施计划，标题与内容（MCP GUI 自动化执行效率改进）一致。
- **Q2 Boundary Honesty**：PASS。末尾明确列出“不纳入本次范围”的三项内容，未发现隐蔽的范围扩张。
- **Q3 Data Purity**：PASS。瓶颈基于真实的 HiBit Uninstaller 执行案例，关键指标（OCR 2-10 秒、整体耗时数分钟、目标 30 秒内）虽为近似值，但足够具体且可验证。
- **Q4 Responsibility Boundary**：PASS。新增能力均落在 MCP 服务器侧（截图、UIA 工具、启动、等待），没有把本应由服务器完成的工作推给客户端或模型。
- **Q5 Naming Consistency**：PASS。新工具名基本遵循现有 `snake_case` 约定；注意现有工具实际是 `type` 而非 `type_text`，`run` 名称较通用但可接受。

## 设计审查 (DR1-DR7)

- **DR1 Goal Clarity**：目标与验收标准清晰可测（UIA 定位、事件等待、应用启动、整体任务 <30 秒、测试覆盖率 ≥80%）。“更自然”偏感性，但不影响执行。
- **DR2 Completeness**：覆盖了视觉理解、控件定位、应用启动、事件等待、OCR 预热、安全六个方面，方向完整。但缺少 `click`/`move_to` 的新旧参数兼容方案、`find_control` 的搜索范围、`run` 白名单规则、`wait_for_idle` 判定标准等关键细节。
- **DR3 Feasibility**：整体可行。`uiautomation` 查找控件、`Shell.Application` 启动桌面/开始菜单程序、UAI 事件等待均可在 Windows 上实现。`wait_for_idle` 基于 CPU 空闲的判断较脆弱，需要更明确的阈值和采样策略；`launch_app` 的名称匹配也依赖实际路径与动词解析。
- **DR4 Consistency**：与现有架构（`mcp_server.py` 注册工具、`safety.py` 统一校验、`ui_automation.py` 可选降级）和 AGENTS.md 风格一致。但计划称 `inspect_point`“已暴露为 MCP 工具”，而当前 `mcp_server.py` 的 `TOOLS` 列表并未注册它，仅内部调用，存在事实出入。
- **DR5 Maintainability**：改动模块化（新增 `launcher.py`、扩展 `ui_automation.py`、补充 `safety.py`），便于独立测试。但涉及 Shell 启动和真实 GUI 的测试需要 mock 或环境隔离策略。
- **DR6 Extensibility**：新增 UIA 工具族和启动工具为后续扩展（如更多等待条件、批量控件枚举）预留了接口，扩展成本较低。
- **DR7 Risk Awareness**：已识别 UIA 支持不足、名称歧义、白名单误拦截、等待超时等风险并给出缓解措施。遗漏：UIA 库未安装时的降级路径、`wait_for_idle` 的抖动风险、`run` 命令解析被绕过的可能性、UIA 定位后仍需进行敏感窗口检查。

## Blocking Issues
<!-- List only issues that prevent "可执行". Each item must include severity (conceptual/architectural/implementation/structural) and attribution (plan_defect / unclear_scope / missing_info). -->

1. **`click`/`move_to` 新增 `target_name` 后的接口约定不明确**
   - 当前工具 schema 中 `x`、`y` 为 `required`；若支持 `target_name` 优先定位、坐标 fallback，则必须重新定义必填/可选关系与校验顺序。计划未给出 schema 与分支逻辑。
   - **Severity**：structural | **Attribution**：plan_defect

2. **`find_control` 搜索范围与匹配语义未说明**
   - 现有 `find_control_by_name` 仅对根控件做 `GetFirstChildControl`，大概率无法直接命中深层菜单项（如“注册表清理程序”）。计划提到支持名称/类型/AutomationId，但未说明是否做子孙遍历、模糊匹配还是精确匹配，验收标准可能无法达成。
   - **Severity**：implementation/structural | **Attribution**：plan_defect / missing_info

3. **`wait_for_idle` 判定标准缺失**
   - 基于进程 CPU 空闲的等待没有给出阈值、采样窗口、进程名去重或多实例处理策略，实现和验收均存在较大主观性。
   - **Severity**：implementation | **Attribution**：unclear_scope

4. **`run` 工具的白名单/安全策略不完整**
   - 计划仅说“默认白名单机制，仅允许启动已知安全应用”，但未定义何谓“已知安全应用”、如何解析命令与参数、是否允许带参数的可执行文件、拦截列表如何配置。这会导致实现时要么过度放行，要么过度限制。
   - **Severity**：implementation/structural | **Attribution**：unclear_scope

5. **UIA 定位后的安全检查流程未明确**
   - 当 `click`/`move_to` 通过 `target_name` 解析到控件后，必须复用 `check_target_window` 对目标进程/窗口类进行敏感检查。计划仅概括“所有新工具必须通过 `safety.py` 检查”，未说明检查时机和数据来源。
   - **Severity**：implementation | **Attribution**：missing_info

## Suggestions (non-blocking)

- 在计划中补充 `click`/`move_to` 的新 JSON schema 示例，明确 `target_name` 与 `(x, y)` 的互斥/兼容关系。
- 将 `find_control` 设计为支持子孙控件遍历，并暴露 `scope`、`match`（精确/子串/正则）等参数以提升通用性。
- 考虑用“控件可用/可点击/窗口可见且 foreground”替代或补充 `wait_for_idle`，降低 CPU 采样带来的不稳定性。
- 明确 `run` 工具的白名单格式（如配置键 `safety.allowed_commands`）与参数拆分规则，优先使用 `shlex` 或路径白名单而非简单字符串匹配。
- 修正 `inspect_point` 的现状描述：当前尚未注册为 MCP 工具，计划应说明会一并补齐该注册。
- 补充 GUI/Shell 相关测试策略（mock `Shell.Application`、标记 `manual` 测试或依赖环境变量跳过）。

## Summary

该计划方向正确，与现有架构和 AGENTS.md 约束基本对齐，能够解决 HiBit 任务中暴露的睡眠等待、OCR 依赖和坐标脆弱问题。但在执行前需要修订现有工具的参数约定、控件搜索语义、`run` 白名单规则以及 `wait_for_idle` 判定标准。补齐这些实现级细节后，可进入执行阶段。
