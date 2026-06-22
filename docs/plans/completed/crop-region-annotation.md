# Crop Region Annotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Augment `crop_screenshot` to automatically produce a non-destructive annotated copy of the source screenshot with the crop region outlined, so models can visually verify "this is the region I cropped" before relying on the cropped image content. Backwards-compatible: existing callers get the same fields plus one optional `annotated_source_path`.

**Architecture:** Add a new non-destructive function `annotate_region(image, x, y, w, h, *, style)` in `computer_use/snapshot.py` that uses Pillow to draw L-shaped corner brackets (with optional coordinate label) on a copy of the source image. Call it from `_handle_crop_screenshot` after the crop is saved, write the annotated image next to the source as `<source>_annotated.png` (sidecar naming convention already used), and extend the returned JSON with `annotated_source_path`. Annotation is **non-destructive** — source PNG is never overwritten. New tool parameter `annotate: bool = True` lets callers opt out.

**Tech Stack:** Python 3.11+, Pillow 12.2.0 (already in `.venv`), no new dependencies.

**Known Limitations (deferred to future work):**
- **No animation / re-annotation on subsequent crops of the same source.** If the agent crops the same source 3 times, three separate `_annotated.png` files accumulate. Future work could deduplicate or stack rectangles.
- **Annotation only on `crop_screenshot`.** Other tools that read screenshots (e.g. `click_on_screenshot`) do not annotate their target on the source. Could be added later if useful for debugging.
- **No DPI / multi-monitor handling for the annotation.** The rectangle is drawn in image pixels matching the source PNG resolution. This is correct by construction (same coordinate space as the source), so it works on DPI-scaled screenshots — but the L-bracket pixel length is fixed (24px), which may look small on very high-DPI captures. Acceptable for MVP.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `computer_use/snapshot.py` | **Modify** | Add `annotate_region()` pure function; export `DEFAULT_BRACKET_ARM_PX`, `DEFAULT_BRACKET_WIDTH_PX`, `ANNOTATION_COLOR` constants |
| `computer_use/mcp_server.py` | **Modify** | `_handle_crop_screenshot`: invoke `annotate_region`, write `<source>_annotated.png`, extend JSON response |
| `computer_use/tools/schemas.py` | **Modify** | `crop_screenshot` schema: add optional `annotate` (bool, default `true`) and `annotate_style` (enum, default `"corner_brackets"`) parameters |
| `skills/computer-use/SKILL.md` | **Modify** | Document the new annotated_source_path field; update tool reference table; explain verification flow |
| `tests/test_snapshot.py` | **Modify** | Tests for `annotate_region()`: no mutation of source, correct pixel changes, corner-bracket geometry, label rendering |
| `tests/test_mcp_server.py` | **Modify** | Tests for `_handle_crop_screenshot`: annotated file is created, sidecar JSON updated, opt-out flag works, out-of-bounds path unchanged |

---

## Annotation Style

A single style ships in MVP: **corner brackets with label**. Layout:

```
┌─(x,y,w,h)
│           │
│           │
│           │
└─          ┘
```

- 4 L-shaped marks at the corners, 24px arm length, 3px line width, color `(255, 0, 0)` pure red.
- Coordinate label `"(x,y,w,h)"` rendered in red, top-left inside the crop, 12px font, 1px white shadow for legibility on dark backgrounds.
- Implementation uses Pillow `ImageDraw.line()` for arms and `ImageDraw.text()` for label. Font uses PIL's default bitmap font (`ImageFont.load_default()`) — no TTF dependency.

A `corner_brackets` style enum value is defined for forward compatibility (future styles: `full_rect`, `crosshair`, `none`).

---

## Task 1: Add `annotate_region()` to `snapshot.py`

**Files:**
- Modify: `computer_use/snapshot.py`
- Modify: `tests/test_snapshot.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_snapshot.py`:

