---
name: easyslides-distill
description: >
  Distill a source PPTX with EasySlides into factual source evidence, a
  content-free semantic layout family, and real reusable component and symbol
  assets. Use for EasySlides/PPTX template distillation, style extraction,
  reusable-template creation, fixed-chrome versus material-slot analysis, or
  Chinese requests such as 蒸馏PPT、提取无内容模板、拆分组件资产和符号资产。
  Promotion is fail-closed: source-order mirrors and metadata-only fragments
  remain review candidates until native PPTX and visual gates pass.
---

# EasySlides PPTX Distill

This Skill is the plugin-local entry point for turning a source PowerPoint into
an inspectable, reusable EasySlides template. It is a staged operation:

1. **Graph** the native OOXML source into factual parts, relationships,
   objects, geometry, text, and assets.
2. **Distill** that evidence into identity, geometry, primitives, slots,
   patterns, and risks.
3. **Generalize** the accepted identity into semantic layout families,
   capacity-bounded named slots, and renderable component/symbol assets.

The canonical production surface is deliberately small and evidence-driven:
**three to five stable page shells**. `cover`, `content`, and `ending` are
required; `toc` and `chapter` are optional and are materialized only when the
source deck provides evidence for them. Source pages are evidence, not runtime
layouts. Repeated content forms are grouped into `body_variants.json`; repeated
visual primitives become component or symbol assets. A distillation that exposes
one public SVG per source slide fails this policy unless it is explicitly marked
as a source-evidence or mirror candidate.

The first pass must preserve the source identity. It is not a redesign pass and
it is not a one-off PPTX fill operation. A completed distillation has three
deliberately separate layers: source evidence, a source-faithful review
candidate, and a content-free semantic production family. A mechanical copy
of the source slide roster is never the production template.

The reusable layer must not retain source-specific titles, body copy, data,
photos, or logos in replaceable slots. Fixed chrome remains protected.

## When to Use

Use this Skill when the request contains any of these intents:

- make this PPT/PPTX into an EasySlides template;
- extract the visual language or component assets from a PPTX;
- create a mirror or slot-guided mirror template;
- preserve the source page structure while replacing material;
- explain which parts of a source deck are fixed chrome and which are content
  slots;
- verify that a distilled template can accept a second, unrelated material set.

Use the regular `easyslides` route instead when the user wants a new story,
allows page count or order to change, or only wants a one-off native PPTX fill.

## Required Repository Reading

From the repository root, read these files before running the workflow:

1. `SKILL.md`
2. `ARCHITECTURE.md`
3. `workflows/routing.md`
4. `workflows/pptx-to-easyslides-template.md`
5. the repository PPTX workflow or the installed `pptx` skill
6. `workflows/create-template.md`
7. `workflows/template-asset-bank.md`
8. `references/template-designer.md`

The repository files are authoritative for commands and current output names.
Do not create a second export backend or silently bypass the existing SVG,
shape IR, DrawingML, and native PPTX paths.

## Distillation Model

Every source deck must be described with the following machine-readable ideas.
They may be represented in `distilled_spec.json`, `template_language.md`, and
the generated contract sidecars:

- `identity_must_preserve`: palette, typography, page ratio, chrome, recurring
  labels, visual rhythm, cover/ending treatment, and other source identity;
- `structural_primitives`: rails, headers, title bars, section numerals,
  dividers, cards, axes, chart frames, image masks, markers, and footer rules;
- `slot_candidates`: title, subtitle, body, list, table, chart, image, label,
  caption, quote, page marker, and other material-bearing slots;
- `adaptable_patterns`: page roles and repeatable compositions that may accept
  new material;
- `forbidden_drift`: changes that would make a claimed source-faithful
  template visibly become a different design;
- `template_language`: concise natural-language rules for future generation;
- `adaptation_strategy`: classic, mirror, or slot-guided mirror behavior,
  including density and overflow policy;
- `source_geometry_risks`: authored oddities, placeholder artifacts, clipping,
  unsupported effects, rotation, crop, opacity, and other risks that must not
  be mistaken for freeform slots.

Rendered source pages are the visual truth. Prose summaries and object-level
metadata are evidence, not a replacement for rendered inspection.

