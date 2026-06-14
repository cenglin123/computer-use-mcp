# Round 4 Review

## Verdict
<!-- 可执行 / 需修复 / 需重新设计 -->
可执行

## Round-Blind-2 Blocking Issues Resolution

1. **Complete JSON Schema and return structure for all new tools** — **RESOLVED**. Appendix A now provides MCP-ready `inputSchema` and return JSON for `find_control`, `inspect_point`, `wait_for_window`, `wait_for_control`, `launch_app`, and `run`. `click`/`move_to` also have a `oneOf` schema in the main text.

2. **`find_control` parameter semantics** — **RESOLVED**. The plan now explicitly documents `name`, `automation_id`, `control_type`, `class_name`; `anyOf` requiring at least one; `scope` (`desktop`/`foreground`/`window`); `match` (`exact`/`contains`/`startswith`); `window_name` rules for `scope=window`; and parent-not-found returns.

3. **`launch_app` `.lnk` parsing** — **RESOLVED**. The plan now specifies `win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk_path)` to read `.TargetPath`, which is the correct and feasible approach for resolving shortcut targets on Windows.

4. **`run` command parsing** — **RESOLVED**. The plan now uses separate `command` + `args` fields, `shutil.which` for PATH lookup, `Path(command).resolve()` for path resolution, and `subprocess.run([executable, *args], ...)` for argument forwarding. This avoids the earlier `shlex.split` POSIX-on-Windows pitfall.

5. **Unified security response format** — **RESOLVED with explicit policy**. The plan clarifies that all *blocking actions* return `{"error": "..."}` via `SafetyError`, while `find_control` (a query tool) returns a structured `found: false, blocked: true` response when `sensitive_check=True`. The distinction is principled and documented.

6. **`wait_for_window`/`wait_for_control` return semantics (`present` field)** — **RESOLVED**. The `found` field has been replaced with `present`, making `exists=False` semantics unambiguous: success returns `{"present": false, "timeout": false}`, timeout returns `{"present": true, "timeout": true}`.

7. **`run`/`inspect_point` return structures** — **RESOLVED**. Both tools now have return JSON definitions in Appendix A.

## 前置自检 (Q1-Q5)

- **Q1: 是否可直接作为 implementer 手册执行？** — **PASS**. 所有新工具 schema、返回结构、字段语义、执行顺序、安全策略均已落盘；实施顺序和改动文件清单清晰。
- **Q2: 输入/返回/语义是否完整且无歧义？** — **PASS**（保留非阻塞建议）. 附录 A 覆盖了全部新增工具；`find_control` 多参数并存时的优先级顺序仍可做一层说明，但已不影响实现。
- **Q3: 技术方案在当前代码库是否可行？** — **PASS**. `WScript.Shell`、UIA descendants 遍历、`shutil.which` + `subprocess.run`、`win32com` Shell 枚举均为 Windows 上成熟方案，与现有 `safety.py` / `ui_automation.py` / `mcp_server.py` 兼容。
- **Q4: 安全策略与现有 safety.py 是否一致、无绕过？** — **PASS**. `click`/`move_to` 解析控件后必须将进程名/类名/控件类型传入 `check_target_window`；`run`/`launch_app` 共享白名单；命令注入通过元字符拦截；阻断动作统一走 `SafetyError` 路径。
- **Q5: 测试与验收标准是否可执行？** — **PASS**. 分层测试策略（mock / manual marker / CI 跳过 / 回归测试）、验收清单、基准测试要求均已明确。

## 设计审查 (DR1-DR7)

- **DR1: 完整性** — 良好。所有新工具的输入 schema、返回结构、错误分支、默认参数均已定义；`find_control` 空结果分支覆盖 UIA 未安装、未命中、父窗口未找到、被拦截四种场景。
- **DR2: 技术正确性** — 良好。`.lnk` 解析改为 `WScript.Shell.Shortcut`；`run` 放弃 `shlex.split` 改为 `command`/`args` 分离；`wait_*` 使用 200ms 轮询是合理 MVP 方案。
- **DR3: 安全性** — 良好。白名单、元字符前置拦截、敏感进程/窗口检查、密码框检查均有涉及；查询与动作的返回策略有清晰边界。
- **DR4: 与现有代码一致性** — 良好。`inspect_point` 内部函数已存在，计划仅将其注册并补充返回说明；`safety.check_target_window` 参数签名与现有代码对齐。
- **DR5: 可测试性** — 良好。 mock 测试、manual marker、`pytest.ini` 注册、CI 环境跳过均有说明。
- **DR6: 风险管理** — 良好。风险矩阵覆盖了 UIA 兼容性、`launch_app` 歧义、白名单误拦截、等待超时、命令注入等主要风险，并给出缓解措施。
- **DR7: 可维护性/文档** — 良好。明确需要同步更新 `docs/api.md`、`CHANGELOG.md`、`docs/CURRENT.md`，并遵守 `AGENTS.md` 同步规则。

## New Blocking Issues (if any)

无。

## Suggestions (non-blocking)

1. **`find_control` 多参数优先级顺序再明确一层**：当前文案“多参数同时存在时按‘名称 → automation_id → control_type → class_name’的顺序组合过滤”可能被误解为优先级递减（只取其一）。建议补充说明这是“AND 组合过滤的遍历/优化顺序”，所有提供的字段都需同时满足。

2. **`launch_app` CSIDL 枚举建议补充路径获取方式**：`Shell.Application.Namespace` 接受的是文件夹路径字符串或特殊文件夹常量对象。建议说明如何通过 `win32com.shell.shell.SHGetFolderPath` 或 `shellcon.CSIDL_*` 取得实际路径，避免实现者直接传入 CSIDL 整数字面量。

3. **`run` 元字符检测给出具体正则/代码示例**：当前已列出 `&`、`|`、`;`、`&&`、`||`、`>`、`<`、`>>`、`^`、`%...%`、`$()`、反引号、换行符，但 `%...%` 和 `$()` 的具体检测逻辑仍可细化（如 `r'%[^%]+%'`、`r'\$\s*\('）。

4. **`inspect_point` 未命中控件时的行为**：建议在附录 A 补充“当指定坐标下无控件时返回/报错”的说明，与现有 `ui_automation.py` 行为保持一致。

5. **Phase 4 可提前或与 Phase 1 并行**：调整 `screenshot`/`ocr` 工具描述及 `docs/api.md` 风险低、无回归，可与其他阶段并行以缩短交付周期。

## Summary

本轮修订已完整解决 round-blind-2 提出的 7 个阻塞问题：所有新工具的 JSON Schema 与返回结构已在 Appendix A 中落地；`find_control` 参数语义完整；`launch_app` 改用 `WScript.Shell` 解析 `.lnk`；`run` 改为 `command`/`args` 分离并使用 `subprocess.run([...])`；安全响应格式按“查询工具结构化 / 动作工具 `SafetyError`”的原则统一；`wait_*` 返回值改用 `present` 字段；`run` 与 `inspect_point` 返回结构已补齐。

未发现新的阻塞性问题。计划可作为 implementer 手册进入执行阶段，建议接受并进入 Phase 1。
