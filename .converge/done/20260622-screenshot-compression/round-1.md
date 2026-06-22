# Round 1 · 20260622-screenshot-compression

## 评议 Verdict: 阻断需修复

### Blocking Issues (4)

| ID | Severity | 问题 | 位置 |
|----|----------|------|------|
| 1 | conceptual | `_load_config()` 无配置时返回的 dict 不含 `image` 键，下游 `_encode_inline_image` 会 KeyError | Task 2 Step 2 |
| 2 | conceptual | `_MAX_INLINE_IMAGE_RAW_BYTES` 检查的是压缩**前**的 PNG 大小，降到 1.125MB 会导致大部分截图在压缩前被 `payload_too_large` 拒绝 | Task 3 Step 3 |
| 3 | structural | 现有测试用假的 PNG bytes，新 `PILImage.open()` 会报错 | Task 4 Step 3 |
| 4 | structural | 集成测试中 `await` 在非 async 函数内是语法错误，项目用 `asyncio.run()` | Task 4 Step 2 |

### Suggestions (5)

- `from computer_use.config import load_config` 已存在，Step 5 是 no-op
- image config overlay 应遵循 `safety`/`display` 的 copy-then-overlay 模式
- 测试缺少 RGBA→RGB 转换、边界条件（1×1、max_width 等于图像宽）
- `MAX_INLINE_IMAGE_BASE64_BYTES` 注释缺量化估算
- `scripts/changelog.py` CLI 接口需确认

### 前置自检：通过（无 conceptual 层设计问题）

---

## 处理

4 个阻断均为 `plan_defect`，修复方向明确且机械。不升级完整收敛，直接在评议模式内修复 plan 后重审。

