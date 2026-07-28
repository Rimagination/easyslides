---
template_id: nsfc_purple_semantic
canvas: ppt169
mode: semantic
category: academic_research
summary: Semantic named-slot template family for research reporting and defense decks.
keywords: academic, research, defense, semantic-layout, named-slots
primary_color: '#751497'
canvas_format: ppt169
replication_mode: semantic_named_slots
---

# NSFC Purple Semantic

A content-free semantic template family distilled from the purple NSFC reference.
It preserves the purple identity, title treatment, pale panels, rounded cards,
and restrained scientific tone without copying source slide order or content.
Cover and ending use a template-owned, content-free dark-purple decorative
background asset recorded in `assets/background_asset.json`.

Production rendering must use named `data-slot` bindings through
`scripts/semantic_template_renderer.py`. DOM-order replacement is forbidden.

## Visual language

- Primary: `#751497`; deep accent: `#4B0D65`; highlight: `#BF4BE7`.
- Surface: pale purple `#F8EAFC`, white cards, border `#E6D5EC`.
- Typography: Microsoft YaHei with bold titles, restrained body text, and no
  source-specific text, logo, figure, or background.
- Canvas: 1280 x 720 (`ppt169`), with a 72 px purple header and a 38 px footer
  band on content pages.
- Components: message bars, rounded cards, image frames, comparison badges,
  metric cards, process circles, timeline rails, quote panels, metric strips,
  table frames, four-card grids, and accent symbols are registered in
  `component_catalog.json` and indexed by `assets/asset_manifest.json`.

## Layout and content contract

Use `layouts.json`, `page_catalog.json`, and `body_variants.json` as the
machine-readable source of truth. Select content pages by semantic role,
`content_shape`, and `item_count`. Never select by source slide number or DOM
order. Every text slot declares capacity and overflow action; split or select
another variant when capacity is exceeded.

The expanded page family includes timeline/milestone, quote/key-takeaway,
metric/KPI summary, table/benchmark, and four-card evidence-matrix patterns.
These are selectable variants, not fixed source-page copies.

Compact control text is hard-locked: its text box center Y must equal its
container center Y within the geometry QA tolerance, and its vertical alignment
must be `middle`/`center`. This is a production invariant, not a styling hint.

## Promotion

The template is not production-ready until the unified gate passes contract,
SVG quality, strict SVG text slots, SVG geometry, native PPTX geometry, native
text layout, placeholder scan, visual diff, cross-material smoke, and human
visual review. See `spec_lock.md` and `rules.md`.
