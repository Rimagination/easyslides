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

### Fast, faithful execution

Reuse confirmed route, mode, reference and page count from this task. Keep one
page ledger in the research document: page/claim, original figure or table and
citation, generated item, selected output, reconstruction and QA status. Each
evidence page needs an observation and interpretation; do not fill gaps with
generic bullets or decorative numeric charts. Mark proposals as untested.

Before scaling, generate a cover and the densest evidence page, then reconstruct
and Office-render those two pages. Review both the generated images and the
editable renders: font metrics, mixed-language lines, table cells, original
figure labels and footer clearance. A good raster pilot alone does not validate
the reconstruction method. Reuse approved pilots in the final deck.

Once the direction is approved, continue in small batches without additional
confirmation of unchanged decisions. Reuse verified outputs and OCR caches;
only regenerate rejected pages. Diagnose bad crops/text/geometry in the affected
page before rerunning the final deck checks. Do not rescan all references,
re-OCR unchanged pages, or create a new bespoke PPTX exporter for each deck.
The same SVG/shape IR backend serves the whole deck; name pages uniquely
(`page_001.svg`, etc.) so notes and source links bind to the correct slide.

Measure Chinese and Latin text using appropriate installed fonts; do not apply
an English table font to Chinese explanations. Merge OCR fragments into logical
lines, keep table cells separate, remove duplicate raster labels, and preserve
figure aspect ratio and frame boundaries. Inspect full-size source/render pairs
for clipped assets, seams, arrows, dense labels and the ending page.

Keep raw pixel QA unchanged. Original-figure restoration and agreed chrome
normalization must be documented; they do not justify weakening global thresholds
or claiming delivery-ready while the full-page fidelity check still fails.

### Native tables

When the source contains a real table, record the table as a Layer B
`native_table` region and each complete cell as its own Layer C element. The SVG
handoff marks that region with `data-pptx-table="true"`; each cell group declares
1-based `data-pptx-table-row` and `data-pptx-table-col` values, and may declare
`data-pptx-table-row-span` or `data-pptx-table-col-span`. Declare the table frame
and its measured `data-pptx-table-col-widths` and
`data-pptx-table-row-heights` in source-canvas pixels. The native exporter emits
one PowerPoint `a:tbl` with real rows, columns, cells and merge metadata.

```xml
<g id="evidence-table" data-pptx-table="true"
   data-pptx-table-x="100" data-pptx-table-y="180"
   data-pptx-table-w="1080" data-pptx-table-h="360"
   data-pptx-table-rows="3" data-pptx-table-cols="3"
   data-pptx-table-col-widths="180 450 450"
   data-pptx-table-row-heights="72 144 144">
  <g data-pptx-table-cell="true" data-pptx-table-row="1" data-pptx-table-col="1">
    <rect x="100" y="180" width="180" height="72" fill="#E4F1FC" stroke="#B8D8ED"/>
    <text data-pptx-textbox="true" data-pptx-valign="middle"
          data-pptx-box-x="100" data-pptx-box-y="180"
          data-pptx-box-w="180" data-pptx-box-h="72"
          text-anchor="middle">路径</text>
  </g>
</g>
```

Keep table cells separate in the inventory, preserve measured column and row
geometry, and inspect the exported table after row formatting and column
resizing on a copy. Cards, panels and complex scientific figures keep their
existing native-shape or source-asset treatment unless the inventory identifies
them as tabular content.

### Complete-slide generation handoff

For new ImageGen pages, use the existing `image-acquire` host-native path. Set
the image resource manifest's `purpose` to `slide_reconstruction`,
`acquisition.path` to `host-native`, and `reference_image` to the actual selected
image. An optional `reference_id` must match the image-reference catalog exactly.
Prefer the selected full reference image. If the host cannot decode it, the same
catalog entry's `preview` is an explicit transport alternative; keep `reference_id`
and record the actual attached JPEG. Do not retry the identical decode failure,
silently select another style, or rewrite an existing generation receipt.
Each item uses `text_policy: embedded`, its complete page content in `prompt`,
and the intended `aspect_ratio`. Evidence pages additionally declare
`evidence_required: true` and `evidence_images` entries with `path`, `citation`
and `figure_id`. Keep the manifest beside its generated output images.

Prepare the normal acquisition request. Inspect all attached images, then pass
the returned `tool_arguments` verbatim to the host ImageGen tool: this includes
the template AND original scientific figures in `referenced_image_paths`.
Generate a complete content page, including text. Save the returned image at
its declared output path. Record the actual call as JSON with `tool_name` and
`tool_arguments`, then register it. Preparation also captures reference file
identities; recording rejects references changed since preparation. Keep the
prepared `image_acquisition_request.json`; if a custom path was used, include
that `request_path` in the call JSON:

```powershell
python scripts/easyslides.py image-acquire record-result <manifest.json> --item <item_id> --image <declared_output.png> --call <actual_call.json>
```

The receipt binds the request, reference files and output bytes. It is recorded
host-call evidence, not independent attestation of the remote service. File
existence alone cannot mark a complete slide Generated. No API, manual or
template-shell fallback is allowed; report unavailable host generation honestly.

Preview a cover and a dense evidence page first; obtain the user's visual
direction before scaling to the full deck. Reuse accepted pages and regenerate
only failed pages. Verify original paper figures against their sources: ImageGen
may distort labels or observations even when the prompt asks for preservation.
Use original figure pixels during reconstruction if needed; disclose material
changes to an approved page and obtain approval. Never invent research data.

