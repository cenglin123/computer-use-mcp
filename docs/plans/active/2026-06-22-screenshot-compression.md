# Screenshot Compression for Context Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce screenshot payload size 10-50x (from ~2-5 MB PNG to ~80-200 KB JPEG) through lossy compression and dimension capping, dramatically lowering per-turn context bloat when inline images accumulate across many computer-use turns.

**Architecture:** Add an inline-image compression pipeline (`resize → JPEG encode`) that runs only when `include_image=true`, keeping the on-disk saved file as full-quality PNG for `click_on_screenshot` coordinate accuracy. Introduce user-configurable `image` section in `config.yaml` for max dimensions, JPEG quality, and format. All screen coordinate tools (`click_on_screenshot`, `crop_screenshot`, etc.) continue to operate on the full-resolution PNG on disk; the compressed variant is exclusively for inline transmission to the MCP client.

**Tech Stack:** Python 3.11+, Pillow (PIL), existing `core.py`/`mcp_server.py`, pytest.

---

## Problem Analysis

Per opencode investigation (`C:\Project\opencode`):

1. Every computer-use turn stores screenshot base64 in SQLite via `tools.ts:154-173` → `processor.ts:573-593` → `PartTable.data` (JSON column).
2. Every subsequent turn loads ALL historical parts via `message-v2.ts:hydrate()` — parsing hundreds of MB of base64-embedded JSON.
3. Compaction only strips images near the model's context limit; `preserveRecentBudget` keeps recent ~8000 token history intact, so recent screenshots are never pruned.
4. 50 turns × 3 screenshots × 2 MB base64 = ~300 MB of base64 in SQLite JSON → 5-7 minutes per turn.

**Why MCP-side compression helps:** Even though opencode's accumulation is the root cause, shrinking each inline image 10-50x reduces the SQLite payload from hundreds of MB to tens of MB, bringing per-turn latency from 5-7 minutes down to 30-90 seconds for typical sessions.

**What NOT to do:** Do NOT compress the on-disk saved PNG — `click_on_screenshot` and `crop_screenshot` depend on pixel-accurate coordinates between the saved file and screen space. The saved file remains full-resolution lossless PNG.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `computer_use/core.py` | Modify | Add `compress_for_inline()`: resize + JPEG encode to buffer |
| `computer_use/mcp_server.py` | Modify | Replace `_encode_png_base64()` with inline compression; update constants; wire config |
| `computer_use/config.py` | Modify | Add `image` config section with defaults |
| `config.example.yaml` | Modify | Document new `image` config options |
| `tests/test_core.py` | Modify | Unit tests for `compress_for_inline()` |
| `tests/test_mcp_server.py` | Modify | Integration tests for inline compression in screenshot flow |
| `docs/api.md` | Modify | Update "上下文保护原则" section with compression behavior |
| `CHANGELOG.md` | Add entry | Document the change |

---

### Task 1: Add `compress_for_inline()` to core.py

**Files:**
- Modify: `computer_use/core.py`

- [ ] **Step 1: Write the function**

Add after the existing `save_screenshot()` function (after line 322):

```python
def compress_for_inline(
    pil_img: Image.Image,
    *,
    max_width: int = 1600,
    jpeg_quality: int = 75,
) -> tuple[bytes, str]:
    """Compress a screenshot for inline transmission to the MCP client.

    Resizes proportionally if wider than *max_width*, then encodes as JPEG.
    Returns ``(raw_bytes, mime_type)``.  The caller is responsible for
    base64-encoding the returned bytes and wrapping them in an
    ``ImageContent`` block.

    The on-disk saved file is *never* compressed — this function is only for
    the inline variant that accompanies ``include_image=true``.
    """
    img = pil_img.copy()
    # JPEG encoder requires RGB; screenshots are typically RGB or RGBA
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max_width > 0 and img.width > max_width:
        ratio = max_width / img.width
        new_h = max(int(img.height * ratio), 1)
        img = img.resize((max_width, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue(), "image/jpeg"
```

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `pytest tests/test_core.py -v`
Expected: All existing tests PASS

---

### Task 2: Add `image` config section

**Files:**
- Modify: `computer_use/config.py`
- Modify: `config.example.yaml`

- [ ] **Step 1: Add defaults to config.py**

In `computer_use/config.py`, add to `_DEFAULTS` dict (after line 48, before the closing `}`):

```python
    "image": {
        "inline": {
            "max_width": 1600,
            "jpeg_quality": 75,
        },
    },
```

