---
type: contract
object_slug: 20260630-skill-curation-loop
contractor: contract-proposer
round: 0 (retroactive — ultraverge completed, entering full converge loop)
generated_at: 2026-06-30T02:00:00Z
---

# Acceptance Contract · 20260630-skill-curation-loop

> This contract defines what "done" means for the Skill Curation Loop plan (`docs/plans/active/20260630-skill-curation-loop.md`). It is drafted retroactively after Round 0 (ultraverge) and constrains all subsequent convergence rounds.

---

## 1. Acceptance Criteria

Each criterion is binary: **pass** (all sub-items satisfied) or **fail** (any sub-item unsatisfied). Verification is by reading the amended plan; no execution or testing is required at this stage.

### A. Scope: MEMORY.md only
The plan must:
- [ ] Explicitly restrict the curator's write target to `.agents/memory/MEMORY.md` for Phase 1. SKILL.md is not a write target.
- [ ] Remove or revise all references to SKILL.md as a curator output destination (lines 44, 88, 98 of the current draft).
- [ ] State clearly that SKILL.md structural changes are deferred to a future phase.

### B. Curator output format: MEMORY.md entry identification
The curator's output JSON schema must:
- [ ] Replace the `skill_name` field with an identifier that locates lessons in MEMORY.md's markdown structure.
- [ ] Specify how each operation identifies its target:
  - `insert`: position (append to end of `## 已验证的重要教训`, or insert at a specified index).
  - `update`: target identified by numbered list index (`#1`–`#19` or dynamic).
  - `delete`: target identified by numbered list index.
- [ ] Specify how the curator handles **index drift** when multiple operations are applied in a single batch (e.g., process deletes in reverse order, regenerate indices after each insertion, or use stable anchor identifiers).
- [ ] Define the full JSON schema with field names, types, and examples.

### C. SkillOS paper notes resolved
Before the plan is executable:
- [ ] SkillOS paper notes (or equivalent reference material) must exist in the repository at a path referenced by the plan.
- [ ] If notes cannot be created, the plan must replace all paper-dependent references (Figure 7 for curator prompt, Figure 13 for LLM-as-judge prompt) with self-contained prompt templates or clear specifications.

### D. LLM API specification
The plan must define:
- [ ] Provider (e.g., OpenAI, Anthropic, local).
- [ ] Model name.
- [ ] Authentication mechanism (env var, config file, etc.).
- [ ] Basic transient-error handling: retry strategy for HTTP 429/503/timeout (backoff, max retries, abort behavior).
- [ ] Cost handling strategy (budget cap, cost tracking, user confirmation before expensive runs).

### E. Trigger mechanism: standalone CLI
The trigger mechanism must be:
- [ ] A standalone CLI command: `python scripts/curator.py --trace-dir <path> [--count N] [--threshold T]`.
- [ ] Documented as intentionally simple (no daemon, no file watcher, no MCP server hook).
- [ ] Batch threshold `N` and exception threshold `T` must be configurable via CLI arguments or config file, not hardcoded.

### F. Success/failure signal data contract
Phase 2's LLM-as-judge output must define:
- [ ] The concrete file path and format where judgment results are stored (e.g., `<trace_dir>/<trace_id>/judgment.json`).
- [ ] The schema of the judgment record (fields: `trace_id`, `verdict: "success"|"failure"|"ambiguous"`, `confidence: float`, `reasoning: str`).
- [ ] How Phase 1's curator reads this data. If Phase 1 must operate without Phase 2 (fallback using `finish_task` + `error_kind`), this must be documented as the default mode.

### G. Converge integration
The plan must define:
- [ ] Which converge mode applies: **standard deliberation**, single-layer. (Ultraverge initial review is complete; subsequent reviews are standard deliberation.)
- [ ] Who orchestrates converge cycles: the **human operator** invokes the CLI script; the script may auto-submit to converge, but final approval is manual.
- [ ] What rubric dimensions apply to curator output: **fidelity** (every proposed lesson must cite specific trace steps that support it), **generalization** (lesson is not overfit to specific window names/coordinates), **non-redundancy** (no overlap or conflict with existing MEMORY entries).
- [ ] How curator suggestions are packaged for converge (e.g., a diff file or structured JSON with proposed MEMORY.md changes).
- [ ] How approved changes are applied to MEMORY.md (scripted insertion/update/deletion at the correct numbered list positions).

