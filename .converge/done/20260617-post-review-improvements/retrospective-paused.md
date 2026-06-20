# Converge Retrospective（暂停版）· 20260617-post-review-improvements

## 状态

- **暂停原因**：用户要求在继续前复盘，因为审计轮数远超预期。
- **当前阶段**：盲审复核阶段，未收敛。
- **已完成轮次**：20 轮常规评审 + 11 次盲审复核（BR5–BR15）。
- **产物**：`docs/plans/active/post-review-improvements-2026-06-17.md` 已根据反馈多次修订。

## 为什么轮数这么多？

1. **Plan 过度包含可执行代码细节**
   - 本 plan 不是纯策略文档，而是直接给出了 fixture、RED 测试、常量定义等代码片段。
   - 每引入一段代码，就为 reviewer 提供了新的实现层审查面：import 顺序、mock 完备性、异常路径、进程清理、marker 命名等。
   - 结果：修复 A 后，B、C、D 等实现细节问题被逐层发现。

2. **盲审 reviewer 不断提出新的实现层假设**
   - 常规评审阶段主要解决方向性问题（scope、职责划分、OCR 声明、混合 DPI 排除）。
   - 进入盲审后，fresh reviewer 从代码可读性角度反复发现：
     - `_TASK_CONTEXT_EXCLUDED_TOOLS` 导入遗漏
     - `win32gui` 顶层导入导致 collection 崩溃
     - `_get_shell_dispatch` mock 不够鲁棒
     - `subprocess.Popen` 与 `ManagedApp` 创建顺序导致进程泄漏
     - 已有 `manual` marker 与新增 `integration` marker 冲突
   - 这些 issue 并非重复，说明 plan 中代码片段确实未达到可直接执行的质量。

3. **P0 排除 gate 未被预先关闭**
   - 原始评审的 #1 P0 项「混合 DPI 多显示器支持」被排除，但需要用户/维护者书面确认。
   - 该 gate 作为前置条件写入验收标准，导致 plan 在缺少用户确认前无法被判为「可执行」。
   - 这是合理的 scope 决策，但也说明 plan 层面无法自证收敛。

## 发现的典型问题分类

| 类别 | 例子 | 解决方式 |
|------|------|----------|
| 导入与可选依赖 | `win32gui` 顶层导入、`uiautomation` 可选 | `try/except` + `pytest.skip`、`pytest.importorskip` |
| Mock 自包含性 | RED 测试未 mock shell dispatch | 提供 `SimpleNamespace` fake 对象 |
| 资源生命周期 | Popen 后才创建 ManagedApp | 先注册再等待，失败时立即 close |
| 约定冲突 | 新增 `integration` vs 已有 `manual` | 复用现有 marker |
| Scope 诚实 | OCR、混合 DPI、视觉 fallback | 在「不包含」中显式列出并说明替代方案 |
| 可维护性 | 行号引用、「已验证」声明 | 改为函数/模块级引用、「当前实现中」 |
| 错误消息语义 | `_BLOCKED_ERROR` 同时用于白名单和敏感进程 | 拆分为 `_NOT_ALLOWED_ERROR` + `_SENSITIVE_PROCESS_ERROR` |
| Schema 迁移完整性 | `_TASK_CONTEXT_EXCLUDED_TOOLS` 未导入 | 在导入示例中补全 |

## 反模式观察

- **archaeology_leftover**：plan 中大量「已验证」声明，是作者基于代码考古的私有知识，blind reviewer 无法独立验证。
- **marker proliferation**：未先检查已有约定就新增 `integration` marker，造成语义重叠。
- **over-specification in plan**：把本应在执行阶段由 executor 处理的代码细节（如具体 mock 对象）写进 plan，导致 plan 成为第二份代码并产生维护负担。

## 当前剩余阻塞

1. **用户确认**：P0 混合 DPI 排除需用户/维护者书面确认（frontmatter `mixed_dpi_exclusion_ack: pending`）。
2. **（潜在）更多实现细节**：即使确认后，新一轮盲审仍可能发现代码片段层面的问题。

## 可选路径

用户可在以下选项中选择：

1. **确认混合 DPI 排除，继续盲审复核**
   - 关闭 P0 gate，再跑 1–2 轮盲审；若通过即可收敛并执行。
   - 风险：仍可能发现新实现细节问题。

2. **确认混合 DPI 排除，接受当前 plan 并进入执行**
   - 把当前 plan 视为「足够好」，由执行者临场处理代码细节。
   - 风险：执行阶段可能遇到 plan 未覆盖的问题，需即时修复。

3. **简化 plan，移除代码片段，重新收敛**
   - 把 plan 改为纯任务/验收/文件列表，不写具体代码。
   - 优势：收敛更快；劣势：执行者对代码实现有更大解释权，可能偏离意图。

4. **将混合 DPI 纳入本 plan**
   - 重新设计 Task 1/3/5 以包含混合 DPI 支持。
   - 需要显著扩大 scope 和时间预算。

## 建议

考虑到已经投入大量评审成本且 plan 的方向性问题已解决，**推荐路径 2**：
- 用户确认混合 DPI 排除；
- 再跑一轮盲审（BR12）作为最终检查；
- 若 BR12 无结构性/概念性阻塞，即使存在少量 implementation 建议也接受；
- 进入执行，并在执行时由 executor 处理剩余的代码细节。

如果用户对代码细节零容忍，则选择路径 3，重置 plan 为高层描述后重新收敛。

## 记录

- 默认 converge 预算已严重超出：`max_outer_loops=5`，`max_blind_rechecks=2`；当前已进行 20 轮常规 + 11 次盲审。
- 继续迭代必须有明确的用户授权或 scope 调整。
