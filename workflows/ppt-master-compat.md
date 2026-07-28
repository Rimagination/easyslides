---
description: PPT Master-compatible EasySlides pipeline: strict serial gates, hand-written SVG execution, native DrawingML export, and rebuildable backups.
---

# PPT Master Compatibility Workflow

Use this workflow when the user explicitly asks for PPT Master behavior, a
PPT Master-compatible deck pipeline, or high-fidelity SVG-to-native-PPTX output.
It preserves EasySlides' local converters and QA gates while mirroring PPT
Master's operating contract.

## Core Rule

PPT Master compatibility is a workflow contract, not a batch generator.

```text
Source material
-> project init
-> Strategist writes design_spec.md and spec_lock.md
-> optional image acquisition
-> Executor selects whole-page recipes and hand-writes SVG pages sequentially into svg_output/
-> svg_quality_checker.py
-> validate_svg_text_slots.py
-> notes/total.md
-> total_md_split.py
-> finalize_svg.py
-> svg_to_pptx.py
-> validate_pptx_text_layout.py
```

The Executor must not generate all SVG pages with a Python, Node, or shell
script. Per-page authoring stays in the main agent because visual rhythm,
source fidelity, card choice, and spec-lock discipline depend on conversation
context.

## Phase A: Strategist

Required project structure:

- `sources/`
- `images/`
- `templates/`
- `svg_output/`
- `notes/`
- `exports/`

Required Strategist artifacts:

- `design_spec.md`: human-readable deck design and page outline.
- `spec_lock.md`: machine-readable execution contract for colors, fonts, page
  rhythm, image policy, template references, charts, and card usage.

Recommended EasySlides artifact:

- `deck_execution_lock.json`: freezes page ids, body variants, required gates,
  and text-fit constraints. PPT Master compatibility can continue without it,
  but strict EasySlides academic decks should create it.

Gate command:

```bash
python scripts/ppt_master_pipeline.py validate-phase-a <project_path>
```

## Phase B: Executor

Before writing the first SVG:

1. Read `references/ppt-master-compat.md`.
2. Read the selected Executor style file, usually `references/executor-consultant.md`
   or `references/executor-consultant-top.md`.
3. Read `references/shared-standards.md`.
4. Batch-read every template SVG and chart SVG named by `spec_lock.md`.

For every page:

1. Re-read `spec_lock.md`.
2. Re-read `deck_execution_lock.json` when present.
3. Select page rhythm: `anchor`, `dense`, or `breathing`.
4. Select a whole-page recipe with `scripts/page_recipe.py`; avoid repeating
   the previous page recipe unless the deck deliberately uses a series.
5. Select chart and card recipes only after the page-level archetype is fixed.
6. Compress content into declared page/card slot capacities.
7. Hand-write exactly one SVG into `svg_output/`.
8. Use top-level `<g id="...">` groups for logical animation and edit targets.
9. Mark non-decorative text with `data-pptx-textbox="true"` and
   `data-pptx-box-x/y/w/h`; use `<tspan>` lines explicitly.

Cards must use `templates/cards/card_library.json` when the page content maps
to a known card shape. Validate card payloads before rendering when practical.
Whole-page recipes live in `templates/page_layouts/ppt_master_page_recipes.json`.

Executor gate command:

```bash
python scripts/ppt_master_pipeline.py validate-executor <project_path>
python scripts/svg_quality_checker.py <project_path>
python scripts/validate_svg_text_slots.py <project_path>/svg_output --strict-unboxed --require-valign --check-canvas
```

The Executor phase is complete only when:

- `svg_output/*.svg` exists for every planned page.
- `svg_quality_checker.py` has 0 errors.
- `notes/total.md` exists.

## Export

Run the export through the compatibility wrapper:

```bash
python scripts/ppt_master_pipeline.py export <project_path>
```

The wrapper enforces this order:

1. `validate_svg_text_slots.py`
2. `visual_measure_gate.py --template-dir ...` when the locked template has a
   `geometry_contract.json`; this also validates `slot_contracts.json` so only
   declared editable slots are replaced
3. `total_md_split.py`
4. `finalize_svg.py`
5. `svg_to_pptx.py`
6. `visual_measure_gate.py` on the newest exported PPTX

Dry-run the command plan:

```bash
python scripts/ppt_master_pipeline.py export <project_path> --dry-run
```

Generate full-size PNG previews during export. On Windows the export preview
uses installed Microsoft PowerPoint first, with LibreOffice/Poppler or PyMuPDF
as a fallback:

```bash
python scripts/ppt_master_pipeline.py export <project_path> --render-png-preview
```

Check project state:

```bash
python scripts/ppt_master_pipeline.py status <project_path>
python scripts/ppt_master_pipeline.py status <project_path> --json
```

## Resume Mode

If context becomes crowded after Phase A, open a fresh thread and continue from
the project folder. The new agent should:

1. Run `python scripts/ppt_master_pipeline.py status <project_path>`.
2. Read this workflow.
3. Read `design_spec.md`, `spec_lock.md`, and source files needed for the next
   page.
4. Continue Phase B without redoing Phase A.

## Non-Goals

- This workflow does not clone PPT Master source files into EasySlides.
- This workflow does not make a batch SVG generator.
- This workflow does not replace EasySlides academic scenario routing.
- This workflow does not skip PPTX text-layout validation.
