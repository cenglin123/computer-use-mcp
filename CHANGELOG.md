# CHANGELOG

<!--
- 日期节倒序排列，最新在前；同一天多次修改合并到同一个日期节，用 `###` 区分主题。
- 写入前不要读全文，用 `python scripts/changelog.py titles/show/add/recent` 操作。
- 当前工作状态写在 docs/CURRENT.md；CHANGELOG 只记录历史变更。
-->

## 2026-06-21

### feat: 强制 task_id 守卫、拦截高成本快照与内联输出预算

#### 变更内容
- Task 1-4 硬化：start_task 之后缺失 task_id 的可执行工具返回 missing_task_id；get_ui_snapshot(scope=desktop, include_screenshot=true) 直接被拦截返回 high_cost_snapshot_blocked；新增 MAX_INLINE_SNAPSHOT_CHARS=200_000 序列化后预算，超额返回 snapshot_output_too_large；guidance、SKILL.md 和 schema 描述同步加强 task_id / 桌面快照 / PNG 重读 三条规则。

#### 迁移影响
- 无破坏性迁移：旧调用方未传 task_id 且无 active task 时仍创建 standalone task；schema 描述增强不影响字段。

### feat: 新增 click_on_screenshot/crop_screenshot 与截图坐标绑定 metadata

#### 变更内容
- screenshot 返回 coordinate_space/capture_left/capture_top/metadata_path 并写入 sidecar JSON。click_on_screenshot 读取 sidecar 将图像像素映射为屏幕坐标，走完整安全链（validate_coordinate/inspect_point/check_target_window）。crop_screenshot 继承源截图偏移量，裁剪后 click_on_screenshot 仍能映射回原屏幕坐标。更新 schemas/guidance/skill/docs 描述截图点击流程。

### refactor: 统一 .agents 目录结构，充实 SKILL，纳入文档治理

#### 变更内容
- - 合并 .agent/memory/ 和 examples/ 到 .agents/ 下（.agents/memory/、.agents/examples/clients/）
- - SKILL.md 新增 Tool Quick Reference 表（30+ 工具速查）和 Minimal Examples 节（视觉点击流程、裁剪+点击、batch 示例）
- - 新增 test_skill_copies_are_identical 测试，防止 skills/ 和 .agents/skills/ 副本漂移
- - 更新 AGENTS.md 文档维护原则纳入 SKILL 同步规则
- - 更新 STRUCTURE.md、docs/agent-usage.md、docs/audit-checklist.md、docs/deployment.md、docs/pitfalls.md、scripts/audit.py 中的路径引用
- - agent_links.py 同步 AGENTS/CLAUDE/GEMINI 三件套



---

## 2026-06-20

### refactor: 提取 MCP tool schemas 到 computer_use/tools/schemas.py

#### 变更内容
- 将 mcp_server.py 中静态的 TOOLS 列表及 schema 相关常量迁移到独立模块，保持 _call_tool、_dispatch_tool、_handle_tool_call、_batch_tool 及 composite 运行时不变；新增测试防止 schema tool name 与 dispatch handler 漂移。

### feat: 优化 launch_app 白名单首次使用体验

#### 变更内容
- 在 computer_use/launcher.py 中区分白名单为空、白名单未命中与敏感进程拦截三种错误消息；白名单相关错误指向 config.example.yaml；新增 config.example.yaml 示例。

### test: 新增真实 GUI 集成测试骨架

#### 变更内容
- 创建 tests/manual/conftest.py 与 tests/manual/test_notepad_smoke.py；manual 测试默认被 marker 跳过，需设置 COMPUTER_USE_RUN_MANUAL=1；pyproject.toml dev 依赖新增 pytest-timeout 与 pywin32。

### docs: 补充 deployment、pitfalls、overview、README

#### 变更内容
- 说明 doctor 的 UIA 检查、截图 redaction 现状、allowed_commands 配置、混合 DPI fail-fast、UIA 不可用时视觉回退、集成测试副作用与测试分层策略。

### fix: 收敛验收发现的测试与文档整理问题

#### 变更内容
- 修复 tests/test_mcp_server.py 中 test_key_down_up_and_press 缩进错误导致的未收集问题；修正已归档计划 frontmatter 为 status: completed；清理 docs/pitfalls.md 重复段落；在 pytest.ini 注册 timeout marker。

### docs: 在 guidance、agent-usage、agent-prompt 同步光标标记验证纪律

#### 变更内容
- 把截图红十字标记用于验证坐标点击落点的使用纪律，从 SKILL.md 同步到 computer_use.guidance、docs/agent-usage.md 和 examples/clients/agent-prompt.md，确保所有 Agent 入口都能读到该规则。

