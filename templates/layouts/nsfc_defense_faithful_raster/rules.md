# nsfc_defense_faithful_raster Rules

- Preserve fixed source geometry before introducing body variants.
- Replace only declared slots from `layouts.json` and `slot_contracts.json`.
- Do not move, resize, recolor, or delete repeated source chrome during faithful reuse.
- Keep cover and ending pages page-specific unless a reviewer explicitly approves a generalized variant.
- Use `page_catalog.json` for page selection by story role, density, and source-slide evidence.
- Verify SVG previews and exported PPTX previews before registering this as production-ready.
