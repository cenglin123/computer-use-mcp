# Acceptance Review

## Verdict
需修复

## Acceptance Criteria Check
- [x] find_control returns correct control info  
  `find_control("注册表清理程序")` 默认按 `contains` 匹配，返回正确的中心坐标、矩形、控件类型与进程名。单元测试 `test_find_control_by_name_contains` 等覆盖该场景。
- [x] wait_for_window behaves as specified  
  实现每 200ms 轮询一次，窗口出现后在 ≤200ms 内返回，满足“1 秒内返回”要求；`exists=False` 语义也正确反转。
- [x] launch_app mechanism implemented  
  `launcher.py` 通过 `Shell.Application` 枚举开始菜单/桌面 `.lnk`，使用 `WScript.Shell` 解析目标路径，支持精确/子串匹配、多匹配歧义提示、白名单与敏感进程检查。
- [x] click/move_to support target_name  
  `click`/`move_to` schema 使用 `oneOf` 表达 `target_name` 或 `(x,y)` 必填，实现优先 UIA 定位、命中后做安全检查，未命中可回退坐标。
- [x] benchmark script provided  
  `scripts/benchmark_hibit.py` 已提供，支持 `--runs`、`--warmup-runs`、冷/热启动、 Phase 耗时报告，并带 `--yes` 手动确认与 CI 拒绝机制。
- [x] tests pass  
  重新运行 `.venv/Scripts/pytest tests/ -v`：**142 passed, 0 failed**。

## Schema Compliance
| Tool | Verdict | Notes |
|------|---------|-------|
| `find_control` | PASS | inputSchema、返回结构与附录 A 一致；`window_name` 未在 schema 中条件必填，但运行时会补 `ValueError`。 |
| `inspect_point` | PASS | schema 与附录 A 一致；返回额外包含 `is_password`，不影响使用。 |
| `wait_for_window` | PASS | schema 与返回结构均符合附录 A，`exists=False` 超时语义正确。 |
| `wait_for_control` | BLOCK | schema 符合，但语义未实现：未真正检查控件的 `Enabled`/`Visible`，成功时固定返回 `enabled: true, visible: true`。 |
| `launch_app` | PASS | schema、返回结构与附录 A 完全一致。 |
| `run` | PASS | schema、返回结构与附录 A 完全一致。 |

## Safety Review
BLOCK（存在策略一致性问题）

- `find_control` 默认 `sensitive_check=True`，命中敏感窗口时返回结构化 `blocked: true` 结果，符合计划。
- `run` 先拦截 shell 元字符，再解析并校验 `allowed_commands` 白名单，使用 `subprocess.run([...])` 列表传参，符合计划。
- `launch_app` 共享 `allowed_commands` 白名单，并对目标进程调用 `check_target_window`，符合计划。
- **问题**：`click`/`move_to` 通过 `target_name` 命中控件后，调用 `check_target_window(result.get("process_name"), result.get("class_name"), result.get("control_type"))`，但 `find_control` 的 `_info_to_result` 未返回 `class_name`，导致敏感窗口类（如 `#32770`）检查被绕过。计划明确要求“必须将控件所属进程名、窗口类名、控件类型传入 `check_target_window`”。
- **问题**：`wait_for_control` 未做安全检查，且未校验真实可用状态，可能误导模型认为不可交互控件已可用。

## Documentation Review
PASS（含小瑕疵）

- `docs/api.md` 已新增“视觉理解工作流”、控件类/启动类工具约定、典型调用示例，与实现基本对齐。
- `CHANGELOG.md` 按 Phase 1-5 记录了本次改进，`docs/CURRENT.md` 已更新为 Phase 5 完成状态。
- 小瑕疵：`docs/api.md` 中把键盘输入工具写成 `type_text`，而实际注册的工具名为 `type`，建议统一。

## Regression Check
PASS

- 全量测试通过（142 passed），未观察到现有坐标点击、截图、OCR、安全校验等接口被破坏。
- `click`/`move_to` 的旧坐标调用路径仍工作正常（见 `test_click_by_coords_still_works`）。
- 新增测试对 `find_control`、`wait_for_window`、`wait_for_control`、`launch_app`、`run`、OCR preheat 等均有覆盖。
- 当前环境未安装 `pytest-cov`，无法量化覆盖率；建议后续安装覆盖率插件并设置 ≥80% 门限。

## Blocking Issues (if any)

1. **`click`/`move_to` 的 `target_name` 安全校验缺少 `class_name`**  
   原因：`find_control` 返回结果未包含 `class_name`。  
   修复建议：在 `_info_to_result` 中增加 `"class_name": info.class_name`，确保 `_dispatch_pointer_tool` 能把 `class_name` 传入 `check_target_window`。

2. **`wait_for_control` 未按语义检查 `Enabled`/`Visible`**  
   原因：当前仅通过 `found.get("found")` 与 `center` 判断可用，成功返回值固定为 `enabled: true, visible: true`，与计划定义及 `docs/api.md` 描述不符。  
   修复建议：在轮询时获取控件实际属性（或扩展 `find_control` 返回 `enabled`/`visible`），仅当 `Exists and Enabled and Visible` 时才认为可用。

## Suggestions (non-blocking)

- 在 `find_control` 的 `inputSchema` 中通过 `dependentRequired` 或文档说明 `scope=window` 时 `window_name` 必填。
- 统一 `docs/api.md` 中 `type` 工具名称（当前写为 `type_text`）。
- 安装 `pytest-cov` 并在 CI/测试流程中加入覆盖率检查，确保新增模块覆盖率 ≥80%。
- 为 `wait_for_control` 补充针对 disabled/invisible 控件的单元测试。

## Summary

本次实现基本完成了计划中的 5 个阶段：UIA 控件工具族、`launch_app`/`run`、语义化 `click`/`move_to`、视觉理解引导、OCR 预热与基准脚本均已落地，且全部 142 个测试通过。但在作为验收关键的**安全策略一致性**和 **`wait_for_control` 语义准确性**上存在两个阻塞性问题，需要在修复后重新验收。建议在修复后补充相关单元测试并再次运行全量测试。
