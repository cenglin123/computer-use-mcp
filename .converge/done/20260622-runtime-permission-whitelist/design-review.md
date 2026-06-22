---
type: design-review
object_slug: 20260622-runtime-permission-whitelist
generated_at: "2026-06-22T01:55:00Z"
---

# Design Review · 20260622-runtime-permission-whitelist

## 7 Dimensions

### DR1: Consistency
**Status: concerns_found** → **FIXED**
- `_extract_*` undefined functions → replaced with structured SafetyError subclass attributes
- `key_sequence` → `key_combo` in frozenset
- `_allowed_commands()` dual definition → Task 2 marked as stub, Task 5 as definitive

### DR2: Completeness
**Status: concerns_found** → **ACKNOWLEDGED**
- Thread safety: noted as deferred (stdio transport processes sequentially)
- Consume scoping: documented trade-off, `level="session"` for multi-window workaround
- Config write failure: silent-except documented, acceptable for MVP

### DR3: Maintainability
**Status: concerns_found** → **ACKNOWLEDGED**
- `_allowed_commands()` dual definition → cross-referenced with "implementers must apply Task 5's version"
- `_window_tools` frozenset → documented as known maintenance point

### DR4: Boundary Clarity
**Status: concerns_found** → **ACKNOWLEDGED**
- `_append_to_config` in runtime_permissions.py → acceptable for MVP; config.py owns defaults, runtime_permissions.py owns writes

### DR5: Residue & Redundancy
**Status: concerns_found** → **ACKNOWLEDGED**
- Duplicate matching algorithm → documented as "Known Limitation" with future refactoring path

### DR6: Portability
**Status: clean**

### DR7: Scalability
**Status: concerns_found** → **ACKNOWLEDGED**
- `consume_window_exception(None,None)` → documented trade-off with session-level workaround
- `_window_tools` enumeration → deferred to tool-level attribute

## Highlights (post-fix status)

1. **SafetyError subclasses now carry structured data** ✅ — `SensitiveProcessError(process_name=)` / `SensitiveWindowError(class_name=)` → no undefined extract functions
2. **Consume scoping documented** ✅ — `None,None` broad consumption is intentional; multi-window users use `session` level
3. **yaml.safe_dump comment loss** ✅ — documented as acceptable-for-MVP with ruamel.yaml migration path

## User Decision
All 6 DR findings addressed: 3 code-level fixes applied to plan, 3 acknowledged as known limitations with deferred work items.