- [ ] **Step 2: Add config loading (two locations)**

**Location A** — In `_load_config()`, in the initial config construction block (lines 59-67), add the `image` key alongside `safety` and `display` so it always exists even when no config file is present:

```python
    config = {
        "log_dir": _expand_user(_DEFAULTS["log_dir"]),
        # ... existing keys ...,
        "safety": dict(_DEFAULTS["safety"]),
        "display": dict(_DEFAULTS["display"]),
        "image": dict(_DEFAULTS["image"]),          # ← ADD
    }
```

**Location B** — After the `display` section loading (after line 110), add the YAML-file overlay:

```python
    image = data.get("image", {})
    inline_cfg = image.get("inline", {})
    cfg_image = config["image"]
    cfg_image["inline"] = {
        "max_width": int(
            inline_cfg.get("max_width", _DEFAULTS["image"]["inline"]["max_width"])
        ),
        "jpeg_quality": int(
            inline_cfg.get("jpeg_quality", _DEFAULTS["image"]["inline"]["jpeg_quality"])
        ),
    }
```

- [ ] **Step 3: Update config.example.yaml**

After the `display:` section (after line 35), add:

```yaml
image:
  # Settings for inline images (returned when include_image=true).
  # The on-disk saved screenshot is always full-resolution PNG.
  inline:
    # Maximum width in pixels. Wider screenshots are proportionally
    # resized. Set to 0 to disable resizing (keep original dimensions).
    # Default: 1600
    max_width: 1600

    # JPEG quality for inline images (1-100). Higher = better quality + larger.
    # UI screenshots are perfectly readable at 70-85.
    # Default: 75
    jpeg_quality: 75
```

- [ ] **Step 4: Run config tests**

Run: `pytest tests/test_config.py -v`
Expected: All tests PASS

---

### Task 3: Wire inline compression into mcp_server.py

**Files:**
- Modify: `computer_use/mcp_server.py`

- [ ] **Step 1: Replace `_encode_png_base64` with `_encode_inline_image`**

Replace the existing `_encode_png_base64` function (line 1737-1738):

```python
def _encode_inline_image(path: Path, config: dict[str, Any]) -> tuple[str, str]:
    """Read saved screenshot, compress for inline, return (base64_str, mime_type).

    The on-disk file is never modified — compression happens in memory only.

    Raises ValueError if the file exceeds _MAX_INLINE_FILE_SIZE (defense against
    loading monster virtual-desktop captures into memory; caller degrades to
    path-only on any exception).
    """
    from PIL import Image as PILImage

    if path.stat().st_size > _MAX_INLINE_FILE_SIZE:
        raise ValueError(f"File too large for inline compression: {path.stat().st_size} bytes")

    img = PILImage.open(path)
    raw, mime = compress_for_inline(
        img,
        max_width=config["image"]["inline"]["max_width"],
        jpeg_quality=config["image"]["inline"]["jpeg_quality"],
    )
    return base64.b64encode(raw).decode("ascii"), mime


# Loose file-size guard: refuse to load >50MB PNG into memory for compression.
# Typical monitor=1 screenshot: 2-5 MB PNG. Virtual desktop (3×4K): ~75 MB.
_MAX_INLINE_FILE_SIZE = 50_000_000
```

- [ ] **Step 2: Update `_screenshot_result_content`**

In `_screenshot_result_content()` (line 1741), update:

**Change the encode block** (lines 1771-1782) from:

```python
    try:
        encoded = await asyncio.to_thread(_encode_png_base64, path)
    except Exception as exc:
        logging.warning("inline screenshot encode failed: %s", exc)
        data["inline_image"] = False
        return [TextContent(type="text", text=json.dumps(data))]

    data["inline_image"] = True
    return [
        TextContent(type="text", text=json.dumps(data)),
        ImageContent(type="image", data=encoded, mimeType="image/png"),
    ]
```

To:

```python
    try:
        cfg = load_config()
        encoded, mime_type = await asyncio.to_thread(_encode_inline_image, path, cfg)
    except Exception as exc:
        logging.warning("inline screenshot encode failed: %s", exc)
        data["inline_image"] = False
        return [TextContent(type="text", text=json.dumps(data))]

    data["inline_image"] = True
    data["inline_mime_type"] = mime_type
    return [
        TextContent(type="text", text=json.dumps(data)),
        ImageContent(type="image", data=encoded, mimeType=mime_type),
    ]
```

