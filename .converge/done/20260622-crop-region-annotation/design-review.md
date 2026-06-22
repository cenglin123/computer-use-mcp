---
type: design-review
object_slug: 20260622-crop-region-annotation
generated_at: "2026-06-22T10:05:00Z"
---

# Design Review · 20260622-crop-region-annotation

## 7 Dimensions Summary

| Dimension | Status | Key Finding |
|-----------|--------|------------|
| DR1 Consistency | concerns | `DEFAULT_CROP_STYLE` in table vs actual constants mismatch; `annotate_region` mislabeled as "pure function" |
| DR2 Completeness | concerns | No annotation-failure test; `annotate_style` forwarding untested; 4 open questions unresolved; manual_test_checklist.md doesn't exist |
| DR3 Maintainability | concerns | Dual default for `annotate` (schema + handler); single-value `annotate_style` enum |
| DR4 Boundary Clarity | clean | — |
| DR5 Residue | concerns | `DEFAULT_CROP_STYLE` ghost constant in file structure table |
| DR6 Portability | clean | — |
| DR7 Scalability | concerns | Small-crop bracket overshoot unaddressed (arms extend beyond crop when < 24px) |

## Highlights

1. **`DEFAULT_CROP_STYLE` ghost** — file structure table lists it but no code defines it. Replace with actual constants.
2. **Small-crop bracket overshoot** — when width/height < 24px, bracket arms extend outside the crop region, visually misleading. Clamp or document minimum.
3. **4 open questions unresolved** — style choice, label content, file location, `click_on_screenshot` annotation. Settle in plan or mark as explicitly deferred.

## User Decision
Plan is executable as-is (3/3 ultraverge reviewers agree). The 3 highlights above are advisory — fix before execution or accept as-is.