```python
class TestAnnotateRegion:
    def test_annotate_region_does_not_mutate_source(self, tmp_path):
        from PIL import Image
        from computer_use.snapshot import annotate_region

        src = tmp_path / "src.png"
        Image.new("RGB", (400, 300), color=(50, 80, 110)).save(src)
        original_bytes = src.read_bytes()

        annotate_region(str(src), x=50, y=40, width=120, height=80)

        assert src.read_bytes() == original_bytes, "source PNG must not be modified"

    def test_annotate_region_returns_new_path(self, tmp_path):
        from PIL import Image
        from computer_use.snapshot import annotate_region

        src = tmp_path / "src.png"
        Image.new("RGB", (400, 300), color=(50, 80, 110)).save(src)

        out_path = annotate_region(str(src), x=50, y=40, width=120, height=80)

        assert out_path != str(src)
        assert out_path.endswith("_annotated.png")
        assert Path(out_path).exists()

    def test_annotate_region_changes_pixels_inside_crop(self, tmp_path):
        from PIL import Image
        from computer_use.snapshot import annotate_region

        src = tmp_path / "src.png"
        # Pure solid color so we can detect any red pixel
        Image.new("RGB", (400, 300), color=(50, 80, 110)).save(src)

        out_path = annotate_region(str(src), x=50, y=40, width=120, height=80)
        img = Image.open(out_path)
        # Sample a pixel inside the top-left corner bracket arm
        # Top-left corner at (50, 40); horizontal arm extends to (50+24, 40)
        # Sample at (60, 41) should be red after drawing
        px = img.getpixel((60, 41))
        assert px[0] > 200 and px[1] < 50 and px[2] < 50, f"expected red, got {px}"

    def test_annotate_region_leaves_outside_crop_untouched(self, tmp_path):
        from PIL import Image
        from computer_use.snapshot import annotate_region

        src = tmp_path / "src.png"
        Image.new("RGB", (400, 300), color=(50, 80, 110)).save(src)

        out_path = annotate_region(str(src), x=100, y=100, width=50, height=50)
        img = Image.open(out_path)
        # Sample well outside the crop
        px = img.getpixel((10, 10))
        assert px == (50, 80, 110), f"outside crop should be unchanged, got {px}"

    def test_annotate_region_handles_bracket_arm_pixel(self, tmp_path):
        from PIL import Image
        from computer_use.snapshot import annotate_region

        src = tmp_path / "src.png"
        Image.new("RGB", (400, 300), color=(255, 255, 255)).save(src)

        out_path = annotate_region(str(src), x=100, y=100, width=80, height=60)
        img = Image.open(out_path)
        # Bottom-right corner at (100+80, 100+60) = (180, 160)
        # Vertical arm goes from (180, 160) up to (180, 160-24=136)
        # Sample at (180, 155) - inside the vertical arm
        px = img.getpixel((180, 155))
        assert px[0] > 200, f"expected red vertical arm, got {px}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_snapshot.py::TestAnnotateRegion -v`
Expected: All FAIL with `ImportError` (function does not exist yet)

- [ ] **Step 3: Implement `annotate_region`**

In `computer_use/snapshot.py`, add at the end of the file:

