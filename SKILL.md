---
name: academic-pptx
description: >
  Generate and edit academic/research PPTX presentations with native editable DrawingML shapes.
  Integrates SVG-to-DrawingML pipeline, XML editing, and academic design templates.
  Use when user asks to "create academic PPT", "make presentation", "生成PPT", "做PPT",
  "制作演示文稿", "thesis defense", "学术报告", "开题报告", or mentions "pptx".
---

# Academic PPTX Skill

> Generate and edit academic/research PPTX presentations with native editable DrawingML shapes.

EasySlides is a **project-backed skill**. This file is the agent entrypoint and
task router; real deck generation depends on the full repository: `scripts/`,
`workflows/`, `templates/`, `references/`, tests, and local runtime
dependencies. Installing only `SKILL.md` is enough for routing guidance, but
not enough to generate or validate PPTX files.

Read `ARCHITECTURE.md` for the layer model and capability paths. Read
`INSTALL.md` for minimal skill, full local runtime, and developer installation
modes.

## Core Capabilities

1. **Create from scratch**: Source content → SVG pages → DrawingML shapes → editable PPTX
2. **Edit existing PPTX**: Unpack → edit XML → validate → repack
3. **HTML/JSX authoring path**: Use HTML/JSX as an experimental upstream authoring layer, then normalize into EasySlides-compatible SVG or shape IR before the existing DrawingML backend
4. **Academic scenario/template system**: Scenario-first academic planning with template-extensible output. The current active layout packs are `academic_general`, `academic_scqa`, `defense_leftnav`, `defense_topnav`, and `literature_minimal`; they are inventory, not scope limits.
5. **71 visualization templates**: Charts, infographics, diagrams, strategic frameworks, and tables
6. **11,634 icons**: Six SVG icon families for consistent academic and business visuals, with `lucide` preferred for new generic icons and emoji replacement
7. **Template Asset Bank**: Convert many real PPTX templates into exact-reuse slide modules for manual-template-substitution quality
8. **PPT Master Page Recipe Library**: whole-page SVG layout archetypes with fixed regions, text slots, diversity rules, and strict SVG slot measurement
9. **Card Component Library**: 13 fixed-size card styles plus PPT Master-style visual recipes with slot capacity contracts, agent selection rules, prompt skeletons, and PPTX preview export
9. **PPT Master compatibility mode**: Strict serial Strategist/Executor workflow, hand-written SVG pages, native DrawingML export, rebuildable backups, and gate checks via `scripts/ppt_master_pipeline.py`

## Backend-Centered Architecture

EasySlides has one production backend: normalized SVG/shape IR converted to
editable DrawingML/PPTX by the local `scripts/svg_to_pptx/` pipeline. Multiple
authoring frontends may feed that backend, but do not introduce a second
production PPTX backend unless a dedicated spike proves better editable output,
Office compatibility, and lower maintenance cost.

### Path A: Create from Scratch (SVG → DrawingML → PPTX)

When no template PPTX exists, use the SVG-to-DrawingML pipeline:

```
Source Content → Project Init → Strategist (Deck Plan + Design Spec) → SVG Generation → Quality Check → Export PPTX
```

**Key advantage**: Every SVG element becomes an editable DrawingML shape — text is selectable, colors are changeable, shapes are movable.

### Path B: Edit Existing PPTX (XML Unpack/Edit/Repack)

When a template PPTX exists:

```
Template PPTX → Unpack XML → Edit Content → Clean Orphans → Validate → Repack PPTX
```

**Key advantage**: Preserves all template formatting, animations, and layout structure.

### Path C: HTML/JSX Authoring (Experimental Upstream)

When the source is a rendered HTML page, dashboard, report, or SVG-heavy
technical slide, use HTML/JSX only as an authoring and measurement layer:

```
HTML/JSX source -> browser measurement / component declarations -> normalized SVG or shape IR -> EasySlides validation -> DrawingML export
```

**Key advantage**: HTML/JSX is easier for LLMs to author for complex layouts,
component reuse, dashboards, and architecture diagrams. The output still flows
through the EasySlides checker and DrawingML backend.

**Boundary**: `@artifact-kit/pptxgenjs-jsx` and `html-to-pptx-skill` may be used
as references or in isolated spikes, but they are not main-path dependencies of
EasySlides. Prefer integrating their DOM measurement and JSX authoring ideas
upstream of the existing SVG/DrawingML backend.

Use `workflows/html-jsx-authoring.md` when evaluating this path.

### Path D: PPT Master Compatibility Mode

