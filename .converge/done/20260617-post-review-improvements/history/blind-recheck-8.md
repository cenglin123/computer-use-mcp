# Blind Recheck 8 · 20260617-post-review-improvements

## Trigger

Eighth blind recheck after BR7 amendments.

## Reviewer

Blind recheck reviewer (ses_124f8ca04ffeiMiWSoU1Ztw9KR)

## Verdict

阻断需修复

## Blocking Issues

1. **结构性**：`tests/integration/conftest.py` 在模块顶层无条件导入 `win32gui`；pytest 在收集阶段即导入 conftest，即使通过 `-m "not integration"` 取消选择，缺少 `pywin32` 也会导致 collection 崩溃，与“集成测试可选”矛盾。
   - Fix: 对 `win32gui` 做可选导入保护（`try/except` 置为 None），在 `_find_window_by_process` 中缺失时 `pytest.skip`。

2. **实现层**：Task 2 RED 测试未 mock `_get_shell_dispatch` 和 `_get_wscript_shell`；在缺少 `win32com` 的环境，`launch_app` 会在命中白名单分支前返回 `"Shell automation unavailable"`，导致断言因错误原因失败。
   - Fix: 在 RED 测试开头用 monkeypatch 让这两个函数返回非 None 的占位对象。

## Suggestions (non-blocking)

- 集成测试直接调用 `mcp_server._call_tool` 会写入 trace，建议考虑覆盖 `trace_dir`。
- `_wait_and_activate_window` 的内外超时预算划分 awkward，可重构。
- README.md 中集成测试说明应放在现有测试说明附近。

## Follow-up

Amended conftest to guard win32gui import; amended Task 2 RED test to mock shell dispatch helpers. Proceed to blind recheck 9.
