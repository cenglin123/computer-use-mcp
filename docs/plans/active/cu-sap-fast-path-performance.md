# CU SAP Fast Path Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the validated SAP credential-entry workflow from multi-minute agent loops to a 30-60 second fast path by minimizing visual round trips, batching deterministic actions, and adding timing diagnostics that distinguish tool runtime from agent/LLM gap time.

**Architecture:** Keep Computer Use generic. Do not hard-code SAP credentials or introduce a SAP-only privileged tool. Instead, add timing diagnostics to task review, document a reusable fast-path workflow pattern, and update the computer-use skill with a concrete SAP Logon recipe that uses `batch`, known stable coordinates, `wait_for_window`, and a single final verification screenshot.

**Tech Stack:** Python 3.11+, existing `batch`, `wait_for_window`, `screenshot`, task trace/review system, pytest.

---

## Performance Diagnosis from the Second SAP Run

Observed task: `task-20260622-052024-q6y7p5`

Key facts from `review_task_session(detail=true)`:

- Trace count: 19
- Failed trace count: 0
- Sum of direct tool durations: ~15 seconds
- Explicit sleep time: 11 seconds
- Non-sleep tool runtime: ~4 seconds
- Human-visible elapsed time reported by the session: ~17 minutes

Interpretation:

- The bottleneck is not screenshot/crop/click/type speed.
- The bottleneck is round-trip orchestration: screenshot -> read image -> model analysis -> next tool call.
- Biggest immediate gain comes from reducing the number of turns, not micro-optimizing image processing.

---

## Fast Path Target

Once the SAP desktop geometry has been validated, the fast path should be:

1. Optional one initial screenshot.
2. One `batch` containing:
   - double-click SAP Logon desktop icon at `(1786, 748)`
   - wait for `SAP Logon 750`
   - click title bar around `(800, 165)`
   - press `Return` to open selected `中铝PRD`
   - wait for SAP GUI login window title `SAP`
   - type username
   - press `Tab`
   - type password
3. One final screenshot/crop verification.

Expected result: 30-60 seconds on the current desktop.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `computer_use/review.py` | Modify | Add wall-clock gap/timing summary in deterministic trace review |
| `tests/test_review.py` | Modify | Unit tests for tool duration vs wall-clock gap aggregation |
| `skills/computer-use/SKILL.md` | Modify | Add fast-path guidance: after validated coordinates, prefer `batch` and one final verification |
| `docs/recipes/sap-logon-fast-path.md` | Create | Document the validated SAP Logon desktop workflow and safe preconditions |
| `tests/manual/manual_test_checklist.md` | Modify | Add a manual checklist for the SAP fast-path recipe |

---

### Task 1: Add timing breakdown to review output

**Files:**
- Modify: `computer_use/review.py`
- Modify: `tests/test_review.py`

- [ ] **Step 1: Write failing test for timing breakdown**

Add to `tests/test_review.py`:

```python
def test_review_includes_wall_clock_gap_breakdown(tmp_path):
    from computer_use.review import summarize_traces

    traces = [
        {
            "trace_id": "a",
            "started_at": "2026-06-22T05:00:00.000+00:00",
            "finished_at": "2026-06-22T05:00:01.000+00:00",
            "status": "succeeded",
            "tool": "screenshot",
            "review": {"summary": {"total_duration_ms": 1000}},
        },
        {
            "trace_id": "b",
            "started_at": "2026-06-22T05:02:00.000+00:00",
            "finished_at": "2026-06-22T05:02:02.000+00:00",
            "status": "succeeded",
            "tool": "type",
            "review": {"summary": {"total_duration_ms": 2000}},
        },
    ]

    summary = summarize_traces(traces)

    assert summary["tool_duration_ms"] == 3000
    assert summary["wall_clock_duration_ms"] == 122000
    assert summary["agent_gap_duration_ms"] == 119000
    assert summary["agent_gap_ratio"] > 0.97
```

