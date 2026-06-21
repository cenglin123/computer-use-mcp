# Design Review: activate-window-and-skill-hardening

> Advisory review — single round, no blocking force.

```yaml
design_review:
  dimensions:
    - name: consistency
      status: concerns_found
      findings:
        - finding: |
            `activate_window` uses `_find_window_by_name` from `ui_automation.py`, which
            only supports case-insensitive "contains" matching. This is consistent with
            `wait_for_window` (same function), but inconsistent with the broader tool
            ecosystem where `find_control`/`click`/`move_to` offer an explicit `match`
            parameter (exact/contains/startswith). A caller wanting exact activation
            (e.g., targeting "Notepad" without hitting "Notepad++") has no way to express
            this, and must add a post-hoc process_name check.
          location: "§A, §实现要点 — match parameter absent"
          impact: >
            Forces callers into a "activate first, verify afterward" pattern when
            exact matching is needed. The inconsistency is visible at the tool schema
            level: all other UIA search tools expose `match`; `activate_window` would
            be the odd one out (alongside `wait_for_window` which shares the same gap).
        - finding: |
            The plan aligns `activate_window`'s safety mechanism with `find_control`'s
            sensitive-window detection (through `check_target_window`), while noting
            that `launch_app` uses a whitelist. This cross-reference is self-consistent
            and correctly recognizes that the two tools operate at different privilege
            levels (pre-launch vs post-launch).
          location: "§A, 实现要点 bullet 3"
          impact: No issue — explicit and correct.
    - name: completeness
      status: concerns_found
      findings:
        - finding: |
            `_find_window_by_name` returns the first descendant with
            `ControlTypeName == "window"`, but many real app windows appear as "Pane",
            "Custom", or "Document" in UIA. The filter may miss the target. After the
            plan, `activate_window` returns `not_found` while `wait_for_window` returns
            `present: false` for the same window — inconsistent behavior for the same
            input.
          location: "§A — window-type strictness in `_find_window_by_name`"
          impact: >
            Cases where a window exists but is classified differently by UIA would
            cause `activate_window` to fail silently (not_found), frustrating callers
            who already confirmed existence via `wait_for_window`.
        - finding: |
            Missing WindowPattern capability check. Not every window control implements
            the WindowPattern required by `SetActive()` (or `SetWindowVisualState`).
            Plan assumes the returned object is a `WindowControl`, but UIA controls
            returned by tree traversal are generic — calling SetActive on a control
            without the pattern raises COM exception, caught by the try/except and
            returned as `activate_failed`. This works but sends a confusing signal:
            "found the window but can't activate it".
          location: "§A — no pattern availability check before SetActive()"
          impact: >
            A caller who finds the window and confirms existence cannot distinguish
            between "temporarily blocked by UIPI" and "this window fundamentally does
            not support activation". Recovery path is unclear.
        - finding: |
            Multi-desktop silent failure is documented but not detected. When the
            target window is on another virtual desktop, `SetActive()` may return
            success (S_OK) without actually bringing the window to the current desktop.
            The tool returns `activated: true` while the window remains invisible.
          location: "§A, 多虚拟桌面边界 bullet"
          impact: >
            A correctness gap: the tool's return value does not reflect real-world
            state. The caller has no way to distinguish "activated on current desktop"
            from "silently no-op on another desktop" without post-hoc verification
            (e.g., `get_ui_snapshot`). The gap is documented but not mitigated.
        - finding: |
            `SetWindowVisualState(WindowVisualState.Normal)` does not preserve the
            window's previous visual state. A window that was maximized before
            minimization will be restored to the non-maximized "Normal" size, altering
            the user's layout.
          location: "§A — visual state preservation"
          impact: >
            Activation may have a side effect (un-maximizing the window) that the
            caller did not request and cannot suppress. The plan provides no parameter
            to control restore-vs-maximize behavior.
    - name: maintainability
      status: concerns_found
      findings:
        - finding: |
            Self-process detection uses recursive parent-process-name matching, which
            is robust against new agent hosts. But the SKILL guidance (§B1) hardcodes
            a separate process-name list (WindowsTerminal.exe, pwsh.exe, Cursor.exe,
            Code.exe, etc.) and instructs agents to check `find_control` results
            against it. Two parallel lists = inevitable drift.
          location: "§B.1 vs §A self-process implementation"
          impact: >
            When a new agent host appears (e.g., Windsurf, Claude Desktop update),
            the implementation tolerates it (recursive parent match), but the SKILL
            guidance still tells agents to check against an outdated hardcoded list.
            SKILL drift will cause false-positive "not sure of target process" guidance
            until manually updated.
        - finding: |
            The plan uses `Copy-Item` as the sync mechanism for SKILL.md two-copy
            distribution. There is no script, no pre-commit hook, no git alias — just
            a prose instruction in the plan. The `test_distribution_readiness` test
            detects drift post-hoc but does not prevent it.
          location: "§B, §C — SKILL sync"
          impact: >
            Low ceremony but high forgetability. In practice, the two copies will
            diverge between plan execution and test failure. Drift recovery requires
            manual re-copy, which may lose edits made to the out-of-sync copy.
    - name: boundary_clarity
      status: clean
      findings:
        - finding: |
            The plan explicitly delineates `launch_app` (start), `wait_for_window`
            (poll for existence), `activate_window` (single-shot find+activate), and
            `find_control` (locate sub-control). The `activate_window` function
            signature is documented as "no polling, caller must wait first" — clear
            composition contract.
          location: "§A, §范围外"
          impact: No issue — clean boundary.
    - name: residue_and_redundancy
      status: concerns_found
      findings:
        - finding: |
            SKILL.md Quick Reference will need a new row for `activate_window`. This
            row plus the B1/UIA-ownership guidance plus the Standard Loop updates
            means three separate edits to the same file. The plan calls them B.1
            through B.6 but does not cross-reference them to avoid conflicts.
          location: "§B.1–B.6"
          impact: >
            Low risk in a single-plan execution, but these are all edits to the same
            file section from different motivations. An incremental or partial
            execution could miss one.
        - finding: |
            `docs/CURRENT.md` is not mentioned in the plan's document list (§C). Per
            AGENTS.md, task status should be recorded in CURRENT.md.
          location: "§C"
          impact: >
            Minor omission. The project convention expects CURRENT.md updates for
            active tasks.
    - name: portability
      status: concerns_found
      findings:
        - finding: |
            The plan correctly documents that multi-desktop and UIPI behavior vary
            by Windows version and integrity level. However, there is no runtime
            detection: the tool cannot report which behavioral regime applies.
            "Documented limitation" shifts the detection burden entirely to the caller.
          location: "§A, 多虚拟桌面 + UIPI"
          impact: >
            Agent using `activate_window` on an unknown Windows version has no
            programmatic way to determine if activation on another desktop is
            working. The agent must perform additional verification steps, increasing
            round-trip cost.
        - finding: |
            The plan implicitly relies on `psutil` being available at the point of
            the self-process check (parent process tree traversal). `psutil` is a
            pre-existing dependency (used in `_get_process_name`), so this is safe
            in the current project. However, if `psutil` import were to fail for any
            reason, the self-activation check would silently degrade: `Process(pid)`
            would raise, caught by the generic except in `_get_process_name`, and
            `process_name` would return `None` — the self-activation check passes
            (process_name mismatch detected as `None ≠ python.exe`). Self-activation
            would succeed when it should have been blocked.
          location: "§A — psutil dependency in self-process check"
          impact: >
            A silent safety degradation path. The `_get_process_name` function at
            ui_automation.py:225-234 wraps everything in a broad `except Exception`,
            which would mask a psutil import failure and return `None`. The caller
            (self-process check) sees `None` and concludes "not our process".
    - name: scalability
      status: concerns_found
      findings:
        - finding: |
            Self-process exclusion in the implementation is scalable (recursive parent
            matching works for any number of agent hosts). The SKILL guidance's
            hardcoded process-name list does not scale and must be maintained manually.
          location: "§B.1 — hardcoded process list in SKILL"
          impact: >
            Recurring maintenance burden. Each new agent host requires a SKILL.md
            edit. The gap between implementation (generic, no-edit) and guidance
            (specific, needs-edit) grows over time.
        - finding: |
            The `mcp_server.py` dispatch uses a flat if/elif chain that already
            exceeds 800 lines. Adding `activate_window` adds one more branch. The
            plan does not refactor or address dispatch scalability.
          location: "§A, mcp_server.py"
          impact: >
            Not a concern now (one more branch is fine), but the dispatch pattern
            does not structurally scale to 50+ tools. Not introduced by this plan,
            but the plan does not mitigate it either.
  highlights:
    - finding: |
        Self-process detection has two parallel mechanisms — one in code (recursive
        parent matching, robust) and one in SKILL guidance (hardcoded process name
        list, fragile). They will drift.
      why_it_matters: |
        The SKILL guidance is the primary instruction agents follow. If it tells agents
        to compare against an outdated process list, agents will either waste time on
        false ownership questions (process not in list) or skip safety checks (wrong
        conclusion). Drift between code and guidance is hard to notice until a safety
        incident occurs.
      suggested_direction: |
        Replace the hardcoded process-name-list in SKILL guidance with a single
        directive: "use `activate_window`'s returned `process_name` and compare it
        against the parent process of your current MCP server process (accessible
        via standard OS introspection)". Give agents a reusable recipe rather than a
        perishable enumeration.
    - finding: |
        `activate_window` cannot detect "success that did nothing" — silent failure
        on another virtual desktop returns `activated: true`.
      why_it_matters: |
        Callers trust the return value. If `activated: true` can mean "nothing
        happened", every activation must be followed by `get_ui_snapshot` or
        `screenshot` to verify — doubling the cost of activation and eroding trust
        in the tool contract.
      suggested_direction: |
        After `SetActive()`, add a lightweight follow-up: query the foreground
        window's name/pid and compare it to the target. If they match, report
        `verified: true`. If they don't match (including multi-desktop silent
        failure), return `activated: false, reason: "focus_verification_failed"`.
        This converts a silent gap into an explicit signal.
    - finding: |
        WindowPattern capability is not checked before calling `SetActive()`. A
        found-but-non-activatable window yields the same `activate_failed` as a
        UIPI-blocked window — indistinguishable.
      why_it_matters: |
        Distinguishing unrecoverable errors (window doesn't support activation) from
        transient ones (UIPI, another desktop) determines the caller's recovery
        strategy. Without this distinction, agents must either retry blindly or give
        up prematurely.
      suggested_direction: |
        Before calling `SetActive()`, check if the control supports the WindowPattern
        via `GetPattern(UIA_WindowPatternId)` or equivalent. If not supported, return
        a distinct reason (e.g., `"activation_not_supported"`). Keep the COM-exception
        fallback for UIPI and other transient failures.
```
