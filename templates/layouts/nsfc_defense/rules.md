# NSFC Defense Rules

- Select one of the five canonical shells, then choose a source-derived body
scene by section, story role, density, evidence count, and source archetype.
- Preserve header treatment, chapter navigation, purple identity, and red
  emphasis semantics. The content shell owns chrome, not a fixed body grid.
- Build content as `claim -> evidence -> consequence`.
- Use at least one figure, equation, table, metric group, or literature exhibit
  on a dense content page; do not collapse scientific evidence into body text.
- Red is for decisive conclusions, warnings, and measured outcomes; it is not a
  general accent color.
- The content shell exposes `PAGE_TITLE` (running title), `KEY_MESSAGE`
  (one or two square-bullet central-message lines), and automatic
  `PAGE_NUMBER`. All body material must enter through a selected body variant
  and stay inside its `body_canvas` regions.
- `KEY_MESSAGE` is the only page-level conclusion. It must be a concise,
  non-repeating claim; body copy must serve evidence, captions, data labels,
  method steps, or supporting takeaways instead. Do not type the square bullet
  yourself: the template owns it.
- `PAGE_TITLE` is a hard single-line title slot with a ten full-width-
  character budget. Shorten the wording before generation; do not insert a
  line break or rely on automatic fitting.
- Every content-page plan must provide `section`, `story_role`, and
  `body_variant_id`; they must match the variant's source narrative contract.
- Direct `body_components` are forbidden. New compositions require source-page
  evidence, declared leaf components, and a reviewed `body_variants.json`
  entry. Do not recolor, resize, crop, change fonts, or reorder layers inside a
  source-derived component.
- Moving or resizing source chrome requires a new reviewed shell; routine
  content variation belongs in `body_variants.json` and its composition scene.
- Text boxes must declare geometry and vertical alignment. Their center Y must
  match their container center Y within geometry QA tolerance.
- The ending shell uses one closing line only. Its default is `敬请批评指正`;
  do not use `聆听` in ending copy or place a subtitle in the title region.
- Overflow action order: choose a lower-density body variant, split evidence,
  then shrink within the declared font floor.
- Run SVG, native PPTX, visual, and cross-material checks before promotion.
