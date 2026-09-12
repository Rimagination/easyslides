# defense_topnav Rules

- `defense_topnav` is a source-faithful academic-blue defense template with a dynamic top navigation bar.
- Default palette is `academic_blue`; alternate palettes must come from `theme_palettes.json` and replace `primary`, `primary_dark`, `soft_surface`, `border`, and `emphasis_text` as a semantic set.
- `thesis_navy_v4` is an opt-in style profile for the Chinese degree-defense
  variant. It exposes `#0A3476` title navy, black body/caption/table text,
  `#333333` secondary text, `#1C8B92` accent, and `#C8D5E6` light borders
  without changing the template's default `academic_blue` palette.
- The v4 defense workflow defaults to editable master design and does not
  generate Image2 visuals. Visual exploration is an explicit upstream choice;
  when enabled, it is a style reference only and never replaces source figures.
- Preserve the source PPT fixed geometry for the cover band, TOC left blue panel, six top-navigation labels, gray key-message bar, open content canvas, and bottom page number.
- Keep cover and ending metadata text boxes in absolute canvas coordinates centered at x=320, 640, and 960; translated groups are reserved for the decorative icons so native PPTX text boxes stay aligned with their icons.
- Keep the ending page intentionally different from the cover: use the asymmetric left blue panel and right-side closing text composition.
- The closing page must not contain the Chinese word `聆听` or any Chinese expression containing `聆听`. English `listening` remains allowed.
- The default Chinese ending title is `恳请老师批评指正！` unless the user provides another academically appropriate line.
- On the ending page, the third metadata item labels `CONTACT` as `专业：`; do not label it as `联系方式：`.
- Treat the top navigation as six variants, not six duplicated SVG shells: `D02-NAV-01` through `D02-NAV-06` in `navigation_states.json`.
- Switch only the active tab, active label/subtitle, and active/inactive text fills when changing sections.
- Keep `03_content.svg` flexible: it must expose one open `CONTENT_AREA` and one `CONTENT_BODY` placeholder.
- Keep the base `CONTENT_AREA` guide invisible (`fill="none"` and `stroke="none"`). Add visible frames only inside a selected body variant when the content needs them.
- Use circular frames for school-emblem placeholders; keep the doctoral cap mark as the default academic placeholder.
- Treat the three-card layout as only one optional `body_variants.json` composition, not as fixed SVG shell chrome.
- Do not use fixed bottom keyword, source, or summary slots on content pages. The bottom area keeps only `PAGE_NUM`.
- Keep `PAGE_TITLE` and `KEY_MESSAGE` on the same visual center line; both text boxes must use middle vertical alignment.
- Keep `KEY_MESSAGE` visually inset inside the gray bar; the text and PPTX textbox left edge should leave at least 24px from the gray backplate's left edge.
- Choose body variants by content semantics: text-first for dense arguments, diagram/flow for relationships and processes, figure-led for image evidence, and cards only for genuinely parallel points.
- For `process_timeline` and similar flow layouts, timeline and process sequences must draw a visible connector line through every circular node center; compute the connector from the actual first and last node positions so 3, 4, 6, or other node counts stay connected.
- Keep generated content below y=118 on content pages.
- Keep card body text at or above 18px; split dense slides rather than shrinking text.
- If a content slide uses a source figure or table screenshot, include a concise exhibit name. Put figure names below images and table names above images.
- Avoid adding external raster assets to the reusable SVG shells. If a generated deck needs images, place them inside the open content area as deck content.
- Final QA for generated defense_topnav decks must include rendered previews for each active navigation state that appears in the deck.
