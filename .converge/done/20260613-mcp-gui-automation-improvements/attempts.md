# Attempt Log

## Round 1 → Round 2

- **reviewer_verdict**: 需修复
- **blocking_issues_count**: 5
- **accepted_fixes**:
  1. `click`/`move_to`：补充新 JSON schema，`target_name` 可选，与 `(x, y)` 至少提供其一；执行顺序改为先 UIA 定位并做控件级安全检查，再回退坐标。
  2. `find_control`：明确搜索为 descendants 遍历，新增 `scope`（desktop/foreground/window）与 `match`（exact/contains/startswith）参数，未命中返回空结果。
  3. `wait_for_idle`：移除作为主要等待手段的定位，主推 `wait_for_window` 与 `wait_for_control`；保留 `wait_for_idle` 时给出明确的采样窗口、CPU 阈值、连续采样次数与精确进程名匹配定义。
  4. `run` 工具：明确白名单来源为 `config.yaml` 的 `safety.allowed_commands`，使用 `shlex.split` 拆分并仅校验首个 token，参数透传，默认拒绝，并拦截 shell 元字符。
  5. UIA 定位后安全检查：明确 `click`/`move_to` 解析控件后将进程名、类名、控件类型传入 `check_target_window`；`find_control` 默认开启 `sensitive_check`。
  6. Misc：修正 `inspect_point` 描述为“计划一并注册为 MCP 工具”；新增 GUI/Shell 测试策略章节，包括 mock 测试、manual marker、CI 环境跳过机制。
- **remaining_risks**: `launch_app` 名称匹配仍依赖实际桌面/开始菜单路径，集成测试需在真实 Windows 桌面环境进行；`wait_for_idle` 即使精确定义也仍存在 CPU 采样抖动，后续实现中考虑是否完全移除。
- **amended_files**: docs/plans/active/mcp-gui-automation-improvements.md

## Round 2 → Round 3

- **source**: blind_recheck
- **reviewer_verdict**: 需修复
- **blocking_issues_count**: 8
- **accepted_fixes**:
  1. `click`/`move_to` schema：用 `oneOf` 表达“必须提供 `target_name` 或 `(x, y)` 之一”的条件必填语义，给出 MCP-compatible JSON schema 示例；并记录如 `oneOf` 不兼容可拆分为 `click_at` / `click_control` 的备选方案。
  2. `launch_app(name)` 精确机制：明确使用 `Shell.Application` 枚举开始菜单/桌面快捷方式；名称匹配主精确、回退子串；单个匹配调用 `Item.InvokeVerb('Open')`，多个匹配返回列表，无匹配返回错误；定义明确返回 JSON 结构。
  3. `run` 命令解析：明确使用 `shlex.split(command, posix=False)`，第一个 token 经 `Path.resolve()` 后与白名单匹配，参数以列表形式传入 `subprocess.run([executable, *args], ...)`。
  4. `wait_for_window` / `wait_for_control` 语义：`wait_for_window` 沿用 `find_control` 的 `contains` 匹配，轮询 200ms，超时/命中分别定义返回结构；`wait_for_control` 定义“可用”为 `Exists and Enabled and Visible`，同样给出超时/命中返回结构。
  5. `inspect_point` 不一致：在计划中显式声明修复 `docs/api.md` 已列出但 `mcp_server.py` 未注册 `inspect_point` 的已有不一致，并同步更新测试。
  6. `find_control` 空结果区分：定义不同返回字段 `uia_available`、`blocked`、`reason`，区分 UIA 未安装、未命中、被安全拦截三种情况；命中返回包含 `name`、`type`、`rect`、`center`、`process_name`。
  7. `launch_app` 安全：`launch_app` 与 `run` 共享 `safety.allowed_commands` 白名单，并将目标进程名传入 `check_target_window` 敏感进程检查。
  8. `run` 元字符列表：扩展拦截字符/模式至 `&`、`|`、`;`、`&&`、`||`、`>`、`<`、`>>`、`^`、`%...%`、`$()`、反引号、换行符，并明确在白名单检查前先进行元字符拦截。
- **remaining_risks**: `oneOf` schema 对某些 MCP 客户端的兼容性需实现时验证；`launch_app` 集成测试仍依赖真实 Windows 桌面/开始菜单环境；`wait_for_window`/`wait_for_control` 的 200ms 轮询在窗口快速闪现场景可能错过事件，后续可考虑 UIA 事件订阅优化。
- **amended_files**: docs/plans/active/mcp-gui-automation-improvements.md

## Round 3 → Round 4

- **source**: blind_recheck_2
- **reviewer_verdict**: 需修复
- **blocking_issues_count**: 7
- **accepted_fixes**:
  1. Added complete JSON schemas and return structures for all new tools in Appendix A (`find_control`, `inspect_point`, `wait_for_window`, `wait_for_control`, `launch_app`, `run`).
  2. Expanded `find_control` parameter semantics: documented `automation_id`, `control_type`, `class_name`, combination/priority behavior, and `scope=window` window-name matching rules with parent-not-found return.
  3. Fixed `launch_app` `.lnk` parsing: specified `win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk_path)` to read `.TargetPath`, combined with `Shell.Application.Namespace` enumeration.
  4. Fixed `run` command parsing: documented `command` + `args` as separate fields, `shutil.which` + `Path.resolve()` whitelist check, and shell-metacharacter check applied only to `command`.
  5. Unified security response format: all blocking actions return `{"error": "..."}` via `SafetyError`; `find_control` query returns structured `blocked: true` when `sensitive_check=True`.
  6. Aligned `click`/`move_to` `target_name` matching: default `"contains"`, optional `match` parameter with enum `["exact", "contains", "startswith"]`.
  7. Added `uiautomation` traversal API hint (`GetDescendantControl` / `GetDescendantControls`, fallback to recursive sibling/child APIs).
  8. Added `config.yaml` OCR preheat example and clarified `run` metacharacter detection rules.
- **remaining_risks**: `oneOf` schema compatibility still needs implementation-time verification with the target MCP client; `launch_app` integration tests still depend on a real Windows Start Menu/Desktop environment; 200ms polling in wait tools may miss rapidly appearing/disappearing windows, which could be improved later with UIA event subscriptions if needed.
- **amended_files**: docs/plans/active/mcp-gui-automation-improvements.md
