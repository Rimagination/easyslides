# annual_speech_2025_distilled Template Language

## Summary

- Slide count: 29
- Recommended baseline surface: `source_rendered_raster_baseline`
- Slot count: 328
- Role counts: `{"cover": 1, "content": 19, "toc": 2, "chapter": 5, "ending": 2}`

## Visual System

- Primary color: `#912C8D`
- Theme fonts: `{"majorLatin": "等线 Light", "minorLatin": "等线"}`
- Palette: #262626, #FFFFFF, #912C8D, #68A4C6, #441351, #6C2280, #000000, #404040
- Effect counts: `{"gradients": 15, "filters": 53, "filter_refs": 53, "opacity": 55, "rotations": 7, "nested_svg_images": 50, "cropped_images": 50}`

## Layout Grammar

- `chapter`: 5 page(s), density [3, 4], slots ['CHAPTER', 'IMAGE']
- `content`: 19 page(s), density [3, 4], slots ['BODY', 'IMAGE', 'PAGE']
- `cover`: 1 page(s), density [3, 3], slots ['TITLE', 'SUBTITLE', 'PRESENTER', 'HERO', 'IMAGE']
- `ending`: 2 page(s), density [3, 3], slots ['IMAGE', 'CLOSING', 'CONTACT']
- `toc`: 2 page(s), density [2, 4], slots ['TOC', 'IMAGE']

## Fidelity Risks

- `gradient_or_filter_effects`: Native editable PPTX export can flatten or mis-layer translucent atmosphere, shadows, and gradient masks.
- `layered_or_cropped_media`: Image crop, rotation, and nested SVG viewBox semantics can drift during shape conversion.
- `text_anchor_alignment`: Text position checks and editable export must preserve start/middle/end anchors.

## Editable Rebuild Plan

- `faithful_visual_baseline` on `source_rendered_raster_baseline`: Lock colors, transparency, text positions, alignment, and occlusion against the original PowerPoint render.
- `editable_chrome_rebuild` on `editable_primitives`: Rebuild repeated backgrounds, headers/nav, cards, labels, and image frames one primitive family at a time.
- `slot_layer_rebuild` on `editable_slots`: Replace only validated text/image slots after the chrome has a passing visual diff.
- `visual_diff_gate` on `source_vs_generated_render`: Compare PowerPoint-rendered PNGs before claiming fidelity or registering the template.