## Workflow

### 1. Establish the source workspace

Use the canonical plugin command from the repository root. It creates evidence
and the faithful review draft; it does not promote assets by default:

```powershell
python scripts/easyslides.py distill "path\to\source.pptx" --template-id my_template
```

The hub delegates this route to `scripts/pptx_template_distill.py`; use the hub
so plugin discovery and CLI help stay aligned.

When a reference workspace already exists, use the command's documented
`--from-existing-source` form instead of importing the source twice. Keep the
raw source and imported assets under:

```text
templates/reference/template_asset_sources/<template_id>/
```

The source workspace should contain `manifest.json`, `source_graph.json`,
`distill_manifest.json`, rendered or extracted assets, SVG evidence, and a
contact sheet whenever the command supports them.

For a source graph without the full template build, use:

```powershell
python scripts/pptx_source_graph.py "path\to\source.pptx" --output tmp\source_graph.json
```

The graph is factual. It intentionally leaves object classification as
`unknown`; semantic component registration belongs to the next phase.

### 2. Read the evidence before generalizing

Inspect the generated contact sheet and the source render evidence. Then read:

- `distilled_spec.json`
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
- `template_language.md`
- `adaptation_strategy.json`
- `source_geometry_risks.json`
- `editable_rebuild_plan.json`

Confirm which elements are fixed chrome and which are material slots. Preserve
rotated side labels, decorative words, `CONTENTS` or equivalent section labels,
section numerals, page markers, cover geometry, and ending geometry unless the
user explicitly asks to replace them.

### 3. Build the evidence-driven shell profile

The runtime template lives under:

```text
templates/layouts/<template_id>/
```

It must contain the three required shell SVGs plus optional `toc` and `chapter`
shell SVGs when the source evidence supports them, plus:

- `design_spec.md`
- `layouts.json`
- `page_catalog.json`
- `story_structure.json`
- `rules.md`
- `body_variants.json`
- `source_page_roster.json`
- contract sidecars generated by `scripts/template_contract_pack.py`

Use the existing repository command to create or refresh the draft. The command
must select one source exemplar for each active shell, preserve all source pages
in the reference workspace, and group content pages by visual form and density.
Do not synthesize a missing TOC or chapter page, and do not add a new public
page because a source slide has a different title or evidence arrangement.

The generated `layouts.json` must declare:

```json
{
  "global_contract": {
    "canonical_shell_policy": "evidence_driven_three_to_five_stable_shells",
    "canonical_shell_minimum": 3,
    "canonical_shell_limit": 5,
    "required_shell_roles": ["cover", "content", "ending"],
    "optional_shell_roles": ["toc", "chapter"],
    "active_shell_roles": ["cover", "content", "ending"]
  },
  "body_variants": "body_variants.json",
  "source_page_roster": "source_page_roster.json"
}
```

The contract pack rejects missing required shells, more than five public pages,
unsupported optional shells, or missing source roster/variant sidecars.

Each body variant must also declare how it uses reusable components. New output
uses ordered `component_refs` objects with stable `asset_id`, unique
`instance_id`, semantic `role`, contiguous `order`, `required`, and
`slot_bindings`. Bare component names in the legacy `components` field remain
readable, but new distillation output must not write them. A variant with no
component dependencies writes `component_refs: []` and an explicit open
composition mode.

Validate this relationship independently:

```powershell
python scripts/body_variant_contract.py templates/layouts/my_template --json
```

### 4. Build the source-scoped review candidate and asset evidence

First run the complete distillation promotion gate. Only when its
`promotion_report.json` has `status=pass` and `promotable=true` may the
source-scoped candidate be materialized:

```powershell
python scripts/easyslides.py distill "path\to\source.pptx" --template-id my_template --promote-assets
```

It produces:

```text
templates/layouts/<template_id>/                 # evidence-driven 3-5-shell runtime layer
templates/layouts/<template_id>_reusable/        # source-scoped review candidate
templates/components/source_templates/<id>_kit/  # source-scoped asset evidence
templates/reference/template_asset_sources/<id>/ # evidence and contracts
```

