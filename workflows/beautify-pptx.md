---
description: Conservative workflow for existing PPTX 1:1 visual beautification.
---

# Beautify PPTX Workflow

Run when the user provides a finished `.pptx` and asks to improve visual polish
while preserving slide count, slide order, and visible wording. This is distinct
from rebuilding the deck from source material and distinct from append-only
enhancement with notes, audio, timings, or transitions.

## Current Implementation Contract

The V1 script entry point is:

```powershell
python scripts/beautify_pptx.py inspect <source.pptx> --out <project>/reports/beautify
python scripts/beautify_pptx.py apply <source.pptx> -o <project>/exports/beautified.pptx --report-dir <project>/reports/beautify --primary "#2454A6" --accent "#E9B44C"
```

V1 is deliberately conservative. It can:

- inspect a PPTX and write `beautify_report.json`
- record slide count, visible text by slide, and package-risk counts
- write `workflow_manifest.json` for the route run
- apply a native theme color patch to theme-bound colors
- verify that slide count and visible text are preserved after patching

V1 does not yet perform per-slide layout repair, typography normalization,
shape alignment, or object-level restyling. Those require a fuller visual diff
and patch planner.

## Route Boundary

Do not route this request through the main SVG generation pipeline unless the
user explicitly allows restructuring, rewriting, merging, splitting, or
reordering slides.

If the user needs stronger beautification than a theme-color patch, state that
the current route can produce an audit/report and conservative theme patch, then
ask whether the slide structure may be rebuilt through the main EasySlides
pipeline.

## Future Implementation Contract

A production implementation should:

- unpack and index the source PPTX
- render before/after PNGs for every slide
- preserve existing visible text content and reading order
- keep slide count and slide order fixed
- apply typography, alignment, spacing, and contrast improvements through native
  PPTX/OOXML patches or audited reconstruction
- write a visual-review package and machine-readable change report
- fail closed when a slide contains unsupported objects that cannot be safely
  restyled