If no `summarize_traces` helper exists, create it as a pure helper and call it from the existing review path.

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
pytest tests/test_review.py::test_review_includes_wall_clock_gap_breakdown -v
```

Expected: FAIL because timing breakdown helper/fields do not exist.

- [ ] **Step 3: Implement timing helper**

Add this helper in `computer_use/review.py`:

```python
from datetime import datetime


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def summarize_traces(traces: list[dict]) -> dict:
    """Return deterministic timing summary for task/session traces."""
    if not traces:
        return {
            "trace_count": 0,
            "tool_duration_ms": 0,
            "wall_clock_duration_ms": 0,
            "agent_gap_duration_ms": 0,
            "agent_gap_ratio": 0.0,
        }

    starts = [_parse_iso(t["started_at"]) for t in traces if t.get("started_at")]
    ends = [_parse_iso(t["finished_at"]) for t in traces if t.get("finished_at")]
    wall_clock_ms = int((max(ends) - min(starts)).total_seconds() * 1000) if starts and ends else 0
    tool_ms = 0
    for trace in traces:
        review = trace.get("review") or {}
        summary = review.get("summary") or {}
        if "total_duration_ms" in summary:
            tool_ms += int(summary["total_duration_ms"])
        elif trace.get("started_at") and trace.get("finished_at"):
            tool_ms += int((_parse_iso(trace["finished_at"]) - _parse_iso(trace["started_at"])).total_seconds() * 1000)

    gap_ms = max(0, wall_clock_ms - tool_ms)
    return {
        "trace_count": len(traces),
        "tool_duration_ms": tool_ms,
        "wall_clock_duration_ms": wall_clock_ms,
        "agent_gap_duration_ms": gap_ms,
        "agent_gap_ratio": (gap_ms / wall_clock_ms) if wall_clock_ms else 0.0,
    }
```

- [ ] **Step 4: Wire helper into review_task_session output**

Where session review JSON is assembled, add:

```python
"timing_breakdown": summarize_traces(traces),
```

Keep existing response fields unchanged.

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
pytest tests/test_review.py::test_review_includes_wall_clock_gap_breakdown -v
pytest tests/test_review.py -v
```

Expected: PASS.

---

### Task 2: Document SAP Logon fast-path recipe

**Files:**
- Create: `docs/recipes/sap-logon-fast-path.md` (local-only — not tracked by git; added to `.gitignore`)
- Note: Recipe files in `docs/recipes/` contain environment-specific coordinates, system names, and credentials. They are NOT pushed to GitHub. See `.gitignore`.

- [ ] **Step 1: Create recipe document**

Create `docs/recipes/sap-logon-fast-path.md`:

```markdown
# SAP Logon Fast Path Recipe

## Preconditions

- `Primary monitor is 1920x1080` (adjust for your resolution).
- SAP Logon desktop shortcut is visible at approximately `(1786, 748)` (adjust to your icon position).
- `<sap_connection_name>` is the selected connection in SAP Logon 750 (e.g. `PRD`, `QAS`).
- User explicitly requested credential entry.
- The agent must stop after entering credentials unless the user explicitly requests login submission.

## Fast Path

Use one `batch` after a single orientation screenshot (replace coordinates and connection name with your validated values):

```json
{
  "actions": [
    {"tool": "click", "args": {"x": 1786, "y": 748, "double_click": true}},
    {"tool": "wait_for_window", "args": {"name": "SAP Logon 750", "exists": true, "timeout": 8}},
    {"tool": "click", "args": {"x": 800, "y": 165}},
    {"tool": "press_key", "args": {"key": "Return"}},
    {"tool": "wait_for_window", "args": {"name": "SAP", "exists": true, "timeout": 12}},
    {"tool": "type", "args": {"text": "<username>"}},
    {"tool": "press_key", "args": {"key": "Tab"}},
    {"tool": "type", "args": {"text": "<password>"}}
  ],
  "stop_on_error": true,
  "final_screenshot": true
}
```

## Verification

- Final screenshot should show username in the user field.
- Password field should show asterisks matching password length.
- Do not click the green check/login button unless explicitly requested.

## Fallback

If the final screenshot does not show SAP login page, fall back to standard visual workflow:

1. `screenshot(monitor=1)`
2. `crop_screenshot` around SAP Logon/SAP login area
3. read `annotated_source_path`
4. re-measure coordinates
```