The asset kit includes `component_asset_manifest.json` for repeated visual
components and `symbol_asset_manifest.json` for repeated shapes, connectors,
groups, and other symbol-like primitives. Only assets with an actual
renderable SVG fragment belong in component/symbol manifests. Unknown,
metadata-only, or one-off objects remain in `review_queue.json` and are not
silently promoted.

The default command is equivalent to the former no-promotion mode. The
compatibility flag remains accepted:

```powershell
python scripts/easyslides.py distill "path\to\source.pptx" --template-id my_template --no-promote-assets
```

The source-scoped candidate is never automatically registered as a main
template. It must remain evidence or be generalized into the same
evidence-driven shell family with
`layouts.json`, `body_variants.json`, named `data-slot` bindings, explicit
capacities, and a fail-closed `template_status.json`. Render material through:

```powershell
python scripts/easyslides.py semantic-render templates/layouts/my_semantic_template plans/deck_plan.json --out svg_output
python scripts/easyslides.py template-gate templates/layouts/my_semantic_template --pptx exports/review.pptx --report reports/production_gate.json
```

Production rendering must bind exact slot names. DOM-order text replacement,
source page numbers, and a fixed source slide count are forbidden routing
signals.

### 5. Apply the editable geometry contract

For every editable text box, preserve the source geometry in the SVG or IR:

- `data-pptx-textbox="true"`
- `data-pptx-box-x`
- `data-pptx-box-y`
- `data-pptx-box-w`
- `data-pptx-box-h`
- `data-pptx-valign`

Text inside a compact control is a shape-plus-text unit. Single-line control
text is vertically middle-aligned. Multiline labels are centered as a group
when the source design centers the control as a whole. A text box must not be
visually top-heavy inside its rectangle: its text center must align with the
container's vertical center, subject to the source's explicit baseline or
optical adjustment.

Preserve parent transforms, direction, rotation, crop, opacity, gradients,
shadows, and layer order. If an SVG transform produces negative extents, emit
legal positive PPTX extents plus the corresponding `flipH` or `flipV`; never
write invalid negative PPTX dimensions.

### 6. Separate fixed chrome from material

Treat fixed chrome as protected geometry. Treat candidate slots as constrained
material inputs with role, density, maximum lines, and overflow policy.

Do not promote these to slots merely because they contain text or images:

- source-authored garbled or placeholder-like text;
- decorative words and section labels;
- navigation rails and page markers;
- cover and ending marks;
- geometry whose placement depends on a source-specific crop or transform.

The graph and derived contracts must retain this hard geometry invariant:

```text
eligible_text_center_y == container_center_y
```

Optical or baseline exceptions must be explicit in a later slot contract with
a reason and adjustment. They are never implicit permission to leave text
top-aligned inside a centered container.

For tight list or table slots, adapt content to the declared capacity and reject
visible ellipses or accidental clipping. If a slot cannot accept the material,
change the page pattern or report the overflow rather than silently shrinking
everything.

### 7. Project Declared Slots

Build the renderer mapping after the semantic contracts exist:

```powershell
python scripts/pptx_projection.py build templates/reference/template_asset_sources/my_template --template-id my_template
```

The `source_template_projection` renderer targets SVG and replaces only
declared slots. Convert the projected SVG through the existing
`scripts/svg_to_pptx.py` path when a native PPTX is required. A missing slot
element is a blocking projection failure; do not fall back to arbitrary text
insertion.

## Acceptance Gates

Before visual promotion, run the shell-shape gate:

```powershell
python scripts/template_contract_pack.py templates/layouts/my_template --check
```

For a production distillation, this must report 3-5 public layouts, with
`cover`, `content`, and `ending` required. `toc` and `chapter` may appear only
when supported by source evidence. The source page count may be larger, but it
must appear only in `source_page_roster.json`; extra forms must be represented
by `body_variants.json` or asset manifests.

Run the focused checks from the repository root. Use the exact current command
help if an option has changed:

