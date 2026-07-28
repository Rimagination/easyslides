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

```powershell
python scripts/confirm_ui.py <project> --out <project>/reports/confirm_ui
python scripts/confirm_ui.py <project> --out <project>/reports/confirm_ui --brand academic-blue
```

## Output Contract

- `confirm.json`: machine-readable confirmation manifest.
- `index.html`: local confirmation page with checkboxes for project, deck title,
  canvas, slide count, scenario, brand, sources, design spec, and spec lock.

## Confirmation Rules

- Missing values remain `unconfirmed`; do not silently substitute defaults.
- If the user changes a value, update the owning artifact first, then rebuild
  the confirmation page.
- Do not proceed to SVG authoring when confirmed values disagree with
  `deck_plan.json`, `design_spec.md`, or `spec_lock.md`.