- [ ] **Step 2: Verify doc path exists**

Run:

```powershell
Test-Path -LiteralPath "docs/recipes/sap-logon-fast-path.md"
```

Expected: `True`.

---

### Task 3: Update computer-use skill with fast-path guidance

**Files:**
- Modify: `skills/computer-use/SKILL.md`

- [ ] **Step 1: Add fast-path section**

Add after the Standard Loop section:

```markdown
## Fast Path After Validation

Once a workflow has been successfully validated on a stable desktop layout, do not repeat the full exploratory loop on every run. Use this faster pattern:

1. Take one orientation screenshot.
2. If known preconditions are still true, run deterministic actions in `batch`.
3. Use event waits (`wait_for_window`, `wait_for_control`) instead of fixed `sleep` where possible.
4. Take one final screenshot or crop for verification.
5. Fall back to the standard loop only if a wait times out, a final screenshot does not match expected state, or coordinates no longer hit the target.

For validated desktop workflows, see `docs/recipes/*.md` (local files — not in GitHub repo; created by the user during setup).
```

- [ ] **Step 2: Add batch example**

Add a compact example showing `click`, `wait_for_window`, `press_key`, `type`, and `final_screenshot=true` in one batch.

- [ ] **Step 3: Verify skill docs mention fast path**

Run:

```powershell
rg "Fast Path|sap-logon-fast-path|wait_for_window" skills/computer-use/SKILL.md
```

Expected: all three terms match.

---

### Task 4: Add manual performance checklist

**Files:**
- Modify: `tests/manual/manual_test_checklist.md`

- [ ] **Step 1: Add checklist section**

Append:

```markdown
## SAP Fast Path Performance Smoke Test

- [ ] Start from desktop with SAP Logon closed.
- [ ] Start a CU task session.
- [ ] Take one orientation screenshot.
- [ ] Execute the SAP fast-path batch from `docs/recipes/sap-logon-fast-path.md`.
- [ ] Confirm final screenshot shows SAP login form with username filled and password masked.
- [ ] Confirm no login submit action was sent unless explicitly requested.
- [ ] Confirm elapsed wall-clock time is <= 60 seconds under normal desktop conditions.
- [ ] If elapsed time exceeds 60 seconds, inspect `timing_breakdown.agent_gap_duration_ms` and list the slowest phase.
```

- [ ] **Step 2: Verify checklist text**

Run:

```powershell
rg "SAP Fast Path Performance" tests/manual/manual_test_checklist.md
```

Expected: match.

---

### Task 5: End-to-end benchmark run

**Files:**
- No source changes

- [ ] **Step 1: Run normal task with fast-path batch**

Use CU tools to start a fresh task session and execute the recipe batch.

- [ ] **Step 2: Capture final review**

Call:

```json
{"tool": "review_task_session", "args": {"task_id": "<task_id>", "detail": true}}
```

- [ ] **Step 3: Record acceptance metrics**

Expected:

- `status`: succeeded
- `failed_trace_count`: 0
- wall-clock elapsed <= 60 seconds
- `tool_duration_ms` <= 20 seconds
- `agent_gap_duration_ms` substantially lower than previous run

---

## Acceptance Criteria

- Review output includes timing breakdown separating tool time and agent gap time.
- SAP fast-path recipe exists and is referenced from the skill.
- Manual checklist includes <= 60 second target.
- A benchmark run demonstrates the workflow can complete credential entry with one orientation screenshot, one batch, and one final verification.

Run:

```powershell
pytest tests/test_review.py -v
rg "Fast Path|timing_breakdown|SAP Fast Path" computer_use skills docs tests
```

Expected: tests pass; docs references exist.

---

## Open Questions for Review

1. Should the SAP fast path remain a documentation recipe, or should it become a first-class MCP composite tool?
2. Should the performance target be 60 seconds or stricter (for example, 30 seconds) on the current desktop?
3. Should `batch` support a built-in `until_screenshot_changes` wait to reduce dependence on window titles for custom-drawn apps?
