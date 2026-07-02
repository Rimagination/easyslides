# PPT Master Compatibility Reference

This reference defines how EasySlides should behave when asked to reproduce the
PPT Master workflow. It is intentionally operational: agents should read it
before SVG execution, then use the local scripts as the source of truth.

## 1. What Is Being Reproduced

PPT Master's essential mechanism is:

- The agent authors SVG pages.
- The SVGs are checked and post-processed.
- `svg_to_pptx.py` converts SVG elements into native PowerPoint DrawingML.
- The resulting PPTX contains editable shapes, text boxes, images, groups,
  transitions, and optional animations.

The compatibility target is therefore the workflow discipline and editable
output contract, not a pixel-for-pixel copy of another repository's prompts.

## 2. Authoring Contract

SVG pages are written by the main agent one at a time.

Required page properties:

- `width`, `height`, and `viewBox` match the chosen canvas.
- Background is explicit.
- Text uses installed fonts declared in `spec_lock.md`.
- Colors come from `spec_lock.md`.
- Images come from `images/` and preserve source policy.
- Logical objects are wrapped in top-level `<g id="...">` groups.
- Every chart or card has declared geometry and no overflow.

Forbidden executor behavior:

- Generating all pages through a Python/Node/shell script.
- Inventing colors, fonts, or icons from memory.
- Skipping `spec_lock.md` rereads on long decks.
- Letting text overflow and relying on PowerPoint auto-fit.
- Flattening editable content into images unless the source itself requires it.

## 3. Page And Card Authoring

PPT Master-compatible execution starts with a whole-page recipe, not a card.
Use `templates/page_layouts/ppt_master_page_recipes.json` and
`scripts/page_recipe.py` to choose the page archetype before selecting nested
cards.

Whole-page generation sequence:

1. Classify the page role and expression shape.
2. Query the page recipe library:

   ```bash
   python scripts/page_recipe.py query --content-shape causal_chain --item-count 4
   python scripts/page_recipe.py prompt --recipe-id pm_causal_map
   ```

3. Compress content into the recipe's declared slots.
4. Author the full 1280x720 SVG page.
5. Put every non-decorative text item into a fixed text slot with
   `data-pptx-textbox="true"` and `data-pptx-box-x/y/w/h`.
6. Use `<tspan>` lines explicitly; never rely on PowerPoint auto-fit.

When the content is a card, the agent should select a card style from
`templates/cards/card_library.json`.

For PPT Master-style visual complexity, also read
`templates/cards/visual-recipes-manual.md` and query
`templates/cards/visual_recipes.json` with `scripts/card_recipe.py`.

Card generation sequence:

1. Classify content shape: metric, parallel points, comparison, process,
   evidence, method module, literature note, or callout.
2. Query the card library if needed:

   ```bash
   python scripts/card_library.py query --content-shape parallel_points --item-count 3
   ```

3. Query a visual recipe when the card needs a specific PPT Master-like
   structure:

   ```bash
   python scripts/card_recipe.py query --content-shape sequence --item-count 3
   python scripts/card_recipe.py prompt --recipe-id pm_flow_strip
   ```

4. Fit the payload into declared slot capacity.
5. Render a polished SVG group using the `consulting_light` visual skin unless
   the deck spec says otherwise.
6. Keep the group inside the page layout's assigned content box.

Preferred SVG card skeleton:

```xml
<g id="card-01">
  <rect x="80" y="160" width="360" height="420" rx="8" fill="#FFFFFF"/>
  <rect x="80" y="160" width="360" height="8" fill="#0076A8"/>
  <circle cx="128" cy="214" r="22" fill="#E0F2FE"/>
  <text x="128" y="222" text-anchor="middle" font-size="16" font-weight="700">01</text>
  <text x="112" y="280" font-size="22" font-weight="700">Card title</text>
  <line x1="112" y1="304" x2="408" y2="304" stroke="#E2E8F0"/>
  <text x="112" y="336" font-size="16">Body line</text>
</g>
```

The skeleton may be adapted, but the card's slot geometry and capacity must not
be silently expanded.

## 4. Quality Gates

Run gates in this order:

1. `python scripts/ppt_master_pipeline.py validate-phase-a <project_path>`
2. After SVG authoring: `python scripts/svg_quality_checker.py <project_path>`
3. Before export: `python scripts/validate_svg_text_slots.py <project_path>/svg_output --strict-unboxed`
4. Before export: `python scripts/ppt_master_pipeline.py validate-export-inputs <project_path>`
5. Export: `python scripts/ppt_master_pipeline.py export <project_path>`

The final export wrapper also runs `validate_pptx_text_layout.py` on the newest
PPTX. The wrapper runs `validate_svg_text_slots.py` before post-processing by
default. Any blocking issue must be repaired before delivery.

## 5. Recovery

If a session resumes later:

- Start with `python scripts/ppt_master_pipeline.py status <project_path>`.
- Trust files on disk over memory.
- Continue from the reported `next_action`.
- Do not regenerate completed Phase A artifacts unless the user requests a
  strategic rewrite.
