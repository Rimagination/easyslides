# PPT Master Page Recipe Manual

This manual is for agents using the PPT Master-compatible route. The main
layout unit is a whole SVG page, not an isolated card.

## Selection Order

1. Classify the slide's expression intent:
   - `overview`
   - `evidence`
   - `mechanism`
   - `metric`
   - `comparison`
   - `process`
   - `argument`
   - `conclusion`
2. Query a whole-page recipe:

   ```bash
   python scripts/page_recipe.py query --content-shape causal_chain --item-count 4
   python scripts/page_recipe.py prompt --recipe-id pm_causal_map
   ```

3. Compress source content into the recipe's slot capacities.
4. If a region needs a reusable card module, query `scripts/card_recipe.py`.
5. Hand-write one full `1280x720` SVG page in `svg_output/`.
6. Validate SVG text slots before export:

   ```bash
   python scripts/validate_svg_text_slots.py <project>/svg_output --strict-unboxed \
     --report <project>/reports/svg_text_slot_report.json
   ```

## Hard Rules

- Page-level diversity comes from `page_recipe.py`; card-level polish comes
  from `card_recipe.py`.
- Non-decorative text must be inside fixed slots using
  `data-pptx-textbox="true"` plus `data-pptx-box-x/y/w/h`.
- Use explicit `<tspan>` lines. Do not rely on PowerPoint auto-fit or hidden
  wrapping.
- If text does not fit, shorten the content, split the page, or choose another
  page recipe. Do not shrink body text below the recipe's minimum.
- Every page should have a visible hierarchy: one dominant idea, secondary
  support, and a controlled action or synthesis region.

## Available Recipes

The registry is `templates/page_layouts/ppt_master_page_recipes.json`.

- `pm_overview_mosaic`: 3-6 parallel points with one synthesis band.
- `pm_evidence_split`: source visual on the left, explanation rail on the
  right.
- `pm_causal_map`: left-to-right mechanism or cause chain.
- `pm_metric_dashboard`: dominant metric plus supporting indicators.
- `pm_comparison_matrix`: four-quadrant comparison or decision page.
- `pm_process_roadmap`: staged process or method route.
- `pm_argument_stack`: claim, evidence, reasoning hierarchy.
- `pm_takeaway_panel`: conclusion or recommendation rows.

## Preview Deck

Generate a renderable 8-page preview project:

```bash
python scripts/page_recipe_preview.py --output-dir outputs/page_recipe_preview_project
python scripts/ppt_master_pipeline.py export outputs/page_recipe_preview_project
```

The preview project is expected to pass:

- `scripts/validate_svg_text_slots.py`
- `scripts/svg_quality_checker.py`
- `scripts/validate_pptx_text_layout.py`

## Diversity Guidance

Avoid repeating the previous page recipe unless the deck is intentionally in a
series. If the previous slide used a grid-like page, prefer a split, chain,
roadmap, or dominant-metric page next.
