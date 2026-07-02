# PPTX To EasySlides Template Workflow

Use this when a source PPTX should become an EasySlides template rather than a
one-off edited deck. The default route is source-faithful first, template
generalization second.

Agent skill order: `ppt-distill` -> `pptx` -> `easyslides-template-reuse` ->
`ppt-template-spec`.

## Output Contract

The workflow produces two artifact folders:

- `templates/reference/template_asset_sources/<template_id>/`
  - `manifest.json`
  - `summary.md`
  - `distilled_spec.json`
  - `template_language.md`
  - `editable_rebuild_plan.json`
  - `adaptation_strategy.json`
  - `source_geometry_risks.json`
  - `contact_sheet.html`
  - `assets/`
  - `svg/`
  - `svg-flat/`
- `templates/layouts/<template_id>/`
  - copied source-faithful SVG pages
  - `design_spec.md`
  - `layouts.json`
  - `page_catalog.json`
  - `story_structure.json`
  - `rules.md`
  - generated contract sidecars from `template_contract_pack.py`

## One-Command Draft

```powershell
python scripts/pptx_template_distill.py "path\to\source.pptx" --template-id my_template
```

This command imports the PPTX, distills the template language, creates a
slot-guided mirror template pack, and writes the machine-readable contract
sidecars.

If `template_language.md` reports high-risk effects such as gradients, filters,
opacity, crop/rotation, or text-anchor alignment, create a source-rendered
raster baseline first. Treat that baseline as the visual truth surface, not as
the final editable template.

## Review Sequence

1. Open the reference contact sheet:

```powershell
start templates\reference\template_asset_sources\my_template\contact_sheet.html
```

2. Review `distilled_spec.json`, `template_language.md`, and
`adaptation_strategy.json`. Confirm these fields are accurate:

- `identity_must_preserve`
- `structural_primitives`
- `slot_candidates`
- `adaptable_patterns`
- `forbidden_drift`
- material-type routing for user-provided content
- overflow policy and validation gates for template adaptation
- source-authored geometry risks that must not be treated as freeform slots

3. Inspect the generated template contract:

```powershell
python scripts\template_contract_pack.py templates\layouts\my_template
```

4. Run geometry QA on the SVG template draft:

```powershell
python scripts\template_geometry_qa.py templates\layouts\my_template --report tmp\my_template_geometry_svg_report.json
```

This gate must pass before the draft can be treated as a usable template. It
checks that text stays inside declared cards/containers, content does not cross
protected chrome such as navigation rails, and image references are not missing.

5. Export the draft template SVGs as an editable PPTX:

```powershell
python scripts\svg_to_pptx.py templates\layouts\my_template --only native -t none -a none -o tmp\my_template_review.pptx
```

6. Run geometry QA on the exported PPTX:

```powershell
python scripts\template_geometry_qa.py templates\layouts\my_template --pptx tmp\my_template_review.pptx --report tmp\my_template_geometry_pptx_report.json
```

This catches export-time drift, including group transforms that move content
into fixed navigation/header regions.

7. Run text-layout validation on the exported PPTX:

```powershell
python scripts\validate_pptx_text_layout.py tmp\my_template_review.pptx --report tmp\my_template_text_layout_report.json
```

For delivery or CI, prefer the unified visual measurement report so slot
contracts, template geometry, PPTX text layout, and optional render diff have
one pass/fail verdict:

```powershell
python scripts\visual_measure_gate.py --template-dir templates\layouts\my_template --pptx tmp\my_template_review.pptx --report tmp\my_template_visual_measure_report.json
```

8. Only after the faithful baseline is accepted, revise the template into one
of these production modes:

- `classic`: flexible visual style with reusable shells
- `mirror`: exact page replacement with fixed geometry
- `slot_guided_mirror`: fixed source pages plus role, density, and slot rules

9. For any fidelity claim, compare PowerPoint-rendered source PNGs against
PowerPoint-rendered generated PNGs. A native editable PPTX with a high visual
diff is a reconstruction draft, not a faithful template.

```powershell
python scripts\render_pptx_png.py source_template.pptx --out tmp\source_render_png --report tmp\source_render_png_report.json
python scripts\render_pptx_png.py tmp\my_template_review.pptx --out tmp\generated_render_png --report tmp\generated_render_png_report.json
python scripts\pptx_visual_diff.py tmp\source_render_png tmp\generated_render_png --out tmp\my_template_visual_diff
python scripts\visual_measure_gate.py --template-dir templates\layouts\my_template --pptx tmp\my_template_review.pptx --source-render-dir tmp\source_render_png --generated-render-dir tmp\generated_render_png --visual-diff-out tmp\my_template_visual_diff --report tmp\my_template_visual_measure_report.json
```

## Guardrails

- Do not redesign during the first pass.
- Do not remove source cover or ending geometry until a reviewer approves it.
- Do not register the template from SVG previews alone; export and inspect the
  PPTX as well.
- Do not promote a draft when either SVG or exported-PPTX geometry QA fails.
- Keep the raw PPTX and imported assets in the reference folder, not in the
  runtime template contract.