### I. LLM output robustness
The plan must define:
- [ ] Validation of curator JSON output (structural schema check before converge review).
- [ ] Rejection handling for lessons unsupported by trace evidence (what happens when curator proposes a lesson with no supporting trace steps).
- [ ] Behavior on repeated malformed output (skip the run, warn user, abort).

### J. Trace data privacy / safety
The plan must:
- [ ] Acknowledge that trace data may contain sensitive information (window titles, file paths, error messages, user input).
- [ ] Define which trace fields are included in the LLM API prompt and which are excluded.
- [ ] Document whether any sanitization is performed before API calls.

### K. Phase dependency ordering
The plan must:
- [ ] State explicitly whether Phase 1 is implementable before Phase 2 (recommended: yes — default success signal uses `finish_task` + `error_kind`).
- [ ] If Phase 1 depends on Phase 2, document the dependency and make the dependency graph visible in the implementation steps section.

---

## 2. Rubric Dimensions

These three dimensions are selected from the standard Plan rubric set. A score of **3/5 (basic pass)** means the plan minimally satisfies the dimension for implementation readiness.

### Correctness (3/5 = basic pass)

> Does the plan accurately reflect the project's existing architecture and constraints?

At 3/5, the plan:
- Accurately identifies that MEMORY.md uses numbered-list entries (not named lessons with `skill_name`).
- Does not propose changes to MCP server core logic.
- Does not propose changes to `safety.py` or input device code.
- References the correct paths and file names (`.agents/memory/MEMORY.md`, `scripts/curator.py`, `.converge/active/`).
- Accounts for the existing `finish_task` and `error_kind` signals in `trace.py`.

### Completeness (3/5 = basic pass)

> Are all necessary parts defined well enough for implementation?

At 3/5, the plan:
- Defines the curator input format (trace directory, trace files, MEMORY.md content).
- Defines the curator output JSON schema with MEMORY.md-compatible identifiers.
- Defines the LLM API (provider, model, auth, cost).
- Defines the trigger mechanism as a standalone CLI.
- Defines the converge integration path (which mode, who orchestrates, rubric).
- Resolves the SkillOS paper dependency.
- All acceptance criteria A–H pass at the contract level.

A 4/5 would additionally define error handling for LLM API failures and a fallback strategy for malformed curator output. A 5/5 would include test fixtures and verified examples.

### Feasibility (4th dimension, 3/5 = basic pass)

> Does the plan acknowledge and account for operational costs?

At 3/5, the plan:
- Acknowledges API cost per curator run (LLM API call + converge reviewer spawns).
- Defines a cost tracking mechanism or budget cap for curator runs.
- Estimates operator time per converge cycle (reading diff, approving/rejecting changes).
- Documents when the curator should NOT be triggered (low-value traces, non-actionable error patterns).

A 4/5 would additionally define a cost-per-run budget and auto-throttle mechanism. A 5/5 would include cost benchmarks from historical runs.

### Consistency (3/5 = basic pass)

> Are the plan's internal definitions and cross-references self-consistent?

At 3/5, the plan:
- Uses the same terminology for MEMORY.md entries across all sections (numbered lesson references, not `skill_name`).
- Has no contradictory statements about write targets (MEMORY.md only, not SKILL.md in Phase 1).
- Phase dependencies are explicit and acyclic.
- The output format shown in the architecture diagram matches the JSON schema.
- Converge rubric dimensions named in Phase 3 match those described in §4.

---

## 3. Out of Scope

This convergence will **not** address:

- **SKILL.md structural changes** — deferred entirely. SKILL.md is not a curator write target in this phase.
- **Model training / RL approaches** — the plan already excludes this; no re-evaluation needed.
- **MCP server core logic changes** — curator is an external script; no changes to `computer_use/core.py`, `safety.py`, or existing tool implementations.
- **Daemon / file-watcher architecture** — the trigger mechanism is explicitly standalone CLI only.
- **Production-grade LLM error recovery** — retry logic and API fallbacks are implementation details, not contract requirements.
- **CI/CD pipeline integration** — not required for Phase 1–3.
- **Multi-user / multi-project deployment** — single-user, single-project scope.
- **`review.py` structural refactoring** — the existing `improvement_suggestions_placeholder` at review.py:91 is out of scope for structural changes, but the plan must acknowledge how curator output relates to this placeholder to document the relationship for future phases.
- **Historical trace migration** — Phase 4 testing may use historical traces, but the plan is not required to define a migration strategy for production trace data.
- **User confirmation UX** — the plan may note that human approval gates exist (converge final approval), but a polished confirmation UI is not required.
