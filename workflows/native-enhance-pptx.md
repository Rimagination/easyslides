---
description: Native enhancement workflow for existing PPTX files.
---

# Native Enhance PPTX Workflow

Run when the user provides an existing `.pptx` and wants speaker notes,
narration audio, slide timings, or page transitions while preserving all
visible slide content and layout.

## Route Boundary

This is an append-oriented direct OOXML workflow:

```text
source.pptx -> archive project -> unzip package -> patch notes/media/timings/transitions -> rezip
```

Do not run SVG conversion, template import, `finalize_svg.py`, or
`svg_to_pptx.py`.

## Project Layout

```text
projects/<name>/
  project.json
  sources/       # archived source PPTX and optional read-back Markdown
  analysis/      # slide_index.json and enhancement_plan.json
  notes/         # one note file per slide
  audio/         # optional narration media
  exports/       # enhanced PPTX
  validation/    # read-back and coverage reports
```

## Current Implementation Contract

The V1 script entry point is:

```powershell
python scripts/native_enhance_pptx.py init <source.pptx> --name <name>
python scripts/native_enhance_pptx.py plan <project>
python scripts/native_enhance_pptx.py validate <project>
python scripts/native_enhance_pptx.py apply <project>
```

V1 supports project initialization, slide indexing, plan refresh, validation,
and direct package apply. Apply patches notes, optional narration media,
audio-duration timings, and page transitions into a copied PPTX. It must not
regenerate visible slides.

## V1 Module Scope

| Module | Behavior |
|---|---|
| `notes` | Add or replace speaker notes generated from visible slide content |
| `audio` | Embed one audio file per slide when narration is requested |
| `timings` | Set slide auto-advance based on audio duration |
| `transitions` | Add page-level transitions for narrated or selected slides |

Visible slide shapes, text bodies, images, charts, tables, masters, and layouts
are out of scope for V1 and must not be modified.
