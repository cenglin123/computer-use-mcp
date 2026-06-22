# Unified Visual Annotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every crop verification image can show both the cursor red crosshair and the crop-region red marker in one image, with explicit metadata describing both layers.

**Architecture:** The current implementation already mostly achieves this because screenshot PNGs are saved with the cursor red crosshair baked in, and `crop_screenshot` creates `<source>_annotated.png` by copying that source image and drawing crop-region L-brackets. This plan formalizes that behavior as a first-class contract, adds metadata for cursor/region layers, avoids duplicate marker drawing, and updates docs/tests so agents know to read one `annotated_source_path` for both cursor and crop verification.

**Tech Stack:** Python 3.11+, Pillow, existing `screenshot`, `crop_screenshot`, `snapshot.annotate_region`, pytest.

---

## Current State

Current code path:

1. `computer_use.core.save_screenshot()` captures the screen and draws the red cursor crosshair directly into the saved PNG.
2. `computer_use.snapshot.annotate_region()` opens that saved PNG, copies it, draws crop-region corner brackets, and writes `<source>_annotated.png`.
3. Therefore, if the source image is a screenshot captured by MCP, `annotated_source_path` already contains both:
   - cursor red crosshair
   - crop-region red L-brackets

Gap:

- This is an accidental emergent behavior, not a documented contract.
- The response JSON does not say whether cursor and crop annotations are both present.
- The screenshot sidecar does not consistently expose cursor image coordinates as structured metadata for later validation.
- If future refactoring stops baking cursor markers into screenshots, crop annotation would silently lose the cursor layer.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `computer_use/snapshot.py` | Modify | No changes needed — annotation layers assembled inline in mcp_server.py |
| `computer_use/mcp_server.py` | Modify | Include cursor metadata in screenshot sidecar/response; include annotation layer metadata in crop response |
| `computer_use/tools/schemas.py` | Modify | Clarify that `annotated_source_path` contains cursor + crop layers when source screenshot has cursor marker |
| `skills/computer-use/SKILL.md` | Modify | Document the one-image verification workflow |
| `tests/test_mcp_server.py` | Modify | Verify crop annotated source includes region marker and layer metadata |
| `tests/test_snapshot.py` | Modify | Verify annotation helpers do not remove existing cursor marker pixels |

---

## Annotation Contract

For a crop created from an MCP screenshot, `crop_screenshot` should return:

```json
{
  "cropped": true,
  "saved_path": ".../crop_....png",
  "annotated_source_path": ".../screenshot_..._annotated.png",
  "annotation_layers": {
    "cursor": {
      "present": true,
      "image_x": 500,
      "image_y": 300,
      "style": "red_crosshair"
    },
    "crop_region": {
      "present": true,
      "x": 400,
      "y": 250,
      "width": 160,
      "height": 90,
      "style": "corner_brackets"
    }
  }
}
```

The source PNG must not be overwritten. The annotated PNG may overwrite a previous `<source>_annotated.png` for the same source, matching current behavior.

---

### Task 1: Add cursor metadata to screenshot sidecar

**Files:**
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_server.py`

> **Helper dependency:** Tests below depend on helper functions `_create_real_png`, `_write_screenshot_sidecar`, `_minimal_config`, and `_call_tool` already defined in `tests/test_mcp_server.py`. If not present, implementers must add them (see existing crop-screenshot tests for patterns).

- [ ] **Step 1: Write failing test for cursor metadata**

Add a test near existing screenshot metadata tests in `tests/test_mcp_server.py`:

```python
def test_screenshot_sidecar_records_cursor_image_position(monkeypatch, tmp_path):
    import json
    import computer_use.mcp_server as server

    config = _minimal_config(str(tmp_path))
    monkeypatch.setattr(server, "load_config", lambda: config)
    monkeypatch.setattr(server.pyautogui, "position", lambda: (25, 35))

    data = json.loads(_call_tool("screenshot", {"monitor": 1}))
    meta = json.loads(Path(data["metadata_path"]).read_text(encoding="utf-8"))

    assert meta["cursor"]["screen_x"] == 25
    assert meta["cursor"]["screen_y"] == 35
    assert meta["cursor"]["image_x"] == 25
    assert meta["cursor"]["image_y"] == 35
    assert meta["cursor"]["style"] == "red_crosshair"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
