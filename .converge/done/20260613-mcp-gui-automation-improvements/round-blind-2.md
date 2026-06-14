# Blind-Slate Recertification Review 2

## Verdict
<!-- 可执行 / 需修复 / 需重新设计 -->
需修复

## Blocking Issues
<!-- If any. Each must include severity and one-sentence description. -->

1. **缺少多个工具的完整 JSON Schema 与返回结构（严重）**：计划仅给出了 `click`/`move_to` 的 `oneOf` schema，而 `find_control`、`wait_for_window`、`wait_for_control`、`launch_app`、`run`、`inspect_point` 均未提供 MCP 可用的 `inputSchema` 和统一返回 JSON 结构，实现者必须自行猜测字段名、类型与必填规则。

2. **`find_control` 参数语义不完整（严重）**：文案声称支持“名称/类型/AutomationId”，但实际只定义了 `scope` 与 `match`；未说明 `automation_id`、`control_type`、`class_name` 等参数的命名、是否互斥、优先级及组合行为。

3. **`launch_app` 解析 `.lnk` 目标路径的技术方案不可行（严重）**：`Shell.Application` 的 `Namespace`/`Item` 不直接暴露快捷方式目标路径（`TargetPath`），计划却要求用其解析目标并做白名单校验；缺少 `WScript.Shell` 或 `win32com` Shortcut 对象的说明，实现者会落地失败。

4. **`run` 工具的 Windows 命令解析方案存在缺陷（严重）**：计划采用 `shlex.split(command, posix=False)` 拆分 Windows 命令行，但 Windows 命令解析并非 POSIX 语义；未说明 PATH 查找、带空格路径、合法 `&`/`^` 路径（如 `C:\Foo & Bar\app.exe`）的处理，直接用 `Path(token).resolve()` 对非绝对路径也会失败。

5. **安全响应格式不一致（中等）**：`find_control` 命中敏感窗口时返回结构化 JSON（`blocked: true`），而 `click`/`move_to` 的 `target_name` 路径计划要求“检查通过后才执行”——即抛 `SafetyError` 转为 `{"error": ...}`；两种返回风格会让调用方/模型处理不一致，需要统一。

6. **`wait_for_window` / `wait_for_control` 在 `exists=False` 时返回值语义反直觉（中等）**：超时时返回 `{"found": true, "timeout": true}`，`found` 字段含义与字面意义相反，建议改为 `exists`/`present` 等更清晰的字段。

7. **`run`、`inspect_point` 返回结构完全缺失（中等）**：`run` 工具没有定义任何返回值；`inspect_point` 虽已内部存在，但注册为 MCP 工具后的返回 JSON 格式未说明。

## Concerns and Suggestions (non-blocking)

- `safety.check_target_window` 已经接收 `process_name`、`class_name`、`control_type` 三个参数，计划写成“扩展...支持控件元数据”容易让实现者做重复工作；建议改为“在 `click`/`move_to` 的 `target_name` 路径中正确调用现有 `check_target_window`，并视需要补充基于 `control_type` 的规则”。

- `click`/`move_to` 的 `target_name` 未说明匹配模式（`exact`/`contains`/`startswith`），建议与 `find_control` 的 `match` 参数对齐，或显式指定默认值。

- `scope="window"` 依赖 `window_name`，建议补充窗口名称的匹配规则（大小写是否敏感、`contains`/`exact`）以及找不到对应窗口时的错误返回。

- “深度优先前序遍历”建议给出 `uiautomation` 库的具体调用方式（`GetDescendantControl` / `GetDescendantControls` / 递归 `GetFirstChildControl` + `GetNextSiblingControl`），避免实现者误选仅搜索直接子控件的 API。

- OCR 预热配置 `ocr.preheat` 的取值未明确（bool、线程数、延迟秒数？），建议给出 `config.yaml` 示例的具体形态。

- Phase 顺序整体合理，但 Phase 4（调整工具描述）风险极低，可与 Phase 1 并行或提前，不会引入回归。

- 测试策略较好，但建议明确 `manual` marker 在 `pytest.ini` 中的注册方式，避免未注册 marker 告警。

- 验收标准“完整复现…30 秒以内”高度依赖环境，建议同时记录 baseline 耗时，或改为“相对 baseline 降低 X%”这类更稳定的指标。

- 元字符拦截中的 `%...%`、`$()`、反引号模式需要给出具体正则/检测方式，否则不同实现者理解可能不一致。

## Summary

该计划方向正确，覆盖了点坐标点击脆弱、OCR 过重、应用启动依赖桌面图标、固定 sleep 等待等核心痛点，风险与缓解措施也基本合理。但就目前版本而言，**不能作为可直接执行的 implementer 手册**：多个关键工具的输入 schema、返回结构、字段语义尚未定义完整，`launch_app` 的 `.lnk` 解析方案在技术上不可行，`run` 的 Windows 命令解析也存在明显缺陷。建议先补齐所有工具的 JSON schema 与返回结构、修正 `launch_app` 和 `run` 的技术实现路径、统一安全响应格式，并澄清 `wait` 工具的返回语义；完成后可重新进入评审。
