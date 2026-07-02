# Slide Image To Editable PPTX

This workflow adapts the core contract from
[w1163222589-coder/slide-image-to-editable-pptx](https://github.com/w1163222589-coder/slide-image-to-editable-pptx)
for EasySlides' SVG/DrawingML backend.

Use it when the source of truth is a slide screenshot, exported slide PNG, or
AI mockup image and the user wants a PowerPoint deck that visually matches the
source while keeping text and simple geometry editable.

## EasySlides Entry Point

Create a reconstruction project with the normal project manager, then scaffold
the image-specific handoff files:

```powershell
python scripts/project_manager.py init <project_name> --format ppt169 --kind slide_image_reconstruction
python scripts/image_reconstruction_pipeline.py init projects/<project_name>_ppt169_<date> path/to/slide_001.png
```

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

## Principle

Every visible source-image element must be assigned to exactly one layer before
assembly:

| Layer | Content | EasySlides implementation |
| --- | --- | --- |
| A: Visual Asset | Complex illustrations, scientific figures, detailed icons, photos, textured decorations | Clean transparent PNG generated from a prompt, or a mask/alpha-backed preserved source asset |
| B: Native Structure | Rectangles, panels, dividers, lines, arrows, badges, simple circles | SVG/DrawingML native shapes |
| C: Editable Content | All readable text, labels, captions, formulas, page numbers | SVG text converted to native PPTX text |

The important operational rule is stricter than ordinary screenshot copying:

- Do not use a full-slide screenshot as a background.
- Do not bake readable text into Layer A images.
- Do not use rectangular crops as element boundaries. If source pixels are
  preserved, the asset must be mask/alpha-backed and have padding so no content
  is clipped.
- Do not redraw complex illustrations with crude PPT primitives. Use generated
  or preserved clean PNG assets.

## Phase 1: Element Inventory

Create `_analysis.json` before writing slide code. Use percentage coordinates
so the inventory survives different image resolutions:

```json
{
  "schema_version": "easyslides.slide_image_inventory.v1",
  "slides": [
    {
      "slide_id": "s01",
      "source_image": "slide_01.png",
      "width_px": 1920,
      "height_px": 1080,
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

```powershell
python scripts/slide_image_inventory.py validate projects/<name>/_analysis.json --report projects/<name>/reports/slide_image_inventory_report.json
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

For strict acceptance:

```powershell
python scripts/image_reconstruction_pipeline.py qa projects/<name> --mode pixel-strict --pptx projects/<name>/pptx/output.pptx --rendered-dir projects/<name>/reports/rendered_png
```
