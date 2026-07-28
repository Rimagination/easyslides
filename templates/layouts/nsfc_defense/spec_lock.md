# NSFC Defense Spec Lock

- Template id: `nsfc_defense`
- Source family: `nsfc_defense_distilled`
- Runtime binding: source chrome plus reviewed body-scene component slots
- Canvas: 1280 x 720, `ppt169`
- Fixed identity: purple research-defense chrome, neuron texture, circuit header,
  red conclusion emphasis, dense white evidence panels, and source page roster.
- Allowed edits: page-title replacement and source-guided selection of a
  reviewed body scene inside the controlled content body canvas. The approved
  argument scene preserves the reviewed source structure while using the NSFC
  purple token system, and can only be selected through
  `grant_text_evidence_stack`.
- Forbidden edits: direct replacement of legacy body slots, DOM-order-only
  replacement, arbitrary chrome geometry changes, generic card substitution for
  scientific exhibits, direct body-component placement, component color/font/
  geometry/crop/layer-order changes, and unreviewed new source-derived scenes
  or shells. The adapted argument scene may only use its declared NSFC token
  mapping; its structural geometry and type scale remain locked.
- Hard text rule: text center Y equals its declared container center Y.
