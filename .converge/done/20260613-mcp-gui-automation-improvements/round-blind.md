# Blind-Slate Recertification Review

## Verdict
需修复

## Blocking Issues

1. **implementation**: `click`/`move_to` 的 JSON schema 无法表达“target_name 与 (x,y) 必须至少提供一个”的条件必填语义。计划示例将 `required` 设为空数组，与文字说明矛盾；MCP schema 应使用 `oneOf`/`anyOf` 或拆分为独立工具，否则实现者无法生成合法接口。

2. **implementation**: `launch_app(name)` 的 Shell.Application 启动机制未精确说明。是使用 `Shell.Application.ShellExecute`、遍历开始菜单快捷方式，还是解析 `Shell.Namespace`？名称匹配规则、歧义处理、返回值结构均未定义，无法直接编码。

3. **implementation**: `run` 工具的命令拆分声称“Windows 兼容的 `shlex.split` 风格”，但 `shlex` 是 Unix 语义，Windows 路径中的反斜杠和引号会被误解析。必须明确使用 `shlex.split(..., posix=False)` 或 `msvcrt`/`subprocess` 的列表参数方式，否则白名单检查可能基于错误 token。

4. **implementation**: `wait_for_window` 与 `wait_for_control` 的语义不完整。`wait_for_window` 的 `name` 是否沿用 `find_control` 的 exact/contains/startswith 规则未说明；`wait_for_control` 的“可用”是指 Exists、Enabled、Visible 还是三者的组合未定义；两者均未说明匹配失败时的返回值与重试策略。

5. **structural**: 当前 `docs/api.md` 已列出 `inspect_point` 为“检查类”工具，但 `computer_use/mcp_server.py` 的 `TOOLS` 列表中并未注册它。计划提到要“一并注册”，但未明确这是修复文档与代码之间已有不一致的一部分，实施时容易遗漏回归测试。

6. **architectural**: `find_control` 在 UIA 未安装、未命中或命中敏感窗口时均返回“空结果”，模型无法区分这三种情况。计划应定义不同的返回字段（如 `uia_available`、`found`、`blocked_reason`）或错误码，否则模型会盲目重试相同查询。

7. **security**: `launch_app` 没有说明任何安全校验。按名称启动任意桌面/开始菜单程序属于高权限操作，应至少与 `run` 工具共享白名单/敏感应用检查，否则控件安全策略存在明显缺口。

8. **security**: `run` 工具的 shell 元字符列表遗漏了 Windows 命令行中常见的 `&&`、`||`、`>`、`<`、`^`、`%...%` 等重定向与连接符；仅拦截 `&`、`|`、`;`、`$()`、反引号不足以防止命令注入，尤其是当白名单误包含 `cmd.exe` 或脚本解释器时。

## Concerns and Suggestions (non-blocking)

- **性能目标可量化性**：验收标准提出“总耗时从数分钟降到 30 秒以内”，但未给出基准环境和测量方法。建议补充至少 3 次冷启动/热启动的计时方式和允许的最大方差。
- **OCR 预热实现细节**：“后台预热”应说明是线程、进程还是协程，是否阻塞首次 `ocr` 调用，以及预热失败时的降级行为。当前 `ocr.py` 使用全局单例，直接后台实例化可能引发线程安全问题。
- **控件匹配顺序**：`find_control` “命中多个时返回首个匹配”应明确遍历顺序（深度优先/广度优先），并建议在返回结果中增加 `match_index`/`total_matches` 帮助模型判断是否ambig。
- **`wait_for_idle` 的采样逻辑**：将 CPU 阈值、采样窗口等写入计划是好的，但“进程匹配按精确进程名进行”在多款同名进程（如多个 `explorer.exe`）场景下可能失效，建议说明按 PID 或窗口句柄匹配的可选方案。
- **测试覆盖率 ≥80%**：新增 GUI/Shell 相关代码若大量依赖 mock，80% 的覆盖率目标可能不够反映真实 UIA 行为。建议对 `manual` 标记的集成测试补充最小清单，而非仅依赖覆盖率数字。
- **AGENTS.md 一致性**：计划未明确执行阶段需要更新 `CHANGELOG.md` 和 `docs/CURRENT.md` 的步骤。虽然这是执行期职责，但在计划层补充提醒可减少遗漏。
- **`screenshot` 多模态引导**：仅调整工具描述可能不足以改变模型“先 OCR 后决策”的习惯。建议在 `docs/api.md` 中加入具体调用模式示例（如“先 screenshot → 描述画面 → 必要时 ocr”）。

## Summary

该计划方向正确，能够针对当前“像素 + OCR + 硬编码 sleep”的痛点提供有效改进路径，且与项目现有架构（`ui_automation.py`、`safety.py`、MCP 工具注册方式）基本契合。但多个关键接口的语义、schema、安全校验和错误处理尚未精确到可直接实现的程度，尤其是 `click`/`move_to` 的条件必填 schema、`launch_app` 的解析机制、`run` 的 Windows 命令拆分，以及 UIA 工具的返回值结构。在这些问题得到澄清和修订之前，不建议直接交给实施者执行。
