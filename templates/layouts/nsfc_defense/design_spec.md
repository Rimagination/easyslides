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
and scientific visual grammar. Its content layer is organized as locked,
source-derived leaf components placed only through reviewed body scenes.

## Narrative organization

1. **National need and problem**: establish the national demand, bottleneck,
   research hotspot, and quantitative technical target.
2. **Innovation and technical content**: compare baselines, state innovation,
   show equations or architectures, and connect material/device work to system
   behavior.
3. **Application and social benefits**: present application evidence, papers or
   international results, metrics, and technology transfer outcomes.

Each content page follows `claim -> evidence -> consequence`. Dense pages are
intentional: keep five stable shells and choose a reviewed scene with the right
evidence shape instead of creating a new shell for every source page. Every
scene is tied to source slides, a section, a narrative role, and an ordered
composition of declared leaf components. Content pages are not a free-form
component stage: a plan must name the matching `section`, `story_role`, and
`body_variant_id`.

## Visual grammar

- 1280 x 720 canvas with purple gradient header and a restrained circuit motif.
- White research panels over a very light neuron texture.
- `#751497` is structural; `#C00000` is reserved for conclusions, risks, and
  decisive metrics.
- Source-style Chinese bold/medium typography, large section titles, compact
  image captions, purple arrows, bordered white panels, and multi-panel exhibits.
- Cover, agenda, chapter divider, content, and ending are the five stable shells.
- The content shell has a fixed information hierarchy: a one-line running
  title, one or two square-bullet central messages, a source-derived body
  scene, and an automatic lower-right page number. Its `body_canvas` is
  cleared before a body variant places its components.
- The source deck's dense evidence forms live in `body_variants.json`. Each
  reviewed scene declares regions and an ordered map of locked source-derived
  leaf components. Header chrome and page-local helpers are not components.

## Page archetypes

See `layouts.json`, `body_variants.json`, `source_page_roster.json`,
`page_catalog.json`, and `story_structure.json`. The roster contains five
stable shells, thirteen source-derived editable leaf components, one
research_core-derived text-rich page scene, and nine reviewed body scenes. The
imported scene remains page-level rather than being treated as a reusable leaf
component; raw extraction fragments remain provenance-only and are never
offered as selectable components.

## Slot policy

Use `slot_contracts.json`. The content shell exposes `PAGE_TITLE` as the
running title, `KEY_MESSAGE` as the central message, and template-owned
`PAGE_NUMBER`. `KEY_MESSAGE` contains one or two square-bullet lines and must
state the page's smallest defensible point. Body material enters through the
selected body's variant slots and component-local bindings, where it must act
as evidence heading, figure caption, data label, method step, or supporting
takeaway rather than repeating the central message. Source-page body slots are
retained as provenance-only shadow metadata, never as direct generation
targets. Text is vertically center-locked to its declared box. Direct
`body_components` are forbidden. A composition outside this catalog requires
a reviewed source-page evidence record and a new registered body variant; it is
not an ad hoc page assembly operation.