### docs: MCP 调用准确度与性能改进计划

#### 变更内容
- 记录 2026-06-20 原神任务中点击偏差、截图占上下文、未读取 SKILL、trace 缺少上下文等问题，改进方案已归档至 docs/plans/completed/mcp-accuracy-performance-improvement.md。

### feat: 实现 review_task detail 参数与 MCP 分发统一

#### 变更内容
- review_task/review_task_session 新增 detail: bool=False 参数，detail=True 时返回 steps 数组（step_index/tool/args/result/duration_ms/screenshot_path 等）。
- 删除 _review_task_session_result 平行实现，MCP 分发统一委托 review.review_task_session。
- tools/schemas.py 为 review_task/review_task_session 增加 detail 参数 schema。
- review_task 顶层调用保持只读，不创建额外 task/trace；detail 输出对历史/raw trace 再做防御性脱敏。
- 新增/更新测试覆盖 detail 行为、MCP 等价性、只读复盘和脱敏。

### docs: 坐标点击门控、上下文预算与执行示例

#### 变更内容
- guidance.py/SKILL.md: 坐标点击三段式（move_to -> screenshot -> click）pre-click 验证 + 失败止损规则。
- guidance.py/SKILL.md: 上下文预算门控（禁用 CLI base64、默认 foreground、60s 响应止损）。
- cli.py: screenshot help 标注 base64 风险。
- docs/api.md: clicked=true 语义说明、自绘 GUI 点击安全示例、batch 观察验证警告、scope=desktop 成本提示。
- docs/pitfalls.md: 长上下文 GUI 任务响应退化陷阱。





---

## 2026-06-17

### feat: 提升 MCP 分发开箱可用性

#### 变更内容
- 新增 MCP prompts、安装 doctor、只读 smoke、通用客户端示例和分发就绪测试，让用户注册 MCP 后可直接发现正确使用路径；强化工具描述和错误 next_action，降低纯文本模型误用与盲点操作风险。

### docs: README 增加中文 MCP 使用说明

#### 变更内容
- 在 README 中补充中文端到端使用流程，覆盖 doctor 自检、客户端注册、guidance/Skill 加载、只读 smoke、真实 GUI 任务闭环和多模态模型限制。


---

## 2026-06-16

### fix: 完成 MCP 安全边界 Converge 验收

#### 变更内容
- 将主屏坐标约束下沉至最终输入原语，补齐拖拽起点与快照实时目标检查，修正 timeout 报告语义和密码输入边界，并增加多屏环境确定性回归测试。无迁移操作；输入仍仅限主屏非负坐标，只读感知继续支持多屏。

### docs: 校准 MCP 安全与多屏说明

#### 变更内容
- 更新系统设计、部署和环境陷阱文档，明确跨屏感知、主屏输入、分层安全检查及显示器拓扑刷新约束；压缩 Agent 常驻摘要并同步 AGENTS.md、CLAUDE.md、GEMINI.md。无接口迁移。

### feat: 截图显示当前光标标记

#### 变更内容
- 截图保存前叠加红色十字与中心圆点，单显示器截图按显示器偏移换算；补充像素级回归测试和设计/API 说明。归档 20260614 项目验收状态，并清理会话导出、HiBit 临时脚本和本地 PaddleOCR 源码副本。无接口迁移。

### docs: 规划 MCP 契约与产物诊断演进

#### 变更内容
- 新增 nested 工具名规范化、invalid_tool 分类、trace artifact manifest、惰性目录和权威执行摘要的实施计划；将已完成的 smart-executor-and-trace 计划从 active 归档到 completed。无运行时变更。

### docs: 规划业务任务会话审计

#### 变更内容
- 新增独立实施计划，定义 task_id 业务任务边界、日期分区 trace、可重建定位索引、standalone 兼容和任务级审计流程；与正在审计的 MCP 契约计划串行实施。

### fix: 强化 batch 契约与 trace 产物报告

#### 变更内容
- 统一 nested 工具 canonical 名称与 invalid_tool 分类，新增 trace artifact manifest 和响应证据字段，自动截图/快照绑定 trace，避免执行侧混淆目录用途或误报产物。

### feat: 增加业务任务会话审计

#### 变更内容
- 新增 task_id 生命周期、日期分区 trace、任务级复盘与旧布局兼容，解决同日多任务 trace 难以归属和审计的问题。

### fix: 加载 task_dir 配置

#### 变更内容
- 修复 config.yaml 中 task_dir 未进入运行时配置的问题，避免业务 task 写入默认用户目录；补充配置测试与 bugfix 复盘文档。