```python
# crop annotation — see plans/active/crop-region-annotation.md
DEFAULT_BRACKET_ARM_PX = 24
DEFAULT_BRACKET_WIDTH_PX = 3
ANNOTATION_COLOR = (255, 0, 0)
ANNOTATION_LABEL_FONT = None  # lazy-loaded default bitmap font


def _get_annotation_font():
    """Lazy-load PIL default font (cached)."""
    global ANNOTATION_LABEL_FONT
    if ANNOTATION_LABEL_FONT is None:
        from PIL import ImageFont
        ANNOTATION_LABEL_FONT = ImageFont.load_default()
    return ANNOTATION_LABEL_FONT


def annotate_region(
    source_path: str,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    style: str = "corner_brackets",
    arm_length: int = DEFAULT_BRACKET_ARM_PX,
    line_width: int = DEFAULT_BRACKET_WIDTH_PX,
) -> str:
    """Draw a red region marker on a copy of the source image. Non-destructive.

    Args:
        source_path: Path to the source PNG. Not modified.
        x, y, width, height: Region in source image pixels.
        style: Marker style. Currently only "corner_brackets" is supported.
        arm_length: Length of each L-bracket arm in pixels.
        line_width: Stroke width in pixels.

    Returns:
        Path to the annotated PNG (a sibling file with `_annotated` suffix).

    Raises:
        ValueError: If style is unknown or region is out of bounds.
        FileNotFoundError: If source_path does not exist.
    """
    if style != "corner_brackets":
        raise ValueError(f"unsupported annotation style: {style!r}")

    from PIL import Image, ImageDraw

    src = Image.open(source_path)
    if src.mode != "RGB":
        src = src.convert("RGB")

    x2, y2 = x + width, y + height
    if x < 0 or y < 0 or x2 > src.width or y2 > src.height:
        raise ValueError(
            f"region ({x},{y},{width},{height}) out of source bounds "
            f"({src.width}x{src.height})"
        )

    annotated = src.copy()
    draw = ImageDraw.Draw(annotated)
    color = ANNOTATION_COLOR
    L = arm_length
    W = line_width

    # Top-left corner
    draw.line([(x, y), (x + L, y)], fill=color, width=W)
    draw.line([(x, y), (x, y + L)], fill=color, width=W)
    # Top-right
    draw.line([(x2, y), (x2 - L, y)], fill=color, width=W)
    draw.line([(x2, y), (x2, y + L)], fill=color, width=W)
    # Bottom-left
    draw.line([(x, y2), (x + L, y2)], fill=color, width=W)
    draw.line([(x, y2), (x, y2 - L)], fill=color, width=W)
    # Bottom-right
    draw.line([(x2, y2), (x2 - L, y2)], fill=color, width=W)
    draw.line([(x2, y2), (x2, y2 - L)], fill=color, width=W)

    # Coordinate label (top-left inside crop, white shadow for legibility)
    label = f"({x},{y},{width},{height})"
    font = _get_annotation_font()
    label_x = x + 6
    label_y = y + 6
    # 1px white shadow
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        draw.text((label_x + dx, label_y + dy), label, fill=(255, 255, 255), font=font)
    draw.text((label_x, label_y), label, fill=color, font=font)

    # Output path: <source>_annotated.png in same directory
    src_path = Path(source_path)
    annotated_path = src_path.with_name(f"{src_path.stem}_annotated.png")
    annotated.save(str(annotated_path))
    return str(annotated_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_snapshot.py::TestAnnotateRegion -v`
Expected: All PASS

---

## Task 2: Wire annotation into `_handle_crop_screenshot`

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_mcp_server.py`:

```python
def test_crop_screenshot_emits_annotated_source(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server
    from PIL import Image

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(shot_path, capture_left=0, capture_top=0)
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 50,
                "y": 60,
                "width": 360,
                "height": 120,
            },
        )
    )

    # New field present
    assert "annotated_source_path" in data
    annotated_path = Path(data["annotated_source_path"])
    assert annotated_path.exists()
    assert annotated_path.name == "shot_annotated.png"

    # Source PNG was NOT overwritten
    src_bytes = shot_path.read_bytes()
    src_img = Image.open(shot_path)
    # sample inside crop region in source — should still be solid color
    assert src_img.getpixel((100, 80)) == (100, 150, 200)

    # Annotated image has red pixels inside the crop region
    annotated_img = Image.open(annotated_path)
    # The crop is (50,60)-(410,180); top-left corner bracket arm at (50,60)-(74,60)
    px = annotated_img.getpixel((60, 61))
    assert px[0] > 200 and px[1] < 50, f"expected red bracket pixel, got {px}"


def test_crop_screenshot_annotate_false_skips_annotation(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 100, 100)
    _write_screenshot_sidecar(shot_path, width=100, height=100)
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 10,
                "y": 10,
                "width": 50,
                "height": 50,
                "annotate": False,
            },
        )
    )

    assert data["cropped"] is True
    # annotated_source_path is either absent or None
    assert data.get("annotated_source_path") in (None, "")
    # No annotated sidecar was written
    assert not (tmp_path / "shot_annotated.png").exists()


