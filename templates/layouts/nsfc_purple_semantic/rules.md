# Rules

- Scenario first, template second.
- Resolve content pages by `content_shape`, never by source page number.
- Every slot has an explicit capacity and overflow policy.
- Choose another variant or split the slide when capacity is exceeded.
- Prefer timeline, quote, metrics, table, or four-card variants when the
  content shape matches; do not force every argument into a two-column card.
- Use table slots for comparable rows and metric slots for independent KPIs;
  do not encode either as decorative body text.
- Source-specific text, figures, logos, and raster backgrounds are forbidden.
- A generic full-slide raster background is allowed only when it is template-owned,
  content-free, and recorded in `assets/background_asset.json`.
- A deck with any blocking QA issue is a review draft, not a final deliverable.
- `data-pptx-textbox` text must declare box geometry and `data-pptx-valign`.
- Compact control text must use `middle`/`center` and share the container center Y.
- Do not promote a template whose strict SVG text, geometry, native PPTX,
  visual-diff, or cross-material gate is missing or unresolved.
