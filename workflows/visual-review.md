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

For academic and teaching decks, use the page claim and source ledger alongside
the final render:

- Check that each figure shows the observation or comparison named on the slide.
  Verify its caption, source, time and place where they matter. Identify evidence,
  context and teaching figures by the job each performs.
- Read the actual figure area after fitting. Ensure the audience can see the
  relevant feature, labels, scale and legend. Check caption alignment and
  paragraph spacing when enlarging it. Keep information that the audience needs
  on screen and fuller explanations in the speaker notes.
- Use the contact sheet to review repeated pictures, near-duplicate crops and
  page compositions. Preserve common theme art and purposeful comparisons.
  Note the related pages when deliberately returning to the same evidence.

Record page numbers and concrete fixes in the existing review findings. Render
again after changes and inspect the affected slides and their neighbors.
Exact-path reuse warnings are a prompt to inspect the images. Visual review
is needed to recognize near-duplicates and judge whether the figure fits the
page and is readable.