When the user explicitly asks to reproduce PPT Master, use the PPT Master
workflow, or prioritize PPT Master-style SVG execution, follow
`workflows/ppt-master-compat.md`.

This mode keeps EasySlides' local converter stack but mirrors PPT Master's
operating contract:

```
Source -> project init -> Strategist design_spec/spec_lock -> optional images
-> Executor hand-writes SVG pages sequentially -> svg_quality_checker
-> validate_svg_text_slots -> notes/total.md -> ppt_master_pipeline export
-> editable PPTX
```

The Executor must write SVG pages directly into `svg_output/`; do not create a
batch script that generates all pages. Use `references/ppt-master-compat.md`
for execution rules, `templates/page_layouts/ppt-master-page-recipes-manual.md`
for whole-page layout selection, and `templates/cards/assembly-manual.md` for
nested card selection.

For a large library of PPTX templates, prefer the Template Asset Bank harness:

```
PPTX templates → pptx_template_import.py workspaces → template_asset_bank.json → exact slide-module reuse
```

Use `workflows/template-asset-bank.md` and `scripts/template_asset_bank.py` when
the goal is to mimic manual template substitution: fixed geometry, fixed
decorative structure, and only text/image/chart data replaced.

### Path E: Slide Image Reconstruction

When the source of truth is a slide screenshot, exported slide PNG, or AI mockup
image, use `workflows/slide-image-to-editable-pptx.md`. This is an upstream
analysis and QA contract for the existing EasySlides backend: first classify
every visible source-image element into Layer A visual assets, Layer B native
structure, or Layer C editable text; then assemble through SVG/shape IR and
DrawingML export.

This path explicitly forbids full-slide screenshot backgrounds, baked text in
image assets, and dirty rectangular crops. Validate the Phase 1 element
inventory with `scripts/slide_image_inventory.py`, then validate the final deck
with `scripts/validate_image_reconstruction_pptx.py` alongside the normal text
layout and render-diff gates.

Use `scripts/project_manager.py init <name> --kind slide_image_reconstruction`
and `scripts/image_reconstruction_pipeline.py init/qa` as the standard project
facade for this path. Default QA mode is `faithful-practical`: editable text,
native structure, and split-asset safety are blocking gates, while
source-vs-render pixel difference is measured and reported for inspection. Use
`--mode pixel-strict` only when near-pixel source matching is required. Complex
raster illustrations that become ugly as vectors should use
`preserve_source_frame`; closed/circular source assets should use masked source
assets with clipping checks.

---

## Academic Scenario-First Template Contract

Use **scenario first, template second** for academic work. In plain terms:
scenario first, template second. The academic scenario
defines the argument structure, evidence obligations, audience state, and page
roles; the template route defines visual containers, geometry, palette, chrome,
and reusable slide modules.

- A **template route is not a scenario**: template route is not a scenario. Do not infer "thesis defense" just
  because a defense-looking template is selected, and do not infer "literature
  report" just because a literature-style shell is available.
- The built-in scenario ids are **seed profiles** for routing, not a closed
  taxonomy. If the user's academic use case is not an exact match, select the
  nearest profile and record `scenario_variant` in `deck_plan.json` and
  `design_spec.md`.
- Preserve the selected profile's hard and required rules, then explicitly note
  which recommended or relaxable rules change for the `scenario_variant`.
- When no matching visual template exists, do not force a defense or literature-report template.
  Use free academic design, a general academic pack,
  a domain pack, or a user-provided template path while keeping source
  traceability, citation retention, text fit, and PPTX deliverability intact.
- When `academic_general` or `academic_scqa` is selected, read
  `references/academic-orchestration.md` and apply Audience-State-Transfer plus
  SCQA before selecting layouts. These templates are for audience-facing
  academic orchestration, not developer-facing production notes.

## Source Material Policy

Before planning or generating a deck, classify the user's input:

- **No supplied source materials**: if the user gives only a topic,
  requirements, or a request to research before making the PPT, run
  `workflows/topic-research.md`. You may gather web text and download relevant
  openly licensed images as PPT assets, then import the research document and
  image folder as source materials with provenance.
- **Provided mature source materials**: if the user supplies a journal paper,
  thesis/dissertation, mature report, existing deck, or similar file/URL with
  substantive text, figures, tables, or captions, treat that material as the
  source of truth. Build from its claims, structure, figures, tables, captions,
  and user-provided assets. Do not replace extracted figures, invent substitute
  evidence visuals, change the source claims, or add outside material unless
  the user explicitly asks; any added generic background/icon must remain
  decorative and never stand in for source evidence.