def test_crop_screenshot_annotation_does_not_affect_existing_fields(monkeypatch, tmp_path) -> None:
    import computer_use.mcp_server as server

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 1920, 1080)
    _write_screenshot_sidecar(shot_path, capture_left=100, capture_top=200)
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 50,
                "y": 60,
                "width": 360,
                "height": 120,
            },
        )
    )

    # All existing fields preserved
    assert data["cropped"] is True
    assert data["capture_left"] == 150
    assert data["capture_top"] == 260
    assert data["width"] == 360
    assert data["height"] == 120
    assert data["saved_path"]
    assert data["metadata_path"]
    assert data["source_screenshot_path"] == str(shot_path)


def test_crop_screenshot_annotation_failure_is_best_effort(monkeypatch, tmp_path) -> None:
    """Annotation failure must NOT break the crop — annotated_source_path is simply absent."""
    import computer_use.mcp_server as server
    from computer_use import snapshot as snap

    shot_path = tmp_path / "shot.png"
    _create_real_png(shot_path, 400, 300)
    _write_screenshot_sidecar(shot_path, capture_left=0, capture_top=0)
    monkeypatch.setattr(server, "load_config", lambda: _minimal_config(str(tmp_path)))
    # Force annotation to fail
    monkeypatch.setattr(snap, "annotate_region", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("simulated")))

    data = json.loads(
        _call_tool(
            "crop_screenshot",
            {
                "screenshot_path": str(shot_path),
                "x": 10, "y": 10, "width": 50, "height": 50,
            },
        )
    )

    assert data["cropped"] is True
    assert "annotated_source_path" not in data or data.get("annotated_source_path") is None
    # Crop output must still exist
    assert Path(data["saved_path"]).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_server.py::test_crop_screenshot_emits_annotated_source tests/test_mcp_server.py::test_crop_screenshot_annotate_false_skips_annotation tests/test_mcp_server.py::test_crop_screenshot_annotation_does_not_affect_existing_fields tests/test_mcp_server.py::test_crop_screenshot_annotation_failure_is_best_effort -v`
Expected: All FAIL — `annotated_source_path` not in JSON, opt-out flag not honored, failure path untested

- [ ] **Step 3: Update `_handle_crop_screenshot` in `mcp_server.py`**

Replace the body of `_handle_crop_screenshot` with:

```python
def _handle_crop_screenshot(
    args: dict[str, Any],
    cs: CoordinateSystem,
) -> str:
    screenshot_path = args["screenshot_path"]
    x = args["x"]
    y = args["y"]
    crop_width = args["width"]
    crop_height = args["height"]
    annotate = args.get("annotate", True)
    annotate_style = args.get("annotate_style", "corner_brackets")

    meta = _read_screenshot_metadata(screenshot_path)
    if meta is None:
        return json.dumps({
            "error": "screenshot_metadata_not_found",
            "next_action": "Call the MCP screenshot tool first and use its saved_path.",
        })

    if not Path(screenshot_path).exists():
        return json.dumps({
            "error": "screenshot_file_not_found",
            "next_action": "Re-run the MCP screenshot tool; the requested screenshot file is missing.",
        })

    src_w = meta.get("width", 0)
    src_h = meta.get("height", 0)
    if x < 0 or y < 0 or x + crop_width > src_w or y + crop_height > src_h:
        return json.dumps({
            "error": "image_coordinate_out_of_bounds",
            "width": src_w,
            "height": src_h,
        })

    config = load_config()
    screenshot_dir = Path(config["screenshot_dir"]).resolve()
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")[:-3]
    crop_path = str(screenshot_dir / f"crop_{timestamp}.png")

    img = PILImage.open(screenshot_path)
    cropped = img.crop((x, y, x + crop_width, y + crop_height))
    cropped.save(crop_path)

    crop_capture_left = meta["capture_left"] + x
    crop_capture_top = meta["capture_top"] + y
    crop_meta = {
        "schema_version": 1,
        "screenshot_path": crop_path,
        "source_screenshot_path": str(screenshot_path),
        "monitor": meta.get("monitor"),
        "coordinate_space": meta.get("coordinate_space", "monitor"),
        "capture_left": crop_capture_left,
        "capture_top": crop_capture_top,
        "width": crop_width,
        "height": crop_height,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }

    # Non-destructive annotation of source — produces <source>_annotated.png
    annotated_path = None
    if annotate:
        try:
            from computer_use.snapshot import annotate_region

            annotated_path = annotate_region(
                str(screenshot_path),
                x,
                y,
                crop_width,
                crop_height,
                style=annotate_style,
            )
            crop_meta["annotated_source_path"] = annotated_path
        except Exception as exc:  # annotation is best-effort
            logger.warning(
                "crop annotation failed for %s: %s", screenshot_path, exc
            )

    crop_meta_path = crop_path + ".json"
    Path(crop_meta_path).write_text(
        json.dumps(crop_meta, ensure_ascii=False), encoding="utf-8"
    )

    response = {
        "cropped": True,
        "saved_path": crop_path,
        "metadata_path": crop_meta_path,
        "source_screenshot_path": str(screenshot_path),
        "capture_left": crop_capture_left,
        "capture_top": crop_capture_top,
        "width": crop_width,
        "height": crop_height,
    }
    if annotated_path is not None:
        response["annotated_source_path"] = annotated_path

    return json.dumps(response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mcp_server.py::test_crop_screenshot_emits_annotated_source tests/test_mcp_server.py::test_crop_screenshot_annotate_false_skips_annotation tests/test_mcp_server.py::test_crop_screenshot_annotation_does_not_affect_existing_fields -v`
Expected: All PASS

- [ ] **Step 5: Run full crop-related test suite to confirm no regressions**

Run: `pytest tests/test_mcp_server.py -k crop -v`
Expected: All PASS (existing `test_crop_screenshot_inherits_offsets`, `test_crop_screenshot_out_of_bounds`, `test_click_on_screenshot_works_with_crop` remain green)

---

## Task 3: Add `annotate` and `annotate_style` parameters to tool schema

**Files:**
- Modify: `computer_use/tools/schemas.py`

- [ ] **Step 1: Update the `crop_screenshot` Tool definition**

In `computer_use/tools/schemas.py`, locate the `crop_screenshot` Tool block and replace it with:

```python
    Tool(
        name="crop_screenshot",
        description="Crop a region from a saved screenshot, preserving coordinate metadata for click_on_screenshot. Use to zoom in on small targets. By default also writes a non-destructive annotated copy of the source with the crop region outlined in red, returned as `annotated_source_path` so models can visually verify the region before reading the cropped content.",
        inputSchema={
            "type": "object",
            "properties": {
                "screenshot_path": {"type": "string"},
                "x": {"type": "integer", "description": "Left edge in image pixels."},
                "y": {"type": "integer", "description": "Top edge in image pixels."},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "annotate": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, write a red L-bracket annotated copy of the source to <source>_annotated.png and return its path. Default true. Set false to skip annotation for performance or when debugging cluttered overlays.",
                },
                "annotate_style": {
                    "type": "string",
                    "enum": ["corner_brackets"],
                    "default": "corner_brackets",
                    "description": "Annotation marker style. Currently only `corner_brackets` is supported.",
                },
            },
            "required": ["screenshot_path", "x", "y", "width", "height"],
        },
    ),
