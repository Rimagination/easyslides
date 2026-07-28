# plugin_distill_smoke Template Language

## Summary

- Slide count: 8
- Recommended baseline surface: `source_rendered_raster_baseline`
- Slot count: 104
- Role counts: `{"cover": 1, "chapter": 1, "content": 5, "ending": 1}`

## Visual System

- Primary color: `#912C8D`
- Theme fonts: `{"majorLatin": "等线 Light", "minorLatin": "等线"}`
- Palette: #000000, #FFFFFF, #262626, #1971D3, #404040, #114B8D, #68A4C6, #0070C0
- Effect counts: `{"gradients": 2, "filters": 13, "filter_refs": 13, "opacity": 13, "rotations": 2, "nested_svg_images": 12, "cropped_images": 12}`

## Layout Grammar

- `chapter`: 1 page(s), density [3, 3], slots ['CHAPTER', 'IMAGE']
- `content`: 5 page(s), density [2, 4], slots ['BODY', 'IMAGE', 'PAGE']
- `cover`: 1 page(s), density [3, 3], slots ['IMAGE', 'TITLE', 'SUBTITLE', 'PRESENTER', 'DATE', 'HERO']
- `ending`: 1 page(s), density [3, 3], slots ['CLOSING', 'CONTACT', 'IMAGE']

## Fidelity Risks

- `gradient_or_filter_effects`: Native editable PPTX export can flatten or mis-layer translucent atmosphere, shadows, and gradient masks.
- `layered_or_cropped_media`: Image crop, rotation, and nested SVG viewBox semantics can drift during shape conversion.
- `text_anchor_alignment`: Text position checks and editable export must preserve start/middle/end anchors.

## Editable Rebuild Plan

- `faithful_visual_baseline` on `source_rendered_raster_baseline`: Lock colors, transparency, text positions, alignment, and occlusion against the original PowerPoint render.
- `editable_chrome_rebuild` on `editable_primitives`: Rebuild repeated backgrounds, headers/nav, cards, labels, and image frames one primitive family at a time.
- `slot_layer_rebuild` on `editable_slots`: Replace only validated text/image slots after the chrome has a passing visual diff.
- `visual_diff_gate` on `source_vs_generated_render`: Compare PowerPoint-rendered PNGs before claiming fidelity or registering the template.
