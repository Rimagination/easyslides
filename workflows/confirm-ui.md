---
description: Local confirmation page workflow for EasySlides project planning.
---

# Confirm UI Workflow

Run before visual execution when the user needs a compact confirmation page for
project assumptions, deck plan, style, brand, and source inventory.

## Route Boundary

This workflow packages existing project artifacts for user confirmation. It
does not invent missing plan values and does not replace the Strategist's
`deck_plan.json`, `design_spec.md`, or `spec_lock.md` responsibilities.

## Commands

First-time users are interviewed in chat using native popup questions; follow
`workflows/clarification-gate.md`. `guide` describes that conversation-first
path. Only when the user requests an HTML guide, use `guide --html` to locate
the optional page. Do not require a form or copy/paste for intake. These optional
diagrams explain editing scope, not measured production quality. Show sample
images/render pairs inline by default; generate an HTML confirmation package
only when that presentation is explicitly requested.

```powershell
python scripts/confirm_ui.py <project> --out <project>/reports/confirm_ui
python scripts/confirm_ui.py <project> --out <project>/reports/confirm_ui --brand academic-blue
python scripts/confirm_ui.py <image_project> --out <image_project>/reports/pilot --pilot-pages 1,5 --pptx <exact.pptx>
```

## Output Contract

- `confirm.json`: machine-readable confirmation manifest.
- `index.html`: local confirmation page with checkboxes for project, deck title,
  canvas, slide count, scenario, brand, sources, design spec, and spec lock.

## Confirmation Rules

- `--pilot-pages` shows actual source images alongside actual editable PPTX
  renders and the chosen editability scope. Source/render/PPTX identities must
  match; missing or stale artifacts fail closed. `--pptx` supports explicitly
  selected renamed outputs without silently choosing by file date/name.
- A pilot remains `needs_review`, or `needs_repair` when existing QA reports
  failures. It never claims delivery-ready from a checkbox or an old QA pass.
  The feedback textbox is manually copied back into chat. Approval confirms
  direction only; it does not bypass final quality checks.

- Missing values remain `unconfirmed`; do not silently substitute defaults.
- If the user changes a value, update the owning artifact first, then rebuild
  the confirmation page.
- Do not proceed to SVG authoring when confirmed values disagree with
  `deck_plan.json`, `design_spec.md`, or `spec_lock.md`.