pytest tests/test_mcp_server.py::test_screenshot_sidecar_records_cursor_image_position -v
```

Expected: FAIL because `cursor` metadata is missing.

- [ ] **Step 3: Add cursor metadata when saving screenshots**

In the screenshot handler in `computer_use/mcp_server.py`, add this metadata block **before** the `save_screenshot()` call:

```python
# Record cursor position before screenshot save — matches what
# save_screenshot() will draw. Capturing after save_screenshot()
# could give a different position if the user moves the mouse.
cursor_screen_x, cursor_screen_y = pyautogui.position()
cursor_image_x = cursor_screen_x - capture_left
cursor_image_y = cursor_screen_y - capture_top
metadata["cursor"] = {
    "screen_x": int(cursor_screen_x),
    "screen_y": int(cursor_screen_y),
    "image_x": int(cursor_image_x),
    "image_y": int(cursor_image_y),
    "present": 0 <= cursor_image_x < width and 0 <= cursor_image_y < height,
    "style": "red_crosshair",
}
```

Use the same capture origin fields already written to sidecar (`capture_left`, `capture_top`).

- [ ] **Step 4: Verify test passes**

Run:

```powershell
pytest tests/test_mcp_server.py::test_screenshot_sidecar_records_cursor_image_position -v
```

Expected: PASS.

---

### Task 2: Return unified annotation layer metadata from crop_screenshot

**Files:**
- Modify: `computer_use/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing test for combined annotation layers**

Add near crop tests:

```python
def test_crop_screenshot_returns_unified_annotation_layers(monkeypatch, tmp_path):
    import json
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(
        shot_path,
        capture_left=0,
        capture_top=0,
        width=1920,
        height=1080,
        cursor={
            "screen_x": 500,
            "screen_y": 300,
            "image_x": 500,
            "image_y": 300,
            "present": True,
            "style": "red_crosshair",
        },
    )
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 400,
                "y": 250,
                "width": 160,
                "height": 90,
            },
        )
    )

    layers = data["annotation_layers"]
    assert layers["cursor"]["present"] is True
    assert layers["cursor"]["image_x"] == 500
    assert layers["cursor"]["image_y"] == 300
    assert layers["cursor"]["style"] == "red_crosshair"
    assert layers["crop_region"] == {
        "present": True,
        "x": 400,
        "y": 250,
        "width": 160,
        "height": 90,
        "style": "corner_brackets",
    }
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
pytest tests/test_mcp_server.py::test_crop_screenshot_returns_unified_annotation_layers -v
```

Expected: FAIL because `annotation_layers` is missing.

- [ ] **Step 3: Add metadata construction in `_handle_crop_screenshot`**

After `annotated_path` is computed, add:

```python
source_cursor = meta.get("cursor", {})
annotation_layers = {
    "cursor": {
        "present": bool(source_cursor.get("present", False)),
        "image_x": source_cursor.get("image_x"),
        "image_y": source_cursor.get("image_y"),
        "screen_x": source_cursor.get("screen_x"),
        "screen_y": source_cursor.get("screen_y"),
        "style": source_cursor.get("style", "red_crosshair"),
    },
    "crop_region": {
        "present": annotated_path is not None,
        "x": x,
        "y": y,
        "width": crop_width,
        "height": crop_height,
        "style": annotate_style,
    },
}
crop_meta["annotation_layers"] = annotation_layers
response["annotation_layers"] = annotation_layers
```

Do not redraw cursor in this task. The cursor marker is already baked into the source screenshot.

- [ ] **Step 4: Verify test passes**

