# Slide Image To Editable PPTX

This workflow adapts the core contract from
[w1163222589-coder/slide-image-to-editable-pptx](https://github.com/w1163222589-coder/slide-image-to-editable-pptx)
for EasySlides' SVG/DrawingML backend.

Use it when the source of truth is a slide screenshot, exported slide PNG, or
AI mockup image and the user wants a PowerPoint deck that visually matches the
source while keeping text and simple geometry editable.

## Mandatory reconstruction-mode choice

Before reconstruction, follow `workflows/clarification-gate.md`: confirm
`full_vector` (全图矢量重建) or `preserve_complex_images` (保留复杂配图).
No automatic default, including urgent requests. For partial rebuilds this
contract applies within the user-selected regions only.

Both modes require native PPT text boxes. Preserve one source line in one text
box; merge OCR fragments and use text runs for mixed styling. Independent labels
and separate table cells remain separate. Check line continuity, baseline and
alignment in actual PPT renders; OCR box count is not the intended text-box count.
Record `source_text_lines` after inspecting the original image: one complete
logical line per entry, including punctuation, labels and page numbers. Do not
derive this list solely from OCR fragments or the exported PPTX. QA requires it
on slides with Layer C text; graphics-only partial selections are exempt.

In `full_vector`, reconstruct visual assets as editable vector geometry and
verify editability after PPT export; outlined text and bitmap-wrapped SVG do not
satisfy the contract. Ask before any raster exception. The raster asset policies
below apply only to `preserve_complex_images` or explicitly approved exceptions.

## EasySlides Entry Point

Create a reconstruction project with the normal project manager, then scaffold
the image-specific handoff files:

```powershell
python scripts/project_manager.py init <project_name> --format ppt169 --kind slide_image_reconstruction
python scripts/image_reconstruction_pipeline.py init projects/<project_name>_ppt169_<date> path/to/slide_001.png --production-scheme <confirmed_scheme> --reconstruction-mode <confirmed_mode>
```

Use the user's confirmed `image_full_rebuild` or `image_partial_rebuild` scheme
and `full_vector` or `preserve_complex_images` mode. Init records both in the
inventory and run report. Existing original images are never replaced, including
when `--overwrite-analysis` is used to regenerate the inventory scaffold.

The project layout is intentionally the same shape as other EasySlides work:

```text
projects/<name>/
  sources/                         # source slide images
  analysis/_analysis.json           # Layer A/B/C element inventory
  pages/page_001/manifest.json      # editable reconstruction manifest / IR handoff
  pages/page_001/assets/split/      # split or preserved visual assets
  pptx/                             # reconstructed PPTX
  reports/                          # inventory, text, asset, and render QA reports
```

The default QA mode is `faithful-practical`: text fit, structural editability,
and split asset safety are hard gates, while source-vs-render pixel difference
is reported for inspection but not treated as a hard failure. Use
`--mode pixel-strict` only when the source image must be matched at near-pixel
level.

Both QA modes require the source images, completed inventory, exported PPTX and
rendered PNGs with matching page counts. Missing evidence blocks acceptance.
Partial rebuilds also compare pixels outside selected regions in both modes.

## Principle

Every visible source-image element must be assigned to exactly one layer before
assembly:

| Layer | Content | EasySlides implementation |
| --- | --- | --- |
| A: Visual Asset | Complex illustrations, scientific figures, detailed icons, photos, textured decorations | Clean transparent PNG generated from a prompt, or a mask/alpha-backed preserved source asset |
| B: Native Structure | Rectangles, panels, dividers, lines, arrows, badges, simple circles | SVG/DrawingML native shapes |
| C: Editable Content | All readable text, labels, captions, formulas, page numbers | SVG text converted to native PPTX text |

The important operational rule is stricter than ordinary screenshot copying:

- Whole-page rebuilds may not use a full-slide screenshot as a background.
  Partial rebuilds retain the source background, named `source_background`,
  and replace only the selected regions.
- Do not bake readable text into Layer A images.
- Do not use rectangular crops as element boundaries. If source pixels are
  preserved, the asset must be mask/alpha-backed and have padding so no content
  is clipped.
- Do not redraw complex illustrations with crude PPT primitives. In
  `preserve_complex_images`, use preserved clean source assets; in `full_vector`,
  rebuild faithful vector detail and disclose limitations before proceeding.

## Phase 1: Element Inventory

Create `_analysis.json` before writing slide code. Use percentage coordinates
so the inventory survives different image resolutions:

```json
{
  "schema_version": "easyslides.slide_image_inventory.v1",
  "production_scheme": "image_full_rebuild",
  "reconstruction_mode": "preserve_complex_images",
  "slides": [
    {
      "slide_id": "s01",
      "source_image": "slide_01.png",
      "width_px": 1920,
      "height_px": 1080,
      "source_text_lines": ["Example title"],
      "elements": [
        {
          "element_id": "s01_e01",
          "description": "main illustration without labels",
          "bbox_percent": {"x": 42, "y": 18, "w": 45, "h": 58},
          "layer": "A",
          "implementation": "imagegen",
          "asset_policy": {"no_text": true, "transparent": true},
          "z_order": 3
        },
        {
          "element_id": "s01_e02",
          "description": "slide title",
          "bbox_percent": {"x": 6, "y": 6, "w": 40, "h": 8},
          "layer": "C",
          "implementation": "native_text",
          "text": "Example title",
          "z_order": 8
        }
      ],
      "completeness_check": {
        "performed": true,
        "layer_a_count": 1,
        "notes": "Checked corners, cards, small icons, and decorative details."
      }
    }
  ]
}
```

Validate the inventory:

For partial rebuilds, each slide additionally records `reconstruction_regions`
as percentage-coordinate objects such as `{"x": 6, "y": 6, "w": 40, "h": 8}`.
Use `[]` for an untouched page; at least one page must have a selected region.
The element inventory and `source_text_lines` cover the selected scope only.
Source-reviewed lines are checked against complete native text lines, including
table cells. Reconcile corrected OCR text in Layer C with this list before QA.
An approved full-vector raster exception is recorded on its slide as
`approved_raster_exceptions: [{"shape_name": "figure_1", "approval": "user confirmation reference"}]`.

```powershell
python scripts/slide_image_inventory.py validate projects/<name>/analysis/_analysis.json --report projects/<name>/reports/slide_image_inventory_report.json
```

The validator blocks common reconstruction failures: missing completeness pass,
Layer A assets that contain text, full-slide assets, malformed bounding boxes,
and rectangular source crops.

## Phase 2: Asset Policy

For Layer A, choose one of two policies:

- `imagegen`: use when the visual is decorative or illustrative and can be
  regenerated cleanly. The prompt must specify content, style, colors, aspect
  ratio, transparency, and end with "No text, no labels, no numbers, no letters."
- `preserve_masked_source`: use when the source asset is evidence, a scientific
  figure, or a user-provided visual that should not be redrawn. Extraction must
  use a mask or alpha matte, not a rectangular crop. If text is present, OCR it
  into Layer C and remove/mask it from the asset when feasible.
- `preserve_source_frame`: use for complex raster illustrations that become
  visibly worse when forced into crude vectors. The asset remains a movable,
  replaceable PPT image frame, while nearby labels, formulas, simple panels,
  axes, and data marks remain editable native objects. Do not use this for
  closed transparent shapes such as circles or rings; those still require
  alpha padding and clipping checks.

For the biochar-style infographic case, most icon/illustration groups should be
Layer A assets, panel backgrounds and arrows should be Layer B, and every label
should be Layer C.

## Phase 3: Assembly

Author the slide as SVG/shape IR and export through EasySlides' existing
DrawingML pipeline. Stack objects in this order:

1. Background color or structural panel fills.
2. Large Layer A visual assets.
3. Layer B panel frames, dividers, lines, and arrows.
4. Small Layer A icons and figures inside panels.
5. Layer C text boxes.
6. Logos or brand marks that must sit on top.

Convert source coordinates with:

```text
x_in = x_px / source_width_px * slide_width_in
y_in = y_px / source_height_px * slide_height_in
```

## Phase 4: Validation

Run the normal EasySlides gates plus the image-reconstruction structural gate:

```powershell
python scripts/image_reconstruction_pipeline.py qa projects/<name> --pptx projects/<name>/pptx/output.pptx --rendered-dir projects/<name>/reports/rendered_png

# Or run individual gates while debugging:
python scripts/validate_pptx_text_layout.py output.pptx --report reports/text_layout_report.json
python scripts/validate_image_reconstruction_pptx.py output.pptx --report reports/image_reconstruction_pptx_report.json
python scripts/render_pptx_png.py output.pptx --out reports/rendered_png --report reports/rendered_png_report.json
python scripts/visual_measure_gate.py --existing-report pptx_text_layout=reports/text_layout_report.json --existing-report image_reconstruction_structure=reports/image_reconstruction_pptx_report.json --report reports/visual_measure_report.json
```

Inspect the rendered PNG against the source image. If a Layer A asset looks
dirty, clipped, or includes text, fix the inventory/asset first rather than
trying to hide the problem during assembly.

Compare title font family/weight, mixed-language baselines, table alignment,
dividers and illustration-to-panel background transitions in an actual Office
render. Preserve source alignment instead of automatically centering labels.
Do not squeeze a mismatched font with extreme negative character spacing.
Structural QA proves editability and text coverage, not visual fidelity; record
remaining visual differences separately and never label an unreviewed render
as visually accepted.

For strict acceptance:

```powershell
python scripts/image_reconstruction_pipeline.py qa projects/<name> --mode pixel-strict --pptx projects/<name>/pptx/output.pptx --rendered-dir projects/<name>/reports/rendered_png
```