After approval, pass `--generation-manifest <manifest.json>` to reconstruction
init with the images in manifest order. This locks the generated source chain.
User-supplied existing images skip generation and this optional argument; never
fabricate a call receipt for them. Reconstruction follows each approved image's
positions, typography, colors and artwork. Other template layouts are out of
scope. Keep complex artwork as independently editable image frames when the
selected mode permits; keep text and simple geometry native.

#### Reuse final pages across generation batches

Pass an ordered selection file to the existing `--generation-manifest` argument
when approved pages span initial, retry or corrected batches:

```json
{
  "schema_version": "easyslides.generation_selection.v1",
  "pages": [
    {"page": 1, "manifest": "generation/initial.json", "item_id": "s01"},
    {"page": 2, "manifest": "generation/retry.json", "item_id": "s02_v2"}
  ]
}
```

Paths are relative to this selection file. Init and final QA validate each
selected item's actual receipt and output in order, even if its batch contains
unfinished/rejected alternatives. They reject duplicate selections, missing
items, changed outputs, mixed reference styles and inconsistent pagination.
This file selects existing receipts; it never synthesizes new receipts or calls
ImageGen. After initialization the source images remain locked. If an approved
source itself changes, initialize a new reconstruction revision with an updated
selection; reuse unaffected verified assets without overwriting the old sources.

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

The default QA mode is `pixel-strict`: text fit, structural editability,
asset safety, provenance and source-render differences are blocking. Explicit
`--mode faithful-practical` is for diagnosis; failed visual comparison still sets
`delivery_ready=false` and causes a nonzero CLI exit. Automated pixel thresholds
are necessary checks, not a substitute for full-size visual review.

Always render the exact delivery PPTX with `render_pptx_png.py`; its automatic
`render_receipt.json` binds every ordered PNG to that PPTX. QA rejects missing or
stale receipts, changed source files and non-contiguous slide numbering. When
multiple PPTX candidates exist, specify `--pptx`; filenames and modification
times must never silently select a version. Keep confirmed route/mode choices
unchanged; start a new project for an intentional route change.

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
  "alignment_contract": {
    "schema_version": "easyslides.alignment_contract.v1",
    "coordinate_space": "source_percent_to_1280x720",
    "canvas": {"width": 1280, "height": 720},
    "geometry_policy": {
      "native_text_box": "absolute_canvas",
      "parent_transform": "forbidden_for_editable_text",
      "match_inventory_boxes": true,
      "box_tolerance_px": 4,
      "center_lock_tolerance_px": 2
    },
    "protected_regions": []
  },
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

### Shared Alignment Contract

`image_reconstruction_pipeline.py init` writes an `alignment_contract` into the
inventory. It establishes one 1280x720 canvas for the whole image-to-editable
route:

- `bbox_percent` is the source-image box for each Layer C line and maps directly
  to the native PPTX text-frame box.
- SVG `data-pptx-box-x/y/w/h` values are absolute canvas coordinates. Editable
  text cannot inherit a parent `translate`, `scale`, or other group transform.
- Center-locked labels declare `alignment.center_lock=true` and use middle
  vertical alignment. Cover metadata, navigation labels, card controls, and the
  ending page follow the same rule.
- A slide may declare `alignment_contract.protected_regions` for navigation
  rails, title bars, or footer chrome. Text crossing those regions requires an
  explicit chrome binding.

The route checks the authored SVG before export when page SVGs are present, then
checks the actual native PPTX frames after export. A frame shift, anchor drift,
parent-transform violation, or protected-region overlap blocks QA with the
slide and element id in the report. The reports are written to
`reports/alignment_contract_svg_report.json` and the alignment section of
`reports/image_reconstruction_pptx_report.json`.

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
python scripts/render_pptx_png.py projects/<name>/pptx/output.pptx --out projects/<name>/reports/rendered_png
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

### Deck-wide pagination contract (mandatory)

Lock pagination once before generation: visible slides, physical/logical numbering,
total, literal format, fixed textbox, alignment, font, size, weight and color.
Pass each exact counter and placement with the template image to ImageGen.
During reconstruction exclude source OCR counters and emit one native footer from
the locked contract; never independently estimate each page's footer typography.
Keep source images unchanged and record approved footer normalization as a visual
deviation. New complete-slide manifests must include one shared `pagination`
object and an integer `page` on every item. Example for physical numbering:

```json
"pagination": {
  "total": 12, "omit_pages": [1],
  "box": [1178, 694, 70, 22],
  "font_family": "Arial", "font_size": 14.5,
  "color": "#526575", "align": "right",
  "format": "{page:02d} / {total:02d}"
}
```

Coordinates and font size use a 1280x720 canvas. The actual host prompt includes
the exact derived counter and reserved box; malformed contracts fail before
generation. The helper `image_generation_contract.pagination_text` also supplies
the counter for native reconstruction. This initial helper covers physical
numbering with optional hidden pages; logical numbering stays an explicit
manually recorded contract. Legacy manifests without pagination remain readable
without changing historical prompts/receipts; do not patch them retroactively.
For an in-progress legacy deck with approved pilots, keep all remaining batches
in its legacy format and normalize native footers from the recorded deck contract.
Do not mix legacy and new pagination manifests in one selection. The structured
pagination requirement applies from the start of a new deck; migrating a started
deck must not force regeneration of already approved pages.
Run the shared `validate_pptx_text_layout.py` before delivery. Native fraction-style
footers in the bottom 10% are checked for format/style/geometry, sequence, total,
duplicates and internal omissions. Raster-only counters and omitted terminal
footers still require visual/contract review; this detector cannot certify them.

For strict acceptance:

```powershell
python scripts/image_reconstruction_pipeline.py qa projects/<name> --mode pixel-strict --pptx projects/<name>/pptx/output.pptx --rendered-dir projects/<name>/reports/rendered_png
```
