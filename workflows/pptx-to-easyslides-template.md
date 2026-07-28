# PPTX To EasySlides Template Workflow

Use this when a source PPTX should become an EasySlides template rather than a
one-off edited deck. The route is source-faithful evidence first, semantic
generalization second, and fail-closed production promotion last.

Plugin skill order: canonical `easyslides` -> plugin-local
`easyslides-distill`. Repository workflows own template reuse and template
specification; separately installed legacy skills are compatibility references
only.

## Output Contract

The workflow separates four artifact layers:

- `templates/reference/template_asset_sources/<template_id>/`
  - `manifest.json`
  - `source_graph.json`
  - `distill_manifest.json`
  - `identity_spec.json`
  - `layout_spec.json`
  - `component_catalog.json`
  - `slot_contracts.json`
  - `asset_provenance.json`
  - `adaptation_policy.json`
  - `review_queue.json`
  - `design_system_pack.json`
  - `component_registry_fragment.json`
  - `projection_manifest.json`
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
  - an evidence-driven 3-5 shell profile: cover/content/ending required;
    toc/chapter optional only when supported by source evidence
  - `body_variants.json` for source-derived content forms
  - ordered `component_refs` linking each composed variant to registered
    template or global component assets
  - `source_page_roster.json` for full source-page traceability
  - `design_spec.md`
  - `layouts.json`
  - `page_catalog.json`
  - `story_structure.json`
  - `rules.md`
  - generated contract sidecars from `template_contract_pack.py`
- `templates/layouts/<template_id>_reusable/`
  - optional source-scoped review candidate
  - never selected as a production template by source slide number or DOM-order
- `templates/components/source_templates/<template_id>_kit/`
  - source-scoped renderable component and symbol fragments
  - unresolved or metadata-only candidates stay in `review_queue`
- `templates/layouts/<semantic_template_id>/`
  - content-free semantic layout family
  - `layouts.json`, `body_variants.json`, and `template_status.json`
  - named slots with explicit capacity and overflow policy

## One-Command Draft

```powershell
python scripts/easyslides.py distill "path\to\source.pptx" --template-id my_template
```

This command imports the PPTX, distills the template language, creates the
faithful review pack, and writes machine-readable contract sidecars. It does
not promote assets by default.

If `template_language.md` reports high-risk effects such as gradients, filters,
opacity, crop/rotation, or text-anchor alignment, create a source-rendered
raster baseline first. Treat that baseline as the visual truth surface, not as
the final editable template.

## Review Sequence

1. Open the reference contact sheet:

```powershell
start templates\reference\template_asset_sources\my_template\contact_sheet.html
```

2. Review `source_graph.json` and `distill_manifest.json` first. Confirm that
the source graph is `ready` for a real PPTX, and that slide -> layout -> master
lineage, object geometry, media references, and the hard vertical alignment
invariant are present. Then review `distilled_spec.json`,
`template_language.md`, and `adaptation_strategy.json`. Confirm these fields
are accurate:

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
python scripts\body_variant_contract.py templates\layouts\my_template --json
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

8. Only after the faithful baseline is accepted, enforce the evidence-driven
   shell-profile policy:

- `cover`: opening identity and title lockup
- `toc`: agenda or roadmap
- `chapter`: section transition
- `content`: body material selected with `body_variants.json`
- `ending`: closing identity and acknowledgement lockup

The runtime template must expose the three required shells and only those
optional shells supported by source evidence. A source deck without a TOC must
not receive a synthesized TOC shell. Source pages beyond the active shell
profile remain in the reference evidence and `source_page_roster.json`; they
are not new public layout files.

Then choose an adaptation mode:

- `classic`: flexible visual style with reusable shells
- `mirror`: exact page replacement with fixed geometry
- `slot_guided_mirror`: an active 3-5 shell profile plus body-variant, density,
  and slot rules

Mirror modes remain source-scoped candidates. A main reusable template must
collapse the source roster into the active shell profile and semantic body
variants such as figure-left/right, comparison, process, and result. Bind
material by exact slot id, shell, and `content_shape`; never by source slide
index.

For composed variants, preserve the complete dependency chain in
`component_plan.json`: body variant asset, ordered `component_refs`, component
renderer, slot bindings, and the union of required QA gates. A required
component that is absent from both the global registry and the template's
`component_catalog.json` is a blocking contract failure.

9. For any fidelity claim, compare PowerPoint-rendered source PNGs against
PowerPoint-rendered generated PNGs. A native editable PPTX with a high visual
diff is a reconstruction draft, not a faithful template.

```powershell
python scripts\render_pptx_png.py source_template.pptx --out tmp\source_render_png --report tmp\source_render_png_report.json
python scripts\render_pptx_png.py tmp\my_template_review.pptx --out tmp\generated_render_png --report tmp\generated_render_png_report.json
python scripts\pptx_visual_diff.py tmp\source_render_png tmp\generated_render_png --out tmp\my_template_visual_diff
python scripts\visual_measure_gate.py --template-dir templates\layouts\my_template --pptx tmp\my_template_review.pptx --source-render-dir tmp\source_render_png --generated-render-dir tmp\generated_render_png --visual-diff-out tmp\my_template_visual_diff --report tmp\my_template_visual_measure_report.json
```

The Phase 5 promotion gate is the single decision point for a distilled
template. It keeps the projection, template geometry, native text layout,
render diff, and cross-material evidence together:

```powershell
python scripts\pptx_distill_promotion_gate.py templates\reference\template_asset_sources\my_template templates\layouts\my_template --pptx tmp\my_template_review.pptx --source-render-dir tmp\source_render_png --generated-render-dir tmp\generated_render_png --out tmp\my_template_promotion_gate --json
```

Read `tmp/my_template_promotion_gate/promotion_report.json`. `pass` means the
source-scoped candidate assets may be generated; it does not make the
source-order template production eligible. `review_required` means required
evidence or unresolved component decisions remain; `fail` means a blocking
contract or visual issue must be fixed first.

To materialize candidate assets after a passed report:

```powershell
python scripts/easyslides.py distill "path\to\source.pptx" --template-id my_template --promote-assets
```

Render and gate the semantic family separately:

```powershell
python scripts/easyslides.py semantic-render templates/layouts/my_semantic_template plans/deck_plan.json --out svg_output
python scripts/easyslides.py template-gate templates/layouts/my_semantic_template --pptx exports/review.pptx --report reports/production_gate.json --promote
```

## Guardrails

- Do not redesign during the first pass.
- Do not remove source cover or ending geometry until a reviewer approves it.
- Do not register the template from SVG previews alone; export and inspect the
  PPTX as well.
- Do not promote a draft when either SVG or exported-PPTX geometry QA fails.
- Do not call `_reusable` a production template merely because source text was
  removed.
- Do not keep source-specific images, logos, titles, tables, or data in a main
  reusable template.
- Do not register metadata-only component/symbol records as assets.
- Do not route material by DOM-order, source page number, or a fixed source
  slide count.
- Do not add a public layout for a source slide that differs only in content
  arrangement; add or refine a body variant instead.
- Keep the raw PPTX and imported assets in the reference folder, not in the
  runtime template contract.