### fix: 收口计划验收反馈

#### 变更内容
- 补齐 run_task_plan 嵌套工具 Schema enum，延迟 CLI inspect_point 导入避免只读审计加载 pyautogui，并关闭 trace 归属冲突时创建的 standalone task。

### feat: 通用化 MCP 客户端支持

#### 变更内容
- 将运行时默认配置、日志和截图目录迁移到 ~/.computer-use，保留旧 Kimi 配置路径兼容回退；更新 README、部署和 API 文档，明确该服务可由任意 stdio MCP 客户端注册使用。

### docs: 说明多模态模型要求

#### 变更内容
- 补充 Computer Use MCP 的能力边界：视觉 GUI 操作需要可读取本地 PNG 截图的多模态模型；纯文本模型只能可靠使用结构化查询、审计和维护类工具。

### docs: 增加 Computer Use MCP agent 使用指南

#### 变更内容
- 新增配套 Skill 与通用 agent prompt，明确多模态能力边界、GUI 操作闭环、安全纪律、batch/task/trace 使用方式，便于非 Kimi 客户端正确接入。












---

## 2026-06-15

### fix: 加固 MCP 安全边界与任务 trace 语义

#### 变更内容
- 修复配置覆盖和命令白名单路径匹配；限制截图与 trace 写入路径；补齐滚动和敏感截图检查；统一 timeout/fail-safe、任务递归预算和单 trace；对日志与 trace 输入正文脱敏并禁止重放脱敏步骤。

---

## 2026-06-14

### feat: 添加 batch MCP 工具

#### 变更内容
- 新增 batch 工具，允许一次调用顺序执行多个 MCP 工具并返回聚合结果与最终截图，减少多步 GUI 任务的往返次数；补充 4 个单元测试。

### feat: 扩展键鼠宏原语

#### 变更内容
- 为 MCP 增加低层输入工具：click 支持 button（left/right/middle），新增 mouse_down、mouse_up、drag、scroll 方向模式、key_down、key_up、press_key；同步更新 core.py、tests、docs/api.md。

### docs: 明确 MCP 最小键鼠宏 + ReAct 边界

#### 变更内容
- 在 docs/overview.md 和 .agent/memory/MEMORY.md 中记录：MCP 只保留键鼠宏原语与屏幕观察，复杂多步 GUI 任务由上层 Agent 通过 ReAct 边截图边规划，复杂命令行任务交给 Bash。

### refactor: 移除 run MCP 工具

#### 变更内容
- 删除 run 工具及其测试/文档；命令行任务由上层框架通过 Bash 完成，MCP 只聚焦 GUI 键鼠宏与屏幕观察。

### refactor: 进一步压缩 MCP 工具集

#### 变更内容
- 移除 ocr、get_screen_size、get_cursor_position 工具，删除 computer_use/ocr.py、ocr_subprocess.py 及相关测试/脚本；更新 config.yaml、docs/api.md 和项目记忆。MCP 现在只保留 19 个核心工具，聚焦键鼠宏 + 屏幕观察 + UIA 辅助。

### fix: screenshot 与 batch 默认不再返回 base64 图像，防止上下文爆炸

#### 变更内容
- `screenshot` 工具新增 `include_image` 参数，默认 `false`；默认仅返回 `{screenshot_taken, monitor, width, height, note}` 元数据。
- `batch` 工具的 `final_screenshot` 默认改为 `false`；显式开启后才会附带最终截图。
- 更新 `docs/api.md`、`tests/manual_test_checklist.md`、`.agent/memory/MEMORY.md` 与 `AGENTS.md` 以反映新的上下文保护约束。
- 相关 MCP server 测试已同步更新。

### MCP 工具增强：screenshot save_path 与 click double_click

#### 变更内容
- - screenshot 新增 save_path 参数，可把 PNG 写入磁盘并返回文件路径，避免 base64 涌入上下文；可与 include_image=true 同时使用。\n- click 新增 double_click 参数，支持原生双击，兼容 target_name 与坐标模式以及 button 参数。\n- 新增 save_screenshot / save_redacted_image / double_click 原子函数。\n- 补充 tests/test_mcp_server.py 相关测试用例。

### feat: screenshot 改为仅返回本地路径引用，默认主屏并带时间戳

- 待补充

### docs: 更新 api.md 与 manual_test_checklist.md 以匹配 screenshot 新行为

- 待补充

### refactor: batch 工具增加 outputSchema 并显式声明直接调用，避免模型写 Python 包装

- 待补充

### fix: 移除 batch/screenshot 的 outputSchema，避免 MCP 客户端因未返回结构化输出而拒绝

