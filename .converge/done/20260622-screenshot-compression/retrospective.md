# Retrospective — 20260622-screenshot-compression

## Summary

3 轮评议收敛（R1: 4 blocking → R2: 2 blocking → R3: 0 blocking 可执行），总发现 6 个 blocking issues，均为 plan_defect。无升级完整收敛、无振荡、无 overturn。

## Round Summary

| Round | Verdict | Blocking | Conceptual | Structural |
|-------|---------|----------|------------|------------|
| R1 | 阻断需修复 | 4 | 2 (#1 config KeyError, #2 size gate) | 2 (#3 fake PNG, #4 await syntax) |
| R2 | 阻断需修复 | 2 | 0 | 2 (#1 RGBA crash, #2 solid-color test) |
| R3 | 可执行 | 0 | 0 | 0 |

## Key Fixes Applied

1. Config init: added `"image": dict(_DEFAULTS["image"])` to `_load_config()` initial construction
2. Size gate: removed pre-compression raw PNG check, added post-compression base64-size check
3. RGBA safety: `compress_for_inline()` now converts non-RGB/L modes to RGB before JPEG encode
4. Test robustness: all test images generated with real PIL, async tests use `asyncio.run()`
5. Oversized test: random noise image (numpy) defeats DCT compression
6. Memory guard: `_MAX_INLINE_FILE_SIZE = 50MB` prevents loading monster virtual-desktop captures
7. Test hygiene: `_minimal_config()` updated with `image` key, test names corrected

## Suggestion Triage

| Suggestion | Disposition |
|------------|------------|
| S1: numpy dep → `os.urandom()` | Accepted for execution |
| S2: Dead `_MAX_INLINE_IMAGE_RAW_BYTES` | Add documentary comment |
| S3: Redundant PIL import | Remove during execution |
| S4: mimeType assertion → exact match | Apply during execution |

## Lessons

- Config loading patterns are easy to miss when adding new top-level keys — the `safety`/`display` copy-then-overlay convention must be followed for every new section
- Size gates should check the output of the pipeline, not the input
- Solid-color images are pathologically compressible — test fixtures must use noise for compression threshold tests

## Blind Recheck

Skipped (评议模式，未达 ≥2 轮 outer loop 条件；3 轮均为评议级单轮审查，无盲审触发).
