# PPT Master-Style Visual Recipe Manual

This manual is for Executor agents writing SVG cards by hand. It complements
`card_library.json`: the library answers "what content fits"; visual recipes
answer "how to draw it with PPT Master-like polish."

## Selection Flow

1. Classify the content shape.
2. Query a visual recipe:

```powershell
python scripts/card_recipe.py query --content-shape sequence --item-count 3
```

3. Read the recipe prompt:

```powershell
python scripts/card_recipe.py prompt --recipe-id pm_flow_strip
```

4. Fit payload text to slot capacities.
5. Hand-write one SVG `<g id="card-...">` component.
6. Place the group inside the assigned slide content area.

## Available Recipes

| Recipe | Best Use |
| --- | --- |
| `pm_section_header_strip` | Compact chapter or subsection header |
| `pm_text_panel_with_header` | Titled evidence/bullet panel |
| `pm_footer_note_bar` | Bottom note or caveat strip |
| `pm_left_accent_info_panel` | Context/fact card with a left accent |
| `pm_flow_strip` | 3-5 step horizontal sequence |
| `pm_numbered_takeaway_list` | Numbered conclusions inside a wide panel |
| `pm_compact_insight_card` | Small insight card with short fact lines |
| `pm_two_metric_finance_card` | Two financial/numeric metrics |
| `pm_progress_metric_card` | Three values plus a progress bar |
| `pm_image_evidence_card` | Image or figure inside a card frame |

## SVG Rules

- Output one `<g>` component, not a full slide.
- Use inline SVG attributes only.
- Do not use `<style>`, CSS classes, `foreignObject`, masks, scripts, or group opacity.
- Keep every child element inside the recipe `box`.
- Use top-level stable ids such as `card-flow-strip`, `card-metric-summary`.
- Use `<rect>`, `<line>`, `<circle>`, `<path>`, `<text>`, and `<image>` only unless a recipe explicitly allows otherwise.
- Keep text in declared slots; if content is too long, shorten or switch recipe.

## Relationship To PPTX

The SVG group is later converted by `scripts/svg_to_pptx.py` into native
DrawingML. That means each shape should be simple enough to become editable:
rounded rectangles, text boxes, lines, circles, progress bars, and simple paths
are preferred over complex filters or image-only panels.