- 待补充

### feat: 所有 MCP 工具响应统一注入 timestamp，便于精确计算每步时间间隔

- 待补充

### feat: 新增 sleep MCP 工具，支持 batch 工作流中固定等待；单位为秒，最大 60 秒

- 待补充

### docs: 整理项目记忆文档，保留通用经验，删除具体任务日志，同步 AGENTS.md/CLAUDE.md/GEMINI.md

- 待补充

### Phase 1: trace system + structured UI snapshot

#### 变更内容
- - Added computer_use/trace.py for structured trace records, reports, and reads; default trace dir ~/.computer-use/traces/.\n- Added computer_use/snapshot.py and get_ui_snapshot MCP tool returning a snapshot-scoped UIA tree with self-contained UIDs.\n- Extended atch with per-action capture_snapshot, shared 	race_id, and sub-step trace recording.\n- Expanded tool registry to 20+ tools including click/move_to by UIA name, low-level mouse/keyboard, drag,
- ind_control, wait_for_*, launch_app, sleep, etc.\n- Updated docs/api.md, docs/overview.md, docs/pitfalls.md, docs/audit-checklist.md to remove OCR references and document snapshot/trace semantics.\n- Added 	race_dir default to config.yaml.

#### 迁移影响
- Optional: add 	race_dir: ~/.computer-use/traces to config.yaml to override the default trace location.

### Phase 2/3: composite tools, task runner, retry and review

#### 变更内容
- - Added computer_use/composite.py with click_by_uid, click_by_text, open_menu,
- ill_form, scroll_until.\n- Added computer_use/runner.py with
- un_task_plan and
- etry_step (single/from_step modes, string retry step_index).\n- Added computer_use/review.py with deterministic
- eview_task summary.\n- Registered 8 new MCP tools in mcp_server.py.\n- Updated 	race.py to support int | str step_index.\n- Added tests: 	ests/test_composite.py, 	ests/test_runner.py, 	ests/test_review.py.\n- Updated docs/api.md and docs/overview.md to document composite, task-level, retry, and review tools.

### fix: 修复 ultraverge 验收发现的 trace、composite 与 batch 问题

#### 变更内容
- run_task_plan 截图不再产生重复 step_index；composite 与 snapshot.click_by_uid 增加 safety.py 校验；结构化错误（ui_not_found/stale_uid 等）写入 trace error_kind；batch 子步骤在 run_task_plan 下使用命名空间避免 step_index 冲突；batch final_screenshot 默认 monitor 改为 1；review_task 从 trace meta 读取 goal；report.md 包含 final_state_path。

### docs: 维护文档体系，补充审计日志

#### 变更内容
- 运行 scripts/audit.py check 与 agent_links.py check；AGENTS.md 行数/字数接近上限但内容精简合理，暂不下沉；新增 docs/audit-log.md 记录审计结果。



















---

## 2026-06-13

### click/move_to 支持平滑移动

#### 变更内容
- 为 click 和 move_to 增加 duration 参数（默认 0.2 秒），通过 pyautogui 的 duration 实现平滑移动，避免光标瞬移导致悬停菜单/下拉框关闭。MCP 工具 Schema、本地 CLI 和 core API 均支持自定义 duration。新增对应单元测试。

### 初始化 agent-first 文档体系

#### 变更内容
- 将项目复制到 C:/Project/computer-use 并初始化 git。建立 AGENTS.md / CLAUDE.md / GEMINI.md 同步体系，创建 STRUCTURE.md、docs/ 专题文档、CHANGELOG 和 plans 目录。迁移 README.md 并添加 AI Agent 协作指针。配置 pre-commit hook。详见 docs/plans/completed/initialization.md。

### 集成 PaddleOCR 图像识别

#### 变更内容
- 新增 ocr MCP 工具，调用项目内置 tools/PADDLEOCR 的 PaddleOCR Python API 对图片进行文字识别。支持 image（base64 PNG）和 image_path 两种输入，返回 texts 与 full_text。PaddleOCR 路径可通过 config.yaml 的 ocr.paddleocr_path 配置。新增 computer_use/ocr.py、tests/test_ocr.py，并更新 mcp_server、config、docs/api.md、config.yaml 与测试。

### ocr 工具支持系统 Python 的 PaddleOCR

#### 变更内容
- 当项目虚拟环境未安装 PaddleOCR 时，ocr 工具自动 fallback 到能导入 paddleocr 的系统 Python（如 anaconda3）执行 OCR。新增 ocr_subprocess.py 辅助脚本，新增 ocr.python_executable 配置项用于显式指定解释器，并补充对应测试与文档。

