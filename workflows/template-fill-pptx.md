---
description: Native PPTX template fill workflow for raw PowerPoint templates.
---

# Template Fill PPTX Workflow

Run when the user provides a raw `.pptx` template plus new material or a topic
and asks for a generated deck that keeps the original PowerPoint design. This
workflow treats the source PPTX as a native slide library and produces a new
PPTX by selecting, cloning, and patching slides through OOXML.

## Route Boundary

Use this workflow for one-off native template fill. Do not run
`pptx_to_svg.py`, `pptx_template_import.py`, `finalize_svg.py`, or
`svg_to_pptx.py` here.

If the user wants a reusable EasySlides template package, run
`workflows/pptx-to-easyslides-template.md` first instead.

## Project Layout

```text
projects/<name>/
  sources/        # raw PPTX template and source materials
  analysis/       # slide library JSON and fill_plan.json
  exports/        # filled native PPTX
  validation/     # read-back Markdown and validation notes
```

## Current Implementation Contract

The V1 script entry point is:

```powershell
python scripts/template_fill_pptx.py analyze <pptx> -o <project>/analysis/slide_library.json
python scripts/template_fill_pptx.py scaffold <project>/analysis/slide_library.json -o <project>/analysis/fill_plan.json
python scripts/template_fill_pptx.py validate <project>/analysis/fill_plan.json
python scripts/template_fill_pptx.py apply <project>/analysis/fill_plan.json -o <project>/exports/filled.pptx
```

V1 supports analysis, plan scaffolding, validation, and native apply for plans
that select, reorder, and reuse source slides. Apply rebuilds the presentation
slide list, clones source slide parts, and patches text/table/chart-cache slots
without entering the SVG pipeline.

For edited charts, V1 clones the chart XML per output slide, updates chart
caches, and clones/synchronizes the embedded workbook part so PowerPoint's chart
data view follows the visible chart. Reused source slides therefore do not bleed
chart edits into each other.

For slide-local structured dependencies, V1 deep-clones private package parts
and writes explicit content-type overrides where needed. Shared design
infrastructure such as masters, layouts, themes, and reusable media remains
shared to keep the output package compact and faithful to the source template.
SmartArt and embedded objects are preserved as native package parts, but their
internal semantic editing is not part of the fill-plan schema yet.

## Fill Plan Rules

- The target story controls output order; source slide order is only inventory.
- A source slide may be reused more than once when its layout fits multiple
  target messages.
- Each planned slide records `source_slide`, `purpose`,
  `layout_rationale`, `replacements`, optional `table_edits`,
  optional `chart_edits`, `notes`, and `transition`.
- Text replacement must respect slot geometry and paragraph count where known.
- Chart edits may set `categories` and existing series `name`/`values`; each
  edited output slide gets its own chart XML part and embedded workbook clone so
  reused source slides do not bleed chart changes into each other.
- Visible design, masters, layout parts, images, and charts are preserved unless
  explicitly targeted by the fill plan.