```powershell
python scripts/template_contract_pack.py templates/layouts/my_template --check
python scripts/svg_quality_checker.py templates/layouts/my_template
python scripts/template_geometry_qa.py templates/layouts/my_template --report tmp/my_template_geometry_svg.json --json
python scripts/svg_to_pptx.py templates/layouts/my_template --only native -t none -a none -o tmp/my_template_review.pptx
python scripts/validate_pptx_text_layout.py tmp/my_template_review.pptx --report tmp/my_template_text_layout_report.json
python scripts/template_geometry_qa.py templates/layouts/my_template --pptx tmp/my_template_review.pptx --report tmp/my_template_geometry_pptx.json --json
python scripts/visual_measure_gate.py --template-dir templates/layouts/my_template --pptx tmp/my_template_review.pptx --report tmp/my_template_visual_measure_report.json
```

For the complete Phase 5 promotion decision, run the orchestration gate from
the reference workspace and runtime template directory:

```powershell
python scripts/pptx_distill_promotion_gate.py templates/reference/template_asset_sources/my_template templates/layouts/my_template --pptx tmp/my_template_review.pptx --source-render-dir tmp/source_render_png --generated-render-dir tmp/generated_render_png --out tmp/my_template_promotion_gate --json
```

It writes `promotion_report.json` plus the focused child reports. A missing
PPTX, render diff, or cross-material run is `review_required`; it is never
treated as promotion success. The report is promotable only when every gate
passes.

For a reusable template, run the cross-material smoke test with a different
material set:

```powershell
python scripts/template_material_smoke_test.py templates/layouts/my_template --out tmp/my_template_material_smoke --force --forbidden-keyword SOURCE_SPECIFIC_TERM
python scripts/svg_quality_checker.py tmp/my_template_material_smoke
python scripts/template_geometry_qa.py tmp/my_template_material_smoke --report tmp/my_template_material_smoke_geometry_svg.json --json
python scripts/svg_to_pptx.py tmp/my_template_material_smoke --only native -t none -a none -o tmp/my_template_material_smoke.pptx
python scripts/validate_pptx_text_layout.py tmp/my_template_material_smoke.pptx --report tmp/my_template_material_smoke_text_layout.json
```

If PowerPoint or LibreOffice is available, render both source and generated
PPTX files and compare their PNGs:

```powershell
python scripts/render_pptx_png.py source_template.pptx --out tmp/source_render_png --report tmp/source_render_png_report.json
python scripts/render_pptx_png.py tmp/my_template_review.pptx --out tmp/generated_render_png --report tmp/generated_render_png_report.json
python scripts/pptx_visual_diff.py tmp/source_render_png tmp/generated_render_png --out tmp/my_template_visual_diff
```

The following are blocking failures:

- `CONTROL-TEXT-VERTICAL-MISALIGN`
- `PPTX-CONTROL-TEXT-VERTICAL-MISALIGN`
- `PPTX-TEXT-CONTAINER-OVERFLOW`
- `PPTX-INVALID-NEGATIVE-EXTENT`
- `ellipsized_material_text`
- failed SVG or exported-PPTX geometry QA

The acceptance claim has two parts:

1. **Faithful reconstruction:** the generated draft preserves colors,
   transparency, crop, rotation, alignment, layer order, and non-overlap
   against source-rendered evidence.
2. **Cross-material reuse:** a second topic can replace material while fixed
   chrome, page roles, cover/ending identity, and declared geometry remain
   intact.

For a semantic production family, add the final gate:

```powershell
python scripts/easyslides.py template-gate templates/layouts/my_semantic_template --pptx tmp/my_semantic_template_review.pptx --report tmp/my_semantic_template_production_gate.json --promote
```

Do not use `--promote` until the contact sheet has been visually reviewed and
the review decision is recorded. `review_required` is not success.

## Handoff Format

Report the result in Chinese and include:

- source PPTX path and slide count;
- `template_id`;
- reference and runtime template folders;
- identity traits that are preserved;
- template language and fidelity risks;
- adaptation mode and overflow policy;
- source geometry risks;
- page roles and slot inventory;
- SVG, PPTX, text-layout, material-smoke, and render-diff status;
- warnings and the next action.

Never claim that a source deck has been distilled solely because a PPTX file was
copied or its colors were patched. Distillation is complete only when the
source evidence, reusable language, slot contract, geometry QA, and handoff
are all present.