### 修复 PaddleOCR 环境依赖，完成 OCR 端到端验证

#### 变更内容
- 卸载系统 Python 中的 paddlepaddle-gpu，安装 CPU 版 paddlepaddle 3.2.1，解决 cudnn_cnn64_9.dll 加载失败。调整 ocr_subprocess.py 将 JSON 结果写入临时文件并通过路径返回，避免 PaddleOCR 的 C++/oneDNN 日志污染 stdout。在 .venv 中调用 ocr 工具可成功经系统 Python 完成真实 OCR 识别。

### feat: Phase 1 control-tool foundation

#### 变更内容
- - Add find_control, wait_for_window, wait_for_control, and inspect_point UI Automation helpers.\n- Add is_allowed_command and contains_shell_metacharacters safety helpers.\n- Register find_control, inspect_point, wait_for_window, wait_for_control as MCP tools.\n- Add config safety.allowed_commands default and config.yaml example.\n- Add unit tests with mocked UIA control trees.

### feat: Phase 2 launch and run tools

#### 变更内容
- - 新增 computer_use/launcher.py，通过 Shell.Application + WScript.Shell 按名称启动开始菜单/桌面快捷方式，支持精确匹配、子串回退、多匹配歧义提示、allowed_commands 白名单与敏感进程检查。\n- 在 mcp_server.py 注册 launch_app 与 run MCP 工具。\n- run 工具使用 subprocess.run([executable, *args]) 列表形式执行，先拦截 shell 元字符，再通过 shutil.which / Path.resolve 解析命令并校验白名单。\n- 新增 tests/test_launcher.py 与 tests/test_mcp_server.py 中 run/launch_app 工具分发测试，全部采用 mock，不依赖真实 Windows Shell。

### feat: Phase 3 semantic click/move_to

#### 变更内容
- 为 click 和 move_to 增加 target_name 与 match 参数，优先通过 UIA 控件定位并执行控件级安全检查，未命中时回退到坐标模式。\n更新 click/move_to 的 MCP 工具 JSON schema，使用 oneOf 表达必须提供 target_name 或 (x, y)。\n返回结果增加 mode（uia/coordinate）、target_name 与 control 信息。\n新增 tests/test_mcp_server.py 单元测试，覆盖 UIA 命中、未命中、坐标回退、敏感进程拦截及缺少参数校验。

### docs: Phase 4 visual understanding guidance and API docs

#### 变更内容
- 更新 `computer_use/mcp_server.py` 中 `screenshot` 与 `ocr` 的工具描述：强调 `screenshot` 返回 base64 PNG 供多模态模型直接读图，`ocr` 仅用于大量文字提取场景。
- 重写 `docs/api.md`：新增“视觉理解工作流”章节，推荐 `screenshot` → 模型读图 → `find_control`/`wait_for_window` → 必要时 `ocr` 的调用模式。
- 在 `docs/api.md` 中补充 `find_control`、`inspect_point`、`wait_for_window`、`wait_for_control`、`launch_app`、`run` 的约定说明及典型调用流程示例。
- 未改动工具 schema 与行为；全量测试保持通过。

### feat: Phase 5 OCR preheat and benchmark

#### 变更内容
- 在 computer_use/ocr.py 中增加可选的 PaddleOCR 后台预热（ocr.preheat，默认 false），模块导入时非阻塞启动后台线程初始化引擎，首次调用可复用已预热实例，未预热完成则降级为按需初始化，预热失败仅记录日志。\n新增 ocr.preheat 默认配置与 config.yaml 示例。\n新增 pytest.ini 并注册 manual marker。\n新增 scripts/benchmark_hibit.py 手动基准脚本，用于测量“启动 HiBit → 工具 → 注册表清理程序”冷/热启动耗时。\n补充 ocr/config 相关单元测试，全量测试通过。

### 升级文档体系到新版 init-agent-docs

#### 变更内容
- 重写 AGENTS.md：新增 Compact 恢复、项目记忆内联摘要、复杂任务闭环升级触发、记忆自检；创建 .agent/memory/MEMORY.md；更新 docs/CURRENT.md、docs/audit-checklist.md、STRUCTURE.md；升级 scripts/audit.py 并移除 WebSocket 关键词 'ws' 以避免误报；agent_links check、audit.py check、pre-commit hook 均通过。

### docs: 在 pitfalls.md 补充自定义绘制标题栏陷阱

#### 变更内容
- 记录 HiBit Uninstaller 等 Delphi/VCL 程序中，文字标签与真实可点击控件（TrkGlassButton）位置不一致导致的坐标点击失效问题。
