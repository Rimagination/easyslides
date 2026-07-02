# Workflow: Create PPTX from Scratch (SVG → DrawingML)

## Pipeline Overview

```
Source Content → Project Init → Strategist → SVG Generation → Quality Check → Export
```

## Step 1: Source Content Processing

Supported formats: PDF, DOCX, XLSX, PPTX, URL, Markdown.

```bash
python scripts/project_manager.py init <name> --format ppt169
python scripts/project_manager.py import-sources <path> <files...> --move
```

Follow SKILL.md **Source Material Policy** before acquisition. If no source
document exists, run the topic-research workflow to gather web text and images
first. If mature source materials exist, import and preserve them as the source
of truth instead of replacing their figures, tables, claims, or structure with
external research.

### Paper-report intake

For a single-paper PDF workflow, build the first traceable deck plan from the
imported project artifacts:

```bash
python scripts/paper_intake.py <project_dir> --json
```

The paper-report intake consumes `<project_dir>/sources/`, converted Markdown,
MinerU/PyMuPDF manifests when available, and `<project_dir>/images/`. It writes
`deck_plan.json`, declares a `source_map` for the main paper and extracted
figures, and immediately validates the result through
`scripts/deck_plan_contract.py`. Treat this as an intake draft: Strategist must
still verify the title, figure captions, claims, and per-page action titles.

### Literature-report flow selection

For `single_paper_report`, read
`references/literature-report-flow-selection.md` before recommending a page
count or story spine.

Input priority:
- If the user supplied an outline, script, speaking notes, or slide-by-slide
  plan, preserve that structure as the primary story contract. Use the paper and
  SI as evidence sources, not as permission to replace the user's order.
- If no outline/script exists, offer or choose between `paper_ppt_concise`
  (short 6-10 slide, figure-first report inspired by
  `xiao634zhang/paper-ppt-skill`) and `literature_report_deep_dive` (20+ slide
  long-form literature-report planning inspired by
  `fangyuanopus/literature-report-ppt-builder`).
- For `literature_report_deep_dive`, maintain `figure_source_manifest`,
  `deck_order_map`, and `page_briefs` before SVG generation.

## Step 2: Strategist Phase (BLOCKING)

### Scenario profile preflight

Load the Scenario profile catalog before presenting confirmations:

```bash
python scripts/scenario_profiles.py --list --json
python scripts/scenario_profiles.py --profile <profile_id> --json
```

Choose the nearest academic profile from source type, audience, and occasion:
`single_paper_report`, `multi_paper_review`, `thesis_defense`,
`proposal_or_fund`, `lab_progress`, `workshop_training`, or
`conference_talk`. Use the selected profile's `structure_strength`,
`typical_slide_count`, and `default_story_spine` to shape the page-count
recommendation and outline.

These are seed profiles, not a closed taxonomy. If the user is preparing a
different academic genre, use the nearest profile as the rule base and record a
`scenario_variant` in `deck_plan.json` and `design_spec.md`. Do not force a
defense or literature-report frame when the occasion is a seminar, training,
project review, invited lecture, teaching exchange, or another scholarly
setting.

Use the selected profile's rule layers as follows:
- Global hard rules always apply.
- Profile `required_rules` are scenario obligations.
- Profile `recommended_rules` are defaults, not template-breaking commands.
- Profile `relaxable_rules` can be softened for workshops, venue constraints,
  or template-specific composition.

Respect the template boundary recorded in the profile: visual choices listed in
`template_may_override` can follow the loaded template or user preference, while
items listed in `template_must_not_override` remain protected.

Use scenario first, template second: the scenario controls content organization
and evidence obligations; the template controls visual containers. A template
route is not a scenario.

If the selected route is `academic_general` or `academic_scqa`, read
`references/academic-orchestration.md` and capture the Audience-State-Transfer
contract before writing the outline. Use SCQA as a default academic spine while
keeping source-faithful materials intact.

Present the **Five Confirmations** to the user:

1. **Canvas format**: Recommend based on scenario (default: 16:9 1280x720 for academic)
2. **Page count**: Based on source document volume
3. **Target audience**: Committee / peers / general public / students
4. **Style objective**: Communication mode (B: data clarity, C: logical persuasion)
5. **Color scheme**: Academic blue default, or user/template preference

After user confirms, output:
- `deck_plan.json` — page-level story contract with `action_title`, `claim`,
  `evidence_sources`, `layout_id`, `rhythm`, and `speaker_note`
- `deck_execution_lock.json` — compact execution lock generated from the
  validated deck plan, body variant contracts, and template tokens
- `design_spec.md` — full design specification (11 sections)
- `spec_lock.md` — machine-readable companion with data lines only

Validate the deck plan before writing `spec_lock.md`:

```bash
python scripts/deck_plan_contract.py <project_dir>/deck_plan.json --json
```

Then write the execution lock:

```bash
python scripts/deck_execution_lock.py <project_dir>/deck_plan.json --write <project_dir>/deck_execution_lock.json --json
```

`deck_plan.json` is the bridge from academic reasoning to visual execution.
Every page should carry a conclusion-style `action_title`, a concise `claim`,
traceable `evidence_sources` pointing into `source_map`, the chosen `layout_id`,
the page `rhythm`, and the `speaker_note` intent. `design_spec.md` may explain
the deck in prose, but the page contract belongs here so QA can check it later.

