---
description: Visual review package workflow for rendered PPTX inspection.
---

# Visual Review Workflow

Run when the user asks to inspect, visually review, self-check, or share a
rendered deck preview before delivery. This workflow is a human review companion
to the blocking QA gates; it does not replace `visual_measure_gate.py`.

## Route Boundary

Use this workflow after a PPTX exists. For automated blocking checks, still run
`scripts/visual_measure_gate.py`. For reference-vs-output pixel comparison, use
`pptx_visual_diff.py` or the relevant image reconstruction QA command.

## Commands

```powershell
python scripts/visual_review.py <deck.pptx> --out <project>/reports/visual_review
```

If slides were already rendered:

```powershell
python scripts/visual_review.py <deck.pptx> --out <project>/reports/visual_review --rendered-dir <project>/reports/rendered_png --skip-render
```

## Output Contract

- `visual_review.json`: machine-readable review manifest.
- `index.html`: local browser review page with slide previews and checkboxes.
- `contact_sheet.png`: compact slide overview for rhythm checks.
- `slides/slide_###.png`: rendered pages when rendering is not skipped.

## Review Scope

Inspect full-size slide previews for readability, alignment, missing assets,
unexpected clipping, broken charts, and page rhythm. Contact sheets are useful
for rhythm, but full-size slides remain authoritative for text overflow.
