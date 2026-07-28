# EasySlides PPTX Distillation Contract

This document freezes the boundary between source evidence and later design
inference. The first implementation target is Phase 1: a factual OOXML source
graph. It is deliberately smaller than a component registry, but it gives all
later stages one stable input.

## Pipeline

```text
PPTX
  -> source_graph.json
  -> identity_spec.json + layout_spec.json
  -> component_catalog.json + slot_contracts.json
  -> template projections
  -> structure / geometry / text / visual / cross-material QA
  -> promotion_report.json
```

`manifest.json` remains the compact import summary. `source_graph.json` is the
object-level evidence graph and is the source of truth for native PPTX facts.
`distilled_spec.json` remains a compatibility and human-review view until the
new semantic contracts fully replace it.

## Phase 1: Source Graph

The graph records:

- package hash and part inventory;
- canvas size in EMU and pixels;
- presentation, slide, layout, master, and theme relationships;
- ordered shape-tree objects with stable object ids;
- geometry, rotation, flips, placeholder metadata, text, lightweight style
  facts, and relationship references;
- media part hashes and the parts that reference each asset;
- slide -> layout -> master lineage.

The graph does not decide whether an object is reusable. Every object starts
with `classification: "unknown"` and
`classification_basis: "phase_1_factual_graph_only"`.

## Contract Outputs

Every real-source distillation workspace should converge on these files:

| File | Responsibility | Phase |
| --- | --- | --- |
| `distill_manifest.json` | pipeline state, artifact map, modes, invariants | 0/1/2 |
| `source_graph.json` | factual native PPTX evidence | 1 |
| `identity_spec.json` | brand, typography, palette, chrome, identity rules | 2 |
| `layout_spec.json` | page grammar, geometry, parent transforms, spatial roles | 2 |
| `component_catalog.json` | fixed, replaceable, hybrid component assets | 2 |
| `slot_contracts.json` | role, capacity, alignment, overflow, replacement rules | 2/3 |
| `asset_provenance.json` | source part, derived asset, license and reuse lineage | 2 |
| `adaptation_policy.json` | mirror, layout, design-system projection policy | 2/3 |
| `review_queue.json` | unresolved objects, risks, and human decisions | 1/2 |
| `design_system_pack.json` | declarative source-template design-system package | 3 |
| `component_registry_fragment.json` | registry fragment for source-scoped discovery | 3 |
| `projection_manifest.json` | renderer mappings and page/component projection targets | 4 |
| `promotion_report.json` | unified promotion decision and next actions | 5 |

## Canonical Runtime Shells

The reusable runtime template has an evidence-driven public shell profile of
3-5 page shells. `cover`, `content`, and `ending` are required; `toc` and
`chapter` are optional and appear only when the source deck provides evidence
for them. A source deck may contain more pages, but those pages remain in the
reference evidence and `source_page_roster.json`. Repeated content compositions
are grouped in `body_variants.json`; repeated visual primitives are promoted to
component or symbol assets.

The shell contract is fail-closed:

```json
{
  "canonical_shell_policy": "evidence_driven_three_to_five_stable_shells",
  "canonical_shell_minimum": 3,
  "canonical_shell_limit": 5,
  "required_shell_roles": ["cover", "content", "ending"],
  "optional_shell_roles": ["toc", "chapter"],
  "active_shell_roles": ["cover", "content", "ending"]
}
```

Adding a sixth public SVG because a source slide has a different evidence
arrangement is a distillation failure. Add a body variant, component asset, or
explicit overflow route instead.

## Body Variant Composition

`body_variants.json` is the page-composition layer, not a second component
library. A composed variant points to reusable modules through ordered
`component_refs`; component definitions remain in the global registry or the
template's `component_catalog.json`.

```json
{
  "variant_id": "figure_with_notes",
  "composition_mode": "ordered_component_refs",
  "component_refs": [
    {
      "asset_id": "component_package/figure_with_notes",
      "instance_id": "main_figure",
      "role": "primary_evidence",
      "order": 1,
      "required": true,
      "slot_bindings": {
        "figure": "MAIN_FIGURE",
        "notes": "INTERPRETATION"
      }
    }
  ]
}
```

The global component registry indexes both `body_variant` and
`template_component` assets. The component plan must preserve the ordered
dependency list and aggregate the QA gates of every required component. See
`references/body-variant-component-contract.md`.

The current repository also writes `distilled_spec.json`,
`template_language.md`, and `source_geometry_risks.json`. These are retained as
compatibility views and must not silently contradict the new contracts.

## Classification

The semantic registry uses four states:

- `fixed`: source identity or chrome; content replacement is prohibited;
- `replaceable`: material-bearing object with a slot contract;
- `hybrid`: fixed shell with replaceable children or parameters;
- `unknown`: unresolved; route to `review_queue.json`.

Classification is evidence-backed. A text box is not automatically a slot, and
an image is not automatically replaceable. Placeholder metadata, lineage,
repetition, visual role, and cross-slide reuse are signals, not silent rules.

## Projection Modes

- `mirror`: preserve page count, order, geometry, and source identity;
- `layout`: preserve page grammar and component relationships while allowing
  controlled content and count changes;
- `design-system`: publish reusable component and slot assets for new decks.

Each output must declare its mode. A mode change is an explicit adaptation,
not an accidental consequence of fitting content.

## Hard Geometry Rule

For every eligible text/container pair, the text center on the vertical axis
must equal the container center on the vertical axis. The geometry contract is:

```text
abs(text_center_y - container_center_y) <= tolerance
```

The default tolerance is zero in the logical geometry model. Optical or
baseline exceptions are allowed only when they are explicitly represented in
the slot contract with a reason and an adjustment value. Rendered QA must still
check the visible result.

## QA Layers

1. Structure: package parts, relationships, ids, and output contracts.
2. Geometry: bounds, transforms, parent-child containment, center alignment.
3. Text: overflow, clipping, line count, font fallback, vertical alignment.
4. Visual: rendered source versus projection diff.
5. Cross-material: at least two materially different inputs through the same
   template and slot contracts.

## Compatibility Rule

The graph is factual, the semantic registry is inferential, and rendered pages
are the visual truth. No later stage may overwrite native source evidence in
`source_graph.json`; it should add a derived contract or review decision.

Phase 2 writes the seven derived contracts into the same reference workspace.
Only objects with native placeholder or image evidence become replaceable by
default. Other slide objects remain `unknown` and are listed in
`review_queue.json`.

Phase 3 writes `design_system_pack.json` and
`component_registry_fragment.json`. These assets are source-template scoped and
declarative. They are discoverable by the global registry, but they are not
installable executable component packs until a reviewed renderer mapping and
cross-material QA are available.

Phase 4 adds `projection_manifest.json` and the
`source_template_projection` renderer. The projection target is SVG; native
PPTX output continues through the existing `scripts/svg_to_pptx.py` route.
Projection replaces only declared slots, preserves source geometry and layer
order, and fails closed when a slot element cannot be located.

Phase 5 adds `promotion_report.json` through
`scripts/pptx_distill_promotion_gate.py`. It composes projection readiness,
slot-contract validation, SVG/PPTX geometry, native text-layout checks, render
diffs, and cross-material smoke evidence. Missing evidence is
`review_required`, not a pass. Promotion is allowed only when every gate
passes and no unresolved projection review remains.