- [ ] **Step 3: Move size check to after compression**

The existing `_MAX_INLINE_IMAGE_RAW_BYTES` checks the **pre-compression** PNG file size (`path.stat().st_size`), but we want to check the **post-compression** result. Replace the raw-size check with a post-compression base64-size check inside `_screenshot_result_content()`.

**Keep** the existing constants unchanged (line 1732-1734):

```python
MAX_INLINE_IMAGE_BASE64_BYTES = 3_000_000
_MAX_INLINE_IMAGE_RAW_BYTES = MAX_INLINE_IMAGE_BASE64_BYTES * 3 // 4
```

**Remove** the raw-size gate from `_screenshot_result_content()` (lines 1767-1769) and **add** a post-compression base64-size gate after the encode step. The updated block becomes:

```python
    try:
        cfg = load_config()
        encoded, mime_type = await asyncio.to_thread(_encode_inline_image, path, cfg)
    except Exception as exc:
        logging.warning("inline screenshot encode failed: %s", exc)
        data["inline_image"] = False
        return [TextContent(type="text", text=json.dumps(data))]

    if len(encoded) > MAX_INLINE_IMAGE_BASE64_BYTES:
        data["inline_image_skipped"] = "payload_too_large"
        return [TextContent(type="text", text=json.dumps(data))]

    data["inline_image"] = True
    data["inline_mime_type"] = mime_type
    return [
        TextContent(type="text", text=json.dumps(data)),
        ImageContent(type="image", data=encoded, mimeType=mime_type),
    ]
```

The pre-existing raw-size guard (`raw_size > _MAX_INLINE_IMAGE_RAW_BYTES` at line ~1767) is **removed** — it was designed for full-resolution PNGs and would silently reject most screenshots before they reach the compression pipeline.

- [ ] **Step 4: Add `from computer_use.core import compress_for_inline` import**

At the top of `mcp_server.py`, add `compress_for_inline` to the existing import from `computer_use.core` (line ~40-50). Check the existing import block and add:

```python
from computer_use.core import (
    # ... existing imports ...,
    compress_for_inline,
)
```

- [ ] **Step 5: Confirm `from computer_use.config import load_config` already exists**

`mcp_server.py` line ~51 already imports `load_config` from `computer_use.config`. No new import needed — verify it exists and skip adding a duplicate.

- [ ] **Step 6: Run existing mcp_server tests**

Run: `pytest tests/test_mcp_server.py -v`
Expected: Tests that reference `_MAX_INLINE_IMAGE_RAW_BYTES` may need updating; the inline screenshot tests should still pass

---

### Task 4: Write tests for inline compression

**Files:**
- Modify: `tests/test_core.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Test `compress_for_inline` sizing**

Add to `tests/test_core.py`:

```python
from computer_use.core import compress_for_inline

def test_compress_for_inline_resizes_wide_image():
    """Image wider than max_width is proportionally resized."""
    from PIL import Image

    img = Image.new("RGB", (2560, 1440), color=(100, 150, 200))
    raw, mime = compress_for_inline(img, max_width=1280, jpeg_quality=75)

    assert mime == "image/jpeg"
    # Verify resized: decompress and check dimensions
    result = Image.open(io.BytesIO(raw))
    assert result.width == 1280
    assert result.height == 720  # 1440 * (1280/2560)


def test_compress_for_inline_keeps_narrow_image():
    """Image narrower than max_width is NOT resized."""
    from PIL import Image

    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    raw, mime = compress_for_inline(img, max_width=1600, jpeg_quality=75)

    result = Image.open(io.BytesIO(raw))
    assert result.width == 800
    assert result.height == 600


def test_compress_for_inline_max_width_zero_disables_resize():
    """max_width=0 keeps original dimensions."""
    from PIL import Image

    img = Image.new("RGB", (2560, 1440), color=(100, 150, 200))
    raw, mime = compress_for_inline(img, max_width=0, jpeg_quality=75)

    result = Image.open(io.BytesIO(raw))
    assert result.width == 2560
    assert result.height == 1440


def test_compress_for_inline_jpeg_smaller_than_raw():
    """JPEG output is smaller than raw RGB pixel buffer."""
    from PIL import Image

    img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    raw, mime = compress_for_inline(img, max_width=1600, jpeg_quality=75)

    # Resized to 1600x900, JPEG should be well under 500KB for solid color
    assert len(raw) < 500_000
    assert mime == "image/jpeg"


