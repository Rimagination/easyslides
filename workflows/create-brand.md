---
description: Brand preset creation workflow for EasySlides decks.
---

# Create Brand Workflow

Run when the user asks to create, register, inspect, or reuse a brand palette
for EasySlides deck generation.

## Route Boundary

Brand presets are reusable design inputs, not a generated deck by themselves.
After creating or selecting a brand, bind it into `design_spec.md`,
`spec_lock.md`, or the selected template's design tokens before SVG authoring.

## Commands

```powershell
python scripts/create_brand.py list
python scripts/create_brand.py show academic-blue
python scripts/create_brand.py init <brand-id> --name "<Brand Name>" --primary "#2454A6" --accent "#E9B44C"
```

## Output Contract

- `templates/brands/registry.json`: discoverable brand registry.
- `templates/brands/<brand-id>/brand.json`: palette, typography, logo, and usage
  constraints.
- Optional copied logo asset under `templates/brands/<brand-id>/assets/`.

## Brand Rules

- Use `#RRGGBB` colors.
- Treat logos as optional assets; do not invent official logos.
- Keep brand presets reusable across templates; template-specific geometry stays
  in layout packs, not in the brand JSON.