```

- [ ] **Step 2: Verify the schema validates**

Run: `python -c "from computer_use.tools.schemas import TOOLS; print([t.name for t in TOOLS if t.name == 'crop_screenshot'][0])"`
Expected: prints `crop_screenshot` without error

- [ ] **Step 3: Re-run all crop tests**

Run: `pytest tests/test_mcp_server.py -k crop tests/test_snapshot.py::TestAnnotateRegion -v`
Expected: All PASS

---

## Task 4: Update skill documentation

**Files:**
- Modify: `skills/computer-use/SKILL.md`

- [ ] **Step 1: Update tool reference table entry**

In the tool reference table in `skills/computer-use/SKILL.md`, update the `crop_screenshot` row:

Before:
```
| | `crop_screenshot` | `screenshot_path`, `x`, `y`, `width`, `height` | Zoom into small target, preserves coordinate mapping |
```

After:
```
| | `crop_screenshot` | `screenshot_path`, `x`, `y`, `width`, `height`, `annotate?`, `annotate_style?` | Zoom into small target, preserves coordinate mapping. By default also writes `<source>_annotated.png` with red L-bracket markers so the agent can visually verify the cropped region before reading the crop content. |
```

- [ ] **Step 2: Add a verification-flow paragraph**

After the "Small target: crop then click" example in the skill document, add a new paragraph:

```markdown
### Verifying crop region before relying on cropped content