def test_compress_for_inline_rgba_to_rgb():
    """RGBA images are converted to RGB for JPEG encoding (JPEG has no alpha)."""
    from PIL import Image

    img = Image.new("RGBA", (800, 600), color=(100, 150, 200, 255))
    raw, mime = compress_for_inline(img, max_width=1600, jpeg_quality=75)

    result = Image.open(io.BytesIO(raw))
    assert result.mode == "RGB"
    assert result.width == 800


def test_compress_for_inline_exact_width_boundary():
    """Image width equal to max_width is NOT resized."""
    from PIL import Image

    img = Image.new("RGB", (1600, 900), color=(100, 150, 200))
    raw, mime = compress_for_inline(img, max_width=1600, jpeg_quality=75)

    result = Image.open(io.BytesIO(raw))
    assert result.width == 1600
    assert result.height == 900


def test_compress_for_inline_tiny_image():
    """1x1 image passes through without error."""
    from PIL import Image

    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    raw, mime = compress_for_inline(img, max_width=1600, jpeg_quality=75)

    assert mime == "image/jpeg"
    assert len(raw) > 0
```

- [ ] **Step 2: Test inline compression integration**

Add to `tests/test_mcp_server.py`:

```python
def test_screenshot_inline_uses_jpeg_compression(tmp_path, monkeypatch):
    """When include_image=true, the inline image is JPEG (not PNG)."""
    import asyncio
    from computer_use import mcp_server
    from PIL import Image

    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    monkeypatch.setattr(
        mcp_server, "load_config",
        lambda: {
            "screenshot_dir": str(screenshot_dir),
            "image": {"inline": {"max_width": 800, "jpeg_quality": 60}},
        },
    )

    # Generate a real PNG with PIL (not fake bytes — _encode_inline_image
    # calls PILImage.open which requires valid image data)
    png_path = screenshot_dir / "test.png"
    img = Image.new("RGB", (1920, 1080), color=(200, 100, 50))
    img.save(png_path, format="PNG")

    result = {
        "screenshot_taken": True,
        "saved_path": str(png_path),
        "width": 1920,
        "height": 1080,
    }
    content = asyncio.run(mcp_server._screenshot_result_content(json.dumps(result)))

    # Should have 2 content blocks: text + image
    assert len(content) == 2
    text_data = json.loads(content[0].text)
    assert text_data["inline_image"] is True
    assert text_data["inline_mime_type"] == "image/jpeg"
    assert content[1].mimeType == "image/jpeg"
    # Verify the image data is valid base64 that decodes to a JPEG
    raw = base64.b64decode(content[1].data)
    decoded = Image.open(io.BytesIO(raw))
    assert decoded.width == 800   # resized from 1920 (800 / 1920 * 1080 = 450)
    assert decoded.height == 450
```

- [ ] **Step 3: Update existing inline screenshot tests**

In `tests/test_mcp_server.py`, the existing test `test_screenshot_inline_appends_full_image` (near line ~157) writes fake PNG bytes (`b"\x89PNG\r\n\x1a\n fake png bytes"`) which will fail with `PILImage.open()`. Rewrite it to generate a real PIL PNG:

```python
def test_screenshot_inline_with_include_image(tmp_path, monkeypatch):
    """include_image=true returns an ImageContent block."""
    import asyncio
    from PIL import Image

    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    monkeypatch.setattr(server, "load_config",
        lambda: {
            "screenshot_dir": str(screenshot_dir),
            "image": {"inline": {"max_width": 0, "jpeg_quality": 75}},
        },
    )

    png = screenshot_dir / "shot.png"
    Image.new("RGB", (400, 300), color=(100, 200, 50)).save(png, format="PNG")

    result = json.dumps({
        "screenshot_taken": True,
        "saved_path": str(png),
    })
    content = asyncio.run(server._screenshot_result_content(result))

    assert len(content) == 2
    assert isinstance(content[1], ImageContent)
    assert content[1].mimeType in ("image/png", "image/jpeg")
    assert json.loads(content[0].text)["inline_image"] is True
