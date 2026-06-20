# Blind Recheck 9 · 20260617-post-review-improvements

## Trigger

Ninth blind recheck after BR8 amendments.

## Reviewer

Blind recheck reviewer (ses_124ee8563ffeuXPR1DDWOd8Arh)

## Verdict

阻断需修复

## Blocking Issues

1. **结构性**：Task 1 fixture 在 `_launch` 中先启动 notepad，然后才创建 `ManagedApp`；若窗口激活超时失败，`ManagedApp` 尚未加入 `launched`，teardown 无法终止进程，导致 notepad 遗留。
   - Fix: 在调用 `subprocess.Popen` 后立即创建 `ManagedApp` 并加入 `launched`，再尝试激活窗口；激活失败时调用 `app.close()`。

2. **概念性**：验收标准要求混合 DPI P0 排除获得书面确认，但未说明确认机制、记录位置。
   - Fix: 在 Task 5 新增 Step 1「确认 P0 排除签收 Gate」，规定确认方式（frontmatter 或提交消息引用来源）。

3. **结构性**：Task 2 RED 测试将 `_get_shell_dispatch`/`_get_wscript_shell` mock 为裸 `object()`，假设它们只在白名单检查后被使用；若未来实现调整顺序，测试会提前失败。
   - Fix: 使用 `SimpleNamespace` 提供最小 fake shell/wscript 对象。

4. **实现层**：Task 1 测试直接对 `_call_tool` 结果调用 `json.loads()` 并断言字段；计划使用「已验证」声明，但 blind reviewer 无法独立核实。
   - Fix: 将「已验证/已确认」改为「当前实现中」，并在测试代码中增加返回类型假设注释。

## Suggestions (non-blocking)

- audit 应在 changelog add 之后，或再补一次 audit。
- `_wait_and_activate_window` 超时预算划分 awkward。
- Task 3 RED 测试应断言 `_attach_task_context_schemas()` 附加了 `task_id` schema。

## Antipattern Observed

- archaeology_leftover: 多处「已验证」声明是基于代码考古的私有知识，blind reviewer 无法独立验证。

## Follow-up

Amended fixture to register proc before window wait, added P0 gate step, strengthened launcher RED test mocks, replaced 「已验证/已确认」with 「当前实现中」and added JSON return-type assumptions. Proceed to blind recheck 10.