When a crop returns unreadable content (uniform color, looks like desktop background, doesn't match expected UI element), do not blindly retry with a different region estimate. Instead:

1. Read the `annotated_source_path` returned by `crop_screenshot` (or the source screenshot sidecar's `annotated_source_path` field if available).
2. Confirm the red L-brackets in that annotated image actually surround the intended control.
3. If brackets miss the target, re-measure from the source screenshot, then call `crop_screenshot` again with corrected coordinates.

The annotated image is non-destructive — the original source PNG is never overwritten, so the agent can repeatedly crop from the same source and inspect each annotation. Set `annotate: false` to skip the sidecar write when not needed (e.g. when cropping in tight performance-sensitive loops).
```

- [ ] **Step 3: Add a "Crops and annotation" entry under Context Budget**

After the "Crop after orienting" bullet under Context Budget, append a new bullet:

```markdown
- **Crop annotated source on disambiguation.** When a cropped image is ambiguous or appears empty, re-read the `annotated_source_path` to confirm the crop region was correct before trying alternative coordinates. This is far cheaper than re-screenshotting the whole screen.
```

- [ ] **Step 4: Spot-check the rendered skill**

Run: `grep -n 'annotat' "skills/computer-use/SKILL.md"`
Expected: 3+ matches (tool table, verification paragraph, context budget bullet)

---

## Task 5: End-to-end manual smoke test

**Files:**
- Modify: `tests/manual/manual_test_checklist.md` (if such checklist exists)

- [ ] **Step 1: Run the live MCP server and crop a real screenshot**

Run the MCP server, then via an MCP client:
1. Call `screenshot(monitor=1)`, capture saved_path as `S`.
2. Call `crop_screenshot(screenshot_path=S, x=100, y=100, width=400, height=300)`.
3. Confirm response JSON contains `annotated_source_path` ending in `_annotated.png`.
4. Open both `S` and the annotated path in an image viewer; visually confirm the source PNG is unchanged and the annotated PNG shows red L-brackets around the (100,100)-(500,400) region with a `(100,100,400,300)` label.

- [ ] **Step 2: Test opt-out**

Call `crop_screenshot(screenshot_path=S, x=100, y=100, width=400, height=300, annotate=false)`.
Confirm `annotated_source_path` is absent and no `_annotated.png` sidecar was written.

- [ ] **Step 3: Test crop on out-of-bounds**

Call `crop_screenshot(screenshot_path=S, x=99999, y=99999, width=400, height=300)`.
Confirm `error` is `image_coordinate_out_of_bounds` and **no** annotated file is written.

- [ ] **Step 4: Document results in review report**

If anything failed, file a `docs/problems/bugfix/...md` per the project's `bugfix-doc` convention. If everything passed, add an entry to the appropriate `docs/problems/...` note acknowledging the change was manually verified.

---

## Rollback Plan

If annotation causes regressions (e.g. Pillow errors on certain PNGs):
1. Revert `mcp_server.py` changes in Task 2 (the JSON response keeps the same fields, just without `annotated_source_path`).
2. Keep `snapshot.py` and the tests — they are inert if not called.
3. Update skill docs to remove the verification paragraph.

The default `annotate=True` can be flipped to `annotate=False` globally by changing the schema default if needed, without code changes to the handler.

---

## Open Questions for Reviewer

1. **Style choice**: Is "corner brackets + coordinate label" the preferred default, or should it be a full rectangle? (Tradeoff: brackets are less visually obstructive but may be harder to spot at a glance.)
2. **Label content**: Should the label include the source path basename, or just `(x,y,w,h)`? Current plan: just coordinates, path is in the sidecar JSON.
3. **File location**: `<source>_annotated.png` (same dir as source) vs `screenshot_dir/anno_<timestamp>.png` (centralized)? Current plan: same dir for cache locality; one extra `_annotated.png` per source is acceptable.
4. **Annotation on `click_on_screenshot`**: Should this tool also annotate its target point on the source? Out of scope for this plan; flagged as future work.