```

Also update the oversized image test `test_screenshot_inline_skips_oversized` — it previously relied on `_MAX_INLINE_IMAGE_RAW_BYTES`. Since the raw-size gate is removed, rewrite it to test the post-compression base64-size gate by generating a very large image:

```python
def test_screenshot_inline_skips_oversized(tmp_path, monkeypatch):
    """Base64-encoded inline image exceeding MAX_INLINE_IMAGE_BASE64_BYTES is skipped."""
    import asyncio
    import numpy as np
    from PIL import Image

    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    monkeypatch.setattr(server, "load_config",
        lambda: {
            "screenshot_dir": str(screenshot_dir),
            "image": {"inline": {"max_width": 0, "jpeg_quality": 100}},
        },
    )

    # Generate a random-noise image whose JPEG at Q100+no-resize will exceed
    # the 3MB base64 budget. Solid-color images compress too well to test
    # the oversized path — noise defeats DCT compression.
    rng = np.random.default_rng(42)
    pixels = rng.integers(0, 256, (2400, 1800, 3), dtype=np.uint8)

    png = screenshot_dir / "big.png"
    Image.fromarray(pixels, "RGB").save(png, format="PNG")

    result = json.dumps({
        "screenshot_taken": True,
        "saved_path": str(png),
    })
    content = asyncio.run(server._screenshot_result_content(result))

    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    data = json.loads(content[0].text)
    assert data["inline_image_skipped"] == "payload_too_large"
```

- [ ] **Step 4: Update `_minimal_config()` helper**

In `tests/test_mcp_server.py`, the `_minimal_config()` helper (near line ~660) is used by many tests as a baseline config dict. Add the `image` key so future maintainers don't hit KeyError when tests exercise inline image paths:

```python
def _minimal_config():
    return {
        "screenshot_dir": ...,
        # ... existing keys ...,
        "image": {"inline": {"max_width": 1600, "jpeg_quality": 75}},
    }
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/test_core.py tests/test_config.py tests/test_mcp_server.py -v`
Expected: All tests PASS

---

### Task 5: Update documentation

**Files:**
- Modify: `docs/api.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update api.md context protection section**

In `docs/api.md`, after line 33 (the "上下文保护原则" paragraph), add:

```markdown
**内联图像压缩**：当 `include_image=true` 时，内联图像会经过以下处理：
- 若宽度超过 `image.inline.max_width`（默认 1600px），按比例缩小
- 以 JPEG 格式编码（质量由 `image.inline.jpeg_quality` 控制，默认 75）
- 落盘 PNG 文件保持原始分辨率，不受影响
- 该行为仅影响 `ImageContent` 块，不影响 `TextContent` 中的 `saved_path` 引用
```

- [ ] **Step 2: Update CHANGELOG**

Use the project's changelog script. Check the actual CLI interface first — the AGENTS.md convention uses `###` headers under date sections. Run:

```bash
python scripts/changelog.py add --title "screenshot: inline JPEG compression for context budget" --body "screenshot 的 include_image=true 路径现在将内联图像压缩为 JPEG（默认最大宽度 1600px，质量 75），显著减少上下文中的图像体积。落盘文件保持全分辨率 PNG 不变。新增 image.inline.max_width / image.inline.jpeg_quality 配置项。"
```

If the script uses a different interface, adapt accordingly — the key content is the title and body above.

---

### Task 6: Final verification

- [ ] **Step 1: Full test suite**

Run: `pytest tests/ -v --ignore=tests/manual`
Expected: All automated tests PASS

- [ ] **Step 2: Manual smoke test**

Run: `python -m computer_use screenshot --monitor 1 --include-image`
Expected: Returns JPEG inline image; saved file remains PNG at full resolution

- [ ] **Step 3: Verify saved file untouched**

After the smoke test, check `~/.computer-use/screenshots/` — the saved PNG should be the original full resolution, not the compressed JPEG.

---

## Design Decisions

1. **Why JPEG not WebP?** — Pillow's JPEG encoder is universally available without extra dependencies; WebP requires `pip install webp` on some platforms. JPEG at quality 75 is visually indistinguishable from PNG for UI screenshots.

2. **Why 1600px default max_width?** — Most LLM vision models downsample images internally to well under 2000px. A 1600px-wide image preserves all detail the model can use while being ~3x smaller than a 2560px or 4K source.

3. **Why compress only inline, not the saved file?** — `click_on_screenshot` and `crop_screenshot` map image pixel coordinates to screen coordinates. If the saved file were resized or lossy-compressed, coordinate mapping would break. The saved file is the ground-truth reference.

4. **Why configurable not hard-coded?** — Different use cases have different quality/size tradeoffs. A user inspecting fine text in a screenshot may want quality 90; a fast automation loop may prefer quality 50 at 1024px.