If the selected template provides `body_variants.json`, `layout_id` must point
to a verified body variant or carry enough `content_shape` for
`scripts/body_variant_adapter.py` to select one. Each checked slide must include
`slot_payload` keyed exactly by that variant's declared slots. Treat
`body_variant_contract`, `template_tokens`, `text_capacity`,
`svg_quality_checker`, `preview_render`, `pptx_roundtrip`, and
`validate_pptx_text_layout` as required gates; a failing `body_variant_status`
means the plan is not ready for SVG generation and arbitrary SVG inside
`CONTENT_AREA` is not allowed.

`deck_execution_lock.json` is the Executor's drift guard. Re-read it before
every page with `spec_lock.md`; if `layout_id`, `rhythm`, body variant id,
declared slots, or required gates no longer match the deck plan, stop and run:

```bash
python scripts/deck_execution_lock.py <project_dir>/deck_plan.json --validate <project_dir>/deck_execution_lock.json --json
```

Run the Academic QA Gate after the deck plan is final enough to execute:

```bash
python scripts/academic_qa_gate.py <project_dir>/deck_plan.json --json
```

The gate checks action-title quality, result-page evidence type, References /
source-provenance planning, and whether applicable academic scenarios end on
Conclusions. Fix errors before SVG generation; review warnings explicitly.

## Step 3: Design Specification Structure

The design spec has 11 sections:

1. **Project Info**: Name, audience, occasion, core message
2. **Canvas**: Dimensions, margins, safe area
3. **Visual Theme**: Primary/secondary/accent colors, functional colors
4. **Typography**: Font families, size hierarchy
5. **Layout**: Page structure, content area, spacing system
6. **Icon**: Library choice, usage rules
7. **Visualization**: Chart types, color coding
8. **Image**: Approach (AI-generated, web search, user-provided)
9. **Outline**: Page-by-page content plan
10. **Speaker Notes**: Style and depth
11. **Tech Constraints**: SVG rules, compatibility requirements

## Step 4: SVG Generation

Generate SVG pages sequentially. Each page must be hand-written.

### Rules

- Re-read `deck_execution_lock.json` and `spec_lock.md` before EVERY page
- viewBox must match canvas (e.g., `0 0 1280 720`)
- Use `<rect>` for backgrounds
- Use `<tspan>` for text wrapping
- Never use: `rgba()`, `foreignObject`, `<mask>`, `<script>`
- Reference icons: `<use data-icon="tabler-filled/icon-name"/>`
- Reference charts: read from `templates/charts/` and adapt data

### Academic Page Types

**Cover page** (`01_cover.svg` template):
- Title, subtitle, author, advisor, institution, date
- Logo placeholder

**TOC page** (`02_toc.svg` template):
- 3-5 items with title + description
- Section numbers

**Chapter divider** (`02_chapter.svg` template):
- Dark blue full-screen background
- Chapter number, title, description

**Content page** (`03_content.svg` template):
- Header + key message bar
- Content area with various layouts
- Footer with page number

**Ending page** (`04_ending.svg` template):
- Thank you message
- Contact info, email, copyright

### Speaker Notes

Generate notes in `notes/total.md`, one section per slide.

## Step 5: Quality Check

```bash
python scripts/svg_quality_checker.py <project_dir>
```

Must pass with 0 errors before proceeding.

## Step 6: Post-processing & Export

```bash
# 1. Split speaker notes into per-slide files
python scripts/total_md_split.py <project_dir>

# 2. Finalize SVGs
python scripts/finalize_svg.py <project_dir>
# - Embeds icon SVG paths (replaces <use data-icon="...">)
# - Base64-embeds images
# - Flattens <tspan> elements
# - Converts rounded rects to paths

# 3. Export to PPTX
python scripts/svg_to_pptx.py <project_dir>
```

Output: `exports/<name>_<timestamp>.pptx`

The PPTX contains native DrawingML shapes:
- Text is selectable and editable
- Colors are changeable
- Shapes are movable and resizable
- Compatible with PowerPoint, LibreOffice, Google Slides

## Step 7: Final PPTX QA

The final gate is the exported PPTX package and its rendered pages, not the SVG
source alone.

```bash
python scripts/office/unpack.py <output.pptx> <tmp_unpacked>
python scripts/office/pack.py <tmp_unpacked> <tmp_roundtrip.pptx> --original <output.pptx> --validate true
python scripts/source_to_md/ppt_to_md.py <output.pptx> -o <project_dir>/reports/pptx_text_check.md
python scripts/validate_pptx_text_layout.py <output.pptx> --report <project_dir>/reports/text_layout_report.json
```

If speaker notes are enabled, verify that `ppt/notesMasters/notesMaster1.xml`
exists, the presentation has a notes master relationship, and each noted slide
has a matching notes slide. Broken notes relationships are blocking defects.

Treat any blocking issue in `text_layout_report.json` as a repair task, not as
an acceptable warning. Prefer shorter slide copy, lower-density body variants,
or slide splitting before shrinking body text below the template floor.

Render the exported PPTX itself to preview images. SVG previews and contact
sheets are not enough: inspect full-size dense pages such as process steps,
card grids, tables, reference lists, and any page ported from a larger
template. If `pdftoppm` is unavailable, use LibreOffice to export PDF and
PyMuPDF to render PNG previews.