Run:

```powershell
pytest tests/test_mcp_server.py::test_crop_screenshot_returns_unified_annotation_layers -v
```

Expected: PASS.

---

### Task 3: Protect existing cursor marker when annotating source

**Files:**
- Modify: `tests/test_snapshot.py`
- Modify: `computer_use/snapshot.py` only if needed

- [ ] **Step 1: Write regression test**

Add to `tests/test_snapshot.py`:

```python
def test_annotate_region_preserves_existing_cursor_crosshair(tmp_path):
    from PIL import Image, ImageDraw
    from computer_use.snapshot import annotate_region

    src = tmp_path / "source.png"
    img = Image.new("RGB", (300, 200), color=(50, 80, 110))
    draw = ImageDraw.Draw(img)
    draw.line([(130, 100), (170, 100)], fill=(255, 0, 0), width=2)
    draw.line([(150, 80), (150, 120)], fill=(255, 0, 0), width=2)
    draw.ellipse([(147, 97), (153, 103)], fill=(255, 0, 0))
    img.save(src)

    annotated_path = annotate_region(str(src), 20, 20, 80, 60)
    annotated = Image.open(annotated_path)

    assert annotated.getpixel((150, 100))[0] > 200
    assert annotated.getpixel((150, 100))[1] < 50
```

- [ ] **Step 2: Run regression test**

Run:

```powershell
pytest tests/test_snapshot.py::test_annotate_region_preserves_existing_cursor_crosshair -v
```

Expected: PASS with current implementation because it copies source pixels before drawing crop brackets.

- [ ] **Step 3: If it fails, fix by preserving source copy semantics**

Ensure `annotate_region()` keeps this behavior:

```python
annotated = src.copy()
draw = ImageDraw.Draw(annotated)
```

Do not create a blank canvas.

---

### Task 4: Update tool schema and skill guidance

**Files:**
- Modify: `computer_use/tools/schemas.py`
- Modify: `skills/computer-use/SKILL.md`

- [ ] **Step 1: Update schema description**

In `crop_screenshot` description, replace the annotation sentence with:

```text
By default also writes a non-destructive annotated copy of the source. For MCP screenshots this annotated image contains both the source screenshot's red cursor crosshair and the crop region's red L-bracket marker, returned as `annotated_source_path`.
```

- [ ] **Step 2: Update skill guidance**

Add a paragraph under crop verification guidance:

```markdown
`annotated_source_path` is the canonical one-image verification artifact. When the source is an MCP screenshot, it contains both visual layers: the red cursor crosshair from the screenshot and the red crop-region marker from `crop_screenshot`. Use it to answer both questions at once: "where was the mouse?" and "what region did I crop?"
```

- [ ] **Step 3: Verify docs contain merged annotation language**

Run:

```powershell
rg "one-image|annotation_layers|red cursor" computer_use skills tests
```

Expected: matches in schema, skill, and tests.

---

## Acceptance Criteria

- `crop_screenshot` returns `annotated_source_path` and `annotation_layers`.
- The annotated image contains both visual layers when the source is an MCP screenshot.
- Source PNG is never overwritten.
- Existing crop metadata (`capture_left`, `capture_top`, `width`, `height`) remains unchanged.
- Existing crop/click tests pass.

Run:

```powershell
pytest tests/test_mcp_server.py -k "screenshot or crop" -v
pytest tests/test_snapshot.py -v
```

Expected: all PASS.

---

## Open Questions for Review

1. Should cursor and crop marker remain both red, or should cursor stay red while crop uses orange/yellow to reduce ambiguity?
2. Should `annotation_layers.cursor.present=false` be returned when the source is not an MCP screenshot, or should the field be omitted entirely? **Decision: Always return `annotation_layers.cursor` with `present: true/false`. Unconditional presence is easier for clients to parse.**
3. Should multiple crop calls on the same source overwrite one `_annotated.png` or generate numbered files such as `_annotated_001.png`?
