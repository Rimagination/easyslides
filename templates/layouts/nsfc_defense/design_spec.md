---
template_id: nsfc_defense
canvas: ppt169
mode: slot_guided_mirror
category: academic_research
summary: NSFC defense template distilled from a dense research-defense deck.
keywords: [nsfc, defense, research, national_need, innovation, application, evidence]
primary_color: '#751497'
canvas_format: ppt169
replication_mode: slot_guided_mirror
---

# NSFC Defense

`nsfc_defense` is the canonical template for National Natural Science Foundation
defense decks. It preserves the source deck's purple chrome, title treatment,
and scientific visual grammar while rebuilding each source-derived content
composition inside a controlled body canvas.

## Narrative organization

1. **National need and problem**: establish the national demand, bottleneck,
   research hotspot, and quantitative technical target.
2. **Innovation and technical content**: compare baselines, state innovation,
   show equations or architectures, and connect material/device work to system
   behavior.
3. **Application and social benefits**: present application evidence, papers or
   international results, metrics, and technology transfer outcomes.

Each content page follows `claim -> evidence -> consequence`. Dense pages are
intentional: keep five stable shells and choose a body variant with the right
evidence shape instead of creating a new shell for every source page. Every
body variant is tied to a source slide, a section, a narrative role, and an
ordered component composition. Content pages are not a free-form component
stage: a plan must name the matching `section`, `story_role`, and
`body_variant_id`.

## Visual grammar

- 1280 x 720 canvas with purple gradient header and a restrained circuit motif.
- White research panels over a very light neuron texture.
- `#751497` is structural; `#C00000` is reserved for conclusions, risks, and
  decisive metrics.
- Source-style Chinese bold/medium typography, large section titles, compact
  image captions, purple arrows, bordered white panels, and multi-panel exhibits.
- Cover, agenda, chapter divider, content, and ending are the five stable shells.
- The content shell preserves only the page title and fixed chrome. Its
  `body_canvas` is cleared before a body variant places its components.
- The source deck's dense evidence forms live in `body_variants.json`. Each
  variant declares a distinct `composition_scene`, regions, and component map.

## Page archetypes

See `layouts.json`, `body_variants.json`, `source_page_roster.json`,
`page_catalog.json`, and `story_structure.json`. The roster contains five
stable shells and twelve source-derived body variants, including research-
hotspot KPI pages, ANN/SNN comparison, equation/network architecture,
literature result, and application-benefit pages.

## Slot policy

Use `slot_contracts.json`. The content shell exposes `PAGE_TITLE` only; body
material enters through the selected body's variant slots and component-local
bindings. Source-page body slots are retained as provenance-only shadow
metadata, never as direct generation targets. Text is vertically center-locked
to its declared box. Direct `body_components` are forbidden. A composition
outside this catalog requires a reviewed source-page evidence record and a new
registered body variant; it is not an ad hoc page assembly operation.
