# nsfc_defense_distilled Template Language

## Summary

- Slide count: 17
- Recommended baseline surface: `source_rendered_raster_baseline`
- Slot count: 307
- Role counts: `{"cover": 1, "content": 15, "ending": 1}`

## Visual System

- Primary color: `#751497`
- Theme fonts: `{"majorLatin": "思源黑体 CN Bold", "minorLatin": "思源黑体 CN Medium", "minorEastAsia": "思源黑体 CN Medium"}`
- Palette: #751497, #FFFFFF, #000000, #C00000, #D9D9D9, #F8EAFC, #F2F2F2, #060607
- Effect counts: `{"gradients": 122, "filters": 36, "filter_refs": 36, "opacity": 251, "rotations": 29, "nested_svg_images": 45, "cropped_images": 45}`

## Layout Grammar

- `content`: 15 page(s), density [2, 4], slots ['BODY', 'IMAGE', 'PAGE']
- `cover`: 1 page(s), density [3, 3], slots ['IMAGE', 'DATE', 'TITLE', 'SUBTITLE', 'PRESENTER', 'HERO']
- `ending`: 1 page(s), density [3, 3], slots ['IMAGE', 'CONTACT', 'CLOSING']

## Fidelity Risks

- `gradient_or_filter_effects`: Native editable PPTX export can flatten or mis-layer translucent atmosphere, shadows, and gradient masks.
- `layered_or_cropped_media`: Image crop, rotation, and nested SVG viewBox semantics can drift during shape conversion.
- `text_anchor_alignment`: Text position checks and editable export must preserve start/middle/end anchors.

## Editable Rebuild Plan

- `faithful_visual_baseline` on `source_rendered_raster_baseline`: Lock colors, transparency, text positions, alignment, and occlusion against the original PowerPoint render.
- `editable_chrome_rebuild` on `editable_primitives`: Rebuild repeated backgrounds, headers/nav, cards, labels, and image frames one primitive family at a time.
- `slot_layer_rebuild` on `editable_slots`: Replace only validated text/image slots after the chrome has a passing visual diff.
- `visual_diff_gate` on `source_vs_generated_render`: Compare PowerPoint-rendered PNGs before claiming fidelity or registering the template.