## Path A: Create from Scratch

### Step 1: Requirements & Project Init

```bash
python scripts/project_manager.py init <project_name> --format ppt169
python scripts/project_manager.py import-sources <path> <files...> --move
```

Supported source formats: PDF, DOCX, XLSX, PPTX, URL, Markdown.

**MinerU PDF Preprocessing**: When importing PDFs, the system automatically tries [MinerU](https://mineru.net) for structural extraction before falling back to PyMuPDF. MinerU provides richer output: Markdown with figure/table identification, layout JSON, and extracted images — enabling better PPTX generation with automatic figure extraction.

| Method | Token Required | Output | Limits |
|--------|---------------|--------|--------|
| Precision Extract API | Yes (`MINERU_API_TOKEN` env or `.mineru_token` file) | Markdown + JSON + images | ≤200 MB, ≤600 pages |
| Agent Lightweight API | No (IP-rate limited) | Markdown only | ≤10 MB, ≤20 pages |
| PyMuPDF fallback | No | Text + images (heuristic) | None |

To enable MinerU: set `MINERU_API_TOKEN` environment variable or create a `.mineru_token` file in the project root.

### Paper-Report Intake

For single-paper report decks, run the paper-report intake after importing
sources and before Strategist writes the final deck plan:

```bash
python scripts/paper_intake.py <project_path> --json
```

The intake reads `<project_path>/sources/`, Markdown converted from the PDF,
MinerU/PyMuPDF-side manifests when present, and `<project_path>/images/`. It
drafts `deck_plan.json` with a `source_map` for the main paper plus extracted
figures, then validates the draft with `scripts/deck_plan_contract.py`.
Strategist should treat the output as a traceable starting point: verify the
paper title, figure captions, claims, and slide roles before writing the final
`design_spec.md` and `spec_lock.md`.

### Single-Paper Literature-Report Flow Selection

Before deriving the outline for `single_paper_report`, read
`references/literature-report-flow-selection.md`.

If the user provides a page outline, speaking script, learning notes, or
slide-by-slide plan, that structure is the primary story contract. Preserve the
user's page order and speaking logic, then use the paper/SI to verify claims and
source figures. Do not replace the user's structure with an automatic long-form
literature-report flow unless the user explicitly asks for a rebuild.

If no outline or script is provided, choose or present two flow options:
- `paper_ppt_concise`: concise, figure-first 6-10 slide paper report inspired
  by `xiao634zhang/paper-ppt-skill`.
- `literature_report_deep_dive`: 20+ slide deep literature-report planning flow
  inspired by `fangyuanopus/literature-report-ppt-builder`, with
  `figure_source_manifest`, `deck_order_map`, and `page_briefs` before visual
  execution.

Both options still use EasySlides' editable SVG/shape-IR -> DrawingML backend as
the production path.

### Scenario Profiles and Rule Layers

Before the confirmation step for academic decks, load the scenario profile
catalog from `references/scenario_profiles.json`.

```bash
python scripts/scenario_profiles.py --list --json
python scripts/scenario_profiles.py --profile <profile_id> --json
```

Seed academic profiles are `single_paper_report`, `multi_paper_review`,
`thesis_defense`, `proposal_or_fund`, `lab_progress`, `workshop_training`, and
`conference_talk`. Pick the nearest profile from the source material, audience,
and occasion, then state it as a recommendation during confirmations. If the
deck is an academic scenario outside these seeds, keep the nearest profile as
the rule base and record a `scenario_variant` rather than squeezing the deck
into defense or literature-report wording.

Apply rule layers in this order:
- `hard_rules`: always enforce; source faithfulness, traceability, citations,
  text fit, template geometry integrity, and PPTX deliverability.
- `required_rules`: enforce for the selected scenario unless the user changes
  the scenario.
- `recommended_rules`: default guidance such as action titles or ghost-deck
  checks; apply when useful, but let templates and content needs override.
- `relaxable_rules`: soft defaults that can yield to venue, template, or
  teaching/activity format.

Templates control visual containers; scenario profiles control content
organization. Template colors, title treatment, page chrome, icon style, and
layout density may override profile recommendations only when allowed by
`template_may_override`; they must not override protected items in
`template_must_not_override`.

### Deck Plan Contract

After confirmations and before `spec_lock.md`, write `deck_plan.json` as the
page-level academic story contract:

```bash
python scripts/deck_plan_contract.py <project_path>/deck_plan.json --json
```

Each slide entry must include `page`, `role`, `action_title`, `claim`,
`evidence_sources`, `layout_id`, `rhythm`, and `speaker_note`. Use
`action_title` for the page's conclusion sentence, `claim` for the supported
statement, and `evidence_sources` for source-map references such as paper pages,
figure/table ids, extracted images, datasets, or user-provided assets. The
validated deck plan feeds `design_spec.md`, `spec_lock.md` `page_rhythm`, and
later QA gates.

After the deck plan passes, freeze the execution handoff as
`deck_execution_lock.json`:

```bash
python scripts/deck_execution_lock.py <project_path>/deck_plan.json --write <project_path>/deck_execution_lock.json --json
```

The execution lock records the per-page `layout_id`, `rhythm`, evidence refs,
body variant selection, declared slots, template palette, and required gates.
Executor must re-read `deck_execution_lock.json` together with `spec_lock.md`
before each page. If either file disagrees with the current deck plan, validate
with `scripts/deck_execution_lock.py --validate` and fix the plan before SVG
authoring.

When the selected template has `body_variants.json`, every executable content
slide must use a verified body variant in `layout_id`, provide `content_shape`,
and fill `slot_payload` with exactly the slots declared by that variant. The
`scripts/deck_plan_contract.py` report includes `body_variant_status` from
`scripts/body_variant_adapter.py`; `body_variant_contract`, `template_tokens`,
`text_capacity`, `svg_quality_checker`, `preview_render`, `pptx_roundtrip`, and
`visual_measure_gate`
are blocking gates before SVG authoring. Do not let Executor bypass this by
writing arbitrary SVG inside `CONTENT_AREA`.

When the selected template exposes a `LOGO` slot, resolve it from
user-provided assets and source-material image folders before SVG generation.
Prefer an actual institutional, laboratory, project, or paper-source logo. If
no suitable logo is available, keep the template's built-in degree-cap icon
fallback; when a real logo is inserted, replace the full `LOGO` group or hide
the fallback drawing.

### Academic QA Gate

Before SVG generation, run the Academic QA Gate on the finalized
`deck_plan.json`:

```bash
python scripts/academic_qa_gate.py <project_path>/deck_plan.json --json
```

The gate checks the deck-plan contract plus academic expression rules:
`action_title` must be a conclusion sentence rather than a topic label, result
pages need figure/table/data/chart evidence, source-linked decks should include
a References/source-provenance slide, and scenarios that recommend
`conclusion_last` should end on Conclusions rather than a generic thank-you
page. Errors block execution; warnings should be resolved or consciously
accepted before writing final SVGs.

For academic content, present the **Five Confirmations** (blocking):

| # | Confirmation | Default for Academic |
|---|-------------|---------------------|
| 1 | Canvas format | 16:9 (1280x720) |
| 2 | Page count | Based on source volume |
| 3 | Target audience | Committee / peers / general |
| 4 | Style objective | Mode B (data clarity) or C (logical persuasion) |
| 5 | Color scheme | Academic blue `#003366` + accent `#0066CC` |

After user confirms, output `deck_plan.json`, `deck_execution_lock.json`,
`design_spec.md`, and `spec_lock.md`.

### Step 2: Template and Design Foundation

Choose the design foundation from the confirmed scenario and template route:

- If the user provides an explicit template path, inspect that template and bind
  the story roles to its available shells or reusable modules.
- If the user asks to use an available EasySlides template, select the best
  matching active academic pack from `templates/layouts/`.
- If no matching template exists, create a free academic design or use a
  general/domain academic pack; do not force a defense or literature-report
  template onto unrelated academic scenarios.
- `academic_general` is the neutral general academic fallback when no domain or
  scenario-specific pack fits.
- `academic_scqa` is the structured academic/technical report variant when the
  material benefits from visible Audience-State-Transfer and SCQA progression.

The design spec must record the chosen `scenario_profile`, any
`scenario_variant`, the template route, and which template constraints may
override visual preferences. Use `templates/reference/design_spec_reference.md`
for the required 11-section structure, then pull the selected template's
`design_spec.md` only if that template is actually selected.

### Step 3: SVG Generation

Generate SVG pages sequentially (one at a time). In Path A, each page is
hand-written SVG. In Path C, generated SVG must be normalized to the same
contract before validation and export.

**Critical rules**:
- viewBox must match canvas (e.g., `0 0 1280 720`)
- Use `<rect>` for backgrounds, `<tspan>` for text wrapping
- Never use `rgba()`, `foreignObject`, `<mask>`, or `<script>`
- Reference icons via `<use data-icon="library/icon-name"/>` (see `templates/icons/README.md`); for new generic icons and emoji replacement, prefer `lucide/*` and color it with the deck theme color
- Reference charts from `templates/charts/` as SVG templates
- Re-read `deck_execution_lock.json` and `spec_lock.md` before every page to
  prevent layout, body-variant, palette, and gate drift

**SVG quality check**:
```bash
python scripts/svg_quality_checker.py <project_dir>
```

### Step 4: Post-processing & Export

```bash
# 1. Split speaker notes
python scripts/validate_svg_text_slots.py <project_dir>/svg_output --strict-unboxed --report <project_dir>/reports/svg_text_slot_report.json

# 2. Split speaker notes
python scripts/total_md_split.py <project_dir>

# 3. Finalize SVGs (embed icons, base64 images, flatten text)
python scripts/finalize_svg.py <project_dir>

# 4. Export to PPTX
python scripts/svg_to_pptx.py <project_dir>
```

Output: `exports/<project_name>.pptx` with native DrawingML shapes.

### Step 5: PPTX Package & Render QA

After every export, run package validation and rendered preview checks before
delivery:

```bash
python scripts/office/unpack.py <output.pptx> <tmp_unpacked>
python scripts/office/pack.py <tmp_unpacked> <tmp_roundtrip.pptx> --original <output.pptx> --validate true
python scripts/source_to_md/ppt_to_md.py <output.pptx> -o <project_dir>/reports/pptx_text_check.md
python scripts/render_pptx_png.py <output.pptx> --out <project_dir>/reports/rendered_png --report <project_dir>/reports/rendered_png_report.json
python scripts/visual_measure_gate.py --pptx <output.pptx> --report <project_dir>/reports/visual_measure_report.json
```

If speaker notes are enabled, package validation must prove that
`ppt/notesMasters/notesMaster1.xml` exists, the presentation has a notes master
relationship, and the deck has the expected `notesSlide*.xml` files. Missing
notes master relationships are blocking even if slide previews look fine.

`visual_measure_gate.py` is the blocking exit gate. It aggregates template slot
contracts, template geometry, PPTX text layout, and optional rendered-PNG diff
reports into `visual_measure_report.json`; it invokes
`scripts/validate_pptx_text_layout.py` and writes `text_layout_report.json` as
the PPTX text subreport. Repair any `SLOT-CONTRACT-*`, `TEXT-OVERFLOW`,
`TEXT-OVERLAP`, `TEXT-OFF-SLIDE`, `TEXT-FONT-TOO-SMALL`, protected-region
overlap, or visual diff threshold issue before delivery. Fix by shortening
copy, splitting slides, choosing a lower-density layout, preserving locked
template geometry, or rasterizing complex styling before shrinking body text.

Render the final PPTX itself, not just the source SVGs. Use LibreOffice/soffice
to export PDF and Poppler or PyMuPDF to render page PNGs; the wrapper is
`scripts/render_pptx_png.py`. If `soffice` or `pdftoppm` is missing from
`PATH`, locate the executable explicitly or use the PyMuPDF fallback; do not
skip visual QA. Inspect full-size previews for dense cards, process pages,
tables, references, and any text that was ported from a larger template.
Contact sheets are useful for rhythm only and can hide one-line overflow.

### Academic Page Layouts

When `academic_general` is selected as the neutral fallback, use these base layout
patterns:

| Layout | Use For | SVG Template |
|--------|---------|--------------|
| Cover | Title, author, institution | `01_cover.svg` |
| TOC | Outline with descriptions | `02_toc.svg` |
| Chapter | Section dividers (dark blue) | `02_chapter.svg` |
| Content | Main content pages | `03_content.svg` |
| Ending | Thank you / Q&A | `04_ending.svg` |

Content page sub-layouts:
- **Single column**: Centered text for key points
- **Two-column cards**: Side-by-side comparison
- **Left-right split** (5:5 or 4:6): Text + image
- **Card grid**: Multiple items in grid
- **Timeline**: Process flow or chronological data
- **Table**: Structured data comparison

### Academic Built-in Layout Library

Use `templates/layouts/` when the user explicitly asks to use a template path
or asks what academic templates are available. The directory contains 5 active
academic layout packs: `academic_general`, `academic_scqa`, `defense_leftnav`,
`defense_topnav`, and `literature_minimal`. Broader brand, government,
enterprise, domain-specific, and special-style PPT Master packs are not part of the active
library unless restored for a specific academic use case. This active inventory
does not define the full academic scope; new or external templates may be bound
to any academic `scenario_variant` if they preserve the hard rules.

Each classic pack contains `design_spec.md` and page shell SVGs such as
`01_cover.svg`, `02_toc.svg`, `02_chapter.svg`, `03_content.svg`, and
`04_ending.svg`. If a future active pack uses a slot-guided mode, it should
also carry `layouts.json`, `page_catalog.json`, `rules.md`,
`story_structure.json`, and generated contract sidecars.

Discovery:
- Human overview: `templates/layouts/README.md`
- Slim index: `templates/layouts/layouts_index.json`
- Root template references: `templates/reference/design_spec_reference.md` and
  `templates/reference/spec_lock_reference.md`

Do not fuzzy-match a bare template name when following PPT Master's stricter
template flow. Prefer an explicit directory path such as
`templates/layouts/academic_general/`.

### L001 Notebook Defense Style Pack

Use `templates/style_packs/l001_notebook_defense/` when the user asks for the L001
notebook-defense / burgundy defense style. This is a minimal style pack, not a
copy of the full EasyPPT asset registry.

Key files:
- `design_tokens.json`: locked wine-red palette, Microsoft YaHei typography,
  fixed closing title, and coordinate contracts.
- `layouts.json`: five lightweight page shells mapped to L001 source layouts.
- `01_cover.svg` to `05_closing.svg`: SVG templates for the EasySlides
  SVG-to-PPTX path.
- `scripts/styles/l001.py`: reusable SVG helper functions.

Validate after edits:

```bash
python scripts/validate_l001.py templates/style_packs/l001_notebook_defense
python scripts/svg_quality_checker.py templates/style_packs/l001_notebook_defense
```

### Guizang PPT Editable Style Pack

Use `templates/style_packs/guizang_ppt/` when the user asks for Guizang, electronic
magazine, electronic ink, or Swiss internationalism styles while still needing
editable PPTX output. This pack adapts
`https://github.com/op7418/guizang-ppt-skill` from HTML/CSS deck templates into
the EasySlides SVG-to-DrawingML path.

Key files:
- `design_tokens.json`: Style A's five ink/paper themes and Style B's four
  Swiss accent themes.
- `layouts.json`: Style A shell mapping plus the upstream Swiss `S01-S22`
  layout registry mapped into editable shell families.
- `style_a/01_cover.svg` to `style_a/04_closing.svg`: Style A native SVG shells.
- `style_b/01_cover.svg` to `style_b/05_closing.svg`: Style B native SVG shells.
- `swiss/S01_index_cover.svg` to `swiss/S22_image_hero.svg`:
  one native SVG skeleton for each upstream Swiss locked layout.
- `scripts/styles/guizang.py`: reusable SVG helper functions.
- `scripts/style_pack_contract.py`: validates `spec_lock.md` `style_pack`
  declarations and resolves Guizang `page_layouts` IDs to concrete SVG files.

When using Guizang as a harness, write `## style_pack` in `spec_lock.md` with
`package: guizang_ppt`, the locked `variant`, `theme`, `layout_source`, and
`validator`. Style B pages should prefer `S01`-`S22` layout IDs when the content
shape matches the upstream Swiss layout registry.

Validate after edits:

```bash
python scripts/style_pack_contract.py <project_path>/spec_lock.md --json
python scripts/validate_guizang.py templates/style_packs/guizang_ppt
python scripts/validate_guizang.py templates/style_packs/guizang_ppt --spec-lock <project_path>/spec_lock.md --json
python scripts/svg_quality_checker.py templates/style_packs/guizang_ppt
```

### Chart Integration

Reference chart SVGs from `templates/charts/`. The catalog contains 71
templates. Common academic charts:

| Chart Type | File | Use Case |
|-----------|------|----------|
| Bar chart | `bar_chart.svg` | Comparisons |
| Line chart | `line_chart.svg` | Trends over time |
| Scatter | `scatter_chart.svg` | Correlations |
| Box plot | `box_plot_chart.svg` | Data distribution |
| Radar | `radar_chart.svg` | Multi-dimensional comparison |
| Heatmap | `heatmap_chart.svg` | Matrix data |
| Fishbone | `fishbone_diagram.svg` | Root cause analysis |
| Timeline | `timeline.svg` | Process / milestones |

To use a chart: read the SVG template, replace placeholder data with actual data, and embed in the slide SVG.

### Card Component Library

### PPT Master Page Recipe Library

Use `templates/page_layouts/ppt_master_page_recipes.json` before selecting
cards whenever the deck follows the PPT Master-compatible route. Page recipes
are the main source of visual diversity: they define the whole-page archetype,
regions, slot capacity, and required text measurement contract.

Useful commands:

```bash
python scripts/page_recipe.py count
python scripts/page_recipe.py query --content-shape causal_chain --item-count 4
python scripts/page_recipe.py validate --recipe-id pm_causal_map --payload-file payload.json
python scripts/page_recipe.py prompt --recipe-id pm_causal_map
```

After SVG authoring, run `scripts/validate_svg_text_slots.py` before export.
Every meaningful text item longer than a tiny label should use
`data-pptx-textbox="true"` and `data-pptx-box-x/y/w/h` with explicit `<tspan>`
lines. If text does not fit, shorten, split, or choose a larger page recipe.

### Card Component Library

Use `templates/cards/card_library.json` when content should be assembled from
fixed-size cards instead of freeform text boxes. Read
`templates/cards/assembly-manual.md` before selecting cards. The library
currently contains 13 card styles covering metrics, parallel points,
comparisons, processes, evidence, method modules, literature notes, and
callouts.

For PPT Master-like cards, also read
`templates/cards/visual-recipes-manual.md` and query
`templates/cards/visual_recipes.json` through `scripts/card_recipe.py`. Visual
recipes define fixed geometry, slot capacity, layered SVG skeletons, and a
prompt contract the Executor can follow when hand-writing SVG pages.

Useful commands:

```bash
python scripts/card_library.py count
python scripts/card_library.py query --content-shape parallel_points --item-count 3
python scripts/card_library.py validate --card-id three_card_summary --payload-file payload.json
python scripts/card_library.py preview --output outputs/card_library_preview.pptx
python scripts/card_recipe.py count
python scripts/card_recipe.py query --content-shape sequence --item-count 3
python scripts/card_recipe.py validate --recipe-id pm_flow_strip --payload-file payload.json
python scripts/card_recipe.py prompt --recipe-id pm_flow_strip
```

Before rendering a card into PPTX, validate the payload. If a slot exceeds its
declared capacity, shorten, split, or choose another card/body variant; do not
expand the card or shrink text below the declared minimum.

---

## Path B: Edit Existing PPTX

### Step 1: Analyze Template

```bash
python scripts/thumbnail.py template.pptx
python -m markitdown template.pptx
```

Review `thumbnails.jpg` for layouts, markitdown output for placeholder text.

### Step 2: Plan Slide Mapping

For each content section, choose a template slide.

**Use varied layouts** — monotonous presentations are a common failure mode. Don't default to title + bullet slides. Actively seek out:
- Multi-column layouts (2-column, 3-column)
- Image + text combinations
- Full-bleed images with text overlay
- Quote or callout slides
- Section dividers
- Stat/number callouts

### Step 3: Unpack

```bash
python scripts/office/unpack.py template.pptx unpacked/
```

Extracts PPTX, pretty-prints XML, escapes smart quotes.

### Step 4: Structural Changes (do sequentially, not with subagents)

- Delete unwanted slides: remove from `<p:sldIdLst>` in `ppt/presentation.xml`
- Duplicate slides: `python scripts/add_slide.py unpacked/ slide2.xml`
- Reorder: rearrange `<p:sldId>` elements
- **Complete all structural changes before editing content**

### Step 5: Edit Content (parallelizable with subagents)

Each slide is a separate XML file (`ppt/slides/slide{N}.xml`). Use subagents for parallel editing.

**Use the Edit tool, not sed or Python scripts.**

Formatting rules:
- Bold headers: `b="1"` on `<a:rPr>`
- Never use unicode bullets — use `<a:buChar>` or `<a:buAutoNum>`
- Multi-item content: separate `<a:p>` elements, never concatenate

### Step 6: Clean & Validate

```bash
python scripts/clean.py unpacked/
python scripts/office/pack.py unpacked/ output.pptx --original template.pptx
```

---

## Design Quality Standards (from guizang-ppt-skill)

### Layout Rhythm

- Alternate light/dark/hero pages — no 3+ consecutive same-theme pages
- Use varied layouts across the deck
- Maintain consistent spacing (card gap 20px, content block gap 24px)

### Typography Hierarchy

| Level | Size (1280x720) | Weight | Use |
|-------|----------------|--------|-----|
| H1 | 56px | Bold | Cover title |
| H2 | 36px | Bold | Section headers |
| H3 | 28px | Bold | Subsection headers |
| Body | 20px | Regular | Main content |
| Caption | 16px | Regular | Labels, annotations |
| Footnote | 12px | Regular | Page numbers, sources |

### Color Usage (60-30-10 Rule)

- **60%**: Neutral backgrounds (`#FFFFFF`, `#F5F7FA`)
- **30%**: Primary color (`#003366`)
- **10%**: Accent color (`#0066CC`, `#CC0000` for emphasis)

### Icon Discipline

- Use one stylistic icon library per deck; prefer `lucide` for new generic
  icons and emoji replacement, with `fill` set to the deck theme color.
  `simple-icons` is only for brand marks.
- Reference via `<use data-icon="library/icon-name"/>`
- Icons are embedded during finalization — never use emoji

---

## Common Pitfalls

### SVG Generation

1. **Wrong viewBox**: Must match canvas dimensions exactly
2. **Missing `spec_lock` re-read**: Re-read before every page
3. **Script-generated SVG**: Forbidden — each page must be hand-written
4. **Using `rgba()`**: Use hex colors with opacity attributes instead
5. **SVG `<text>` labels**: Use HTML labels, not SVG text in diagrams
6. **Template porting overflow**: Compact templates such as `defense_leftnav` cannot
   safely reuse long card/process copy from larger templates. Shorten at the
   source content layer and use punctuation-aware Chinese wrapping before
   export.

### PPTX Editing

1. **Unicode bullets**: Never use `•` — causes double bullets
2. **Smart quotes**: Use XML entities (`&#x201C;` etc.) in new text
3. **Missing `clean.py`**: Always run after structural changes
4. **Manual slide copy**: Use `add_slide.py` — manual copy misses bookkeeping
5. **ElementTree**: Use `defusedxml.minidom` — ElementTree corrupts namespaces
6. **Unvalidated speaker notes**: Notes slides require a notes master part,
   relationships, and content types. Always run the unpack/pack validation and
   a PPT-to-Markdown extraction check after exporting a deck with notes.

### Design

1. **Monotonous layouts**: Vary layout types across the deck
2. **Inconsistent spacing**: Use the template's spacing system
3. **Mixed icon styles**: Stick to one library per deck
4. **No visual rhythm**: Alternate between light, dark, and hero pages

---

## File Structure

```
<repo>/
├── SKILL.md                          # This file
├── references/
│   ├── workflow-create.md            # Path A detailed workflow
│   ├── workflow-edit.md              # Path B detailed workflow
│   ├── design-guidelines.md          # Academic design standards
│   └── svg-rules.md                  # SVG authoring constraints
├── templates/
│   ├── academic/                     # Academic defense template
│   │   ├── design_spec.md            # Design specification
│   │   ├── 01_cover.svg              # Cover page
│   │   ├── 02_toc.svg                # Table of contents
│   │   ├── 02_chapter.svg            # Chapter divider
│   │   ├── 03_content.svg            # Content page
│   │   └── 04_ending.svg             # Ending page
│   ├── layouts/                      # 7 active academic layout template packs
│   ├── charts/                       # 71 visualization SVG templates
│   └── icons/                        # 11,634 icons across six libraries
│       ├── chunk-filled/
│       ├── phosphor-duotone/
│       ├── simple-icons/
│       ├── tabler-filled/
│       └── tabler-outline/
└── scripts/
    ├── template_asset_bank.py         # Build exact-reuse PPTX template module banks
    ├── svg_to_pptx/                  # SVG → DrawingML converter
    │   ├── __init__.py
    │   ├── drawingml_converter.py    # Main dispatcher
    │   ├── drawingml_elements.py     # Element converters
    │   ├── drawingml_paths.py        # Path parser
    │   ├── drawingml_styles.py       # Style converters
    │   ├── drawingml_utils.py        # Utilities
    │   ├── pptx_builder.py           # PPTX assembly
    │   └── pptx_slide_xml.py         # Slide XML generation
    ├── office/                       # PPTX editing tools
    │   ├── unpack.py                 # Extract & pretty-print
    │   ├── pack.py                   # Validate & repack
    │   ├── helpers/                  # Run merging, redline simplification
    │   ├── validators/               # XSD schema validation
    │   └── schemas/                  # OOXML XSD schemas
    ├── add_slide.py                  # Add/duplicate slides
    ├── clean.py                      # Remove orphaned resources
    ├── finalize_svg.py               # SVG post-processing
    ├── svg_quality_checker.py        # SVG quality validation
    ├── config.py                     # Configuration
    ├── project_manager.py            # Project management
    └── svg_to_pptx.py                # CLI wrapper
```

## Dependencies

```bash
pip install python-pptx>=0.6.21 defusedxml lxml Pillow
```

Optional (for source conversion):
```bash
pip install pymupdf markitdown pandoc
```
