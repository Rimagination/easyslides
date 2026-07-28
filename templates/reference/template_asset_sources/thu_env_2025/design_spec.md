---
template_id: thu_env_2025
display_name_zh: 清华环境 2025 模板蒸馏
category: scenario
summary: THU Environment visual identity distilled into EasySlides academic shells plus measured body variants.
keywords:
  - thu_env
  - academic_report
  - environmental_science
  - body_variants
  - slot_guided_distillation
primary_color: "#1971D3"
canvas_format: ppt169
replication_mode: slot_guided_distillation
source_pptx: C:/Users/Liang/Downloads/2025nianhuanjingxueyuanmoban-jiyuxuexiao.pptx
---

# THU Env 2025 - Design Specification

## I. Template Positioning

`thu_env_2025` is **not** a direct PPTX mirror template. The source deck is a
large institutional PPT package with fixed photos, decorative geometry, and
placeholder content. EasySlides should not reuse it as a black-box deck.

The correct use is:

1. Preserve the THU Environment identity assets and measured visual motifs.
2. Distill useful content-page modules into body variants.
3. Render those variants inside the active EasySlides academic shell system
   (`academic_scqa`, `defense_topnav`, or chart templates), so outputs stay
   editable, capacity-checked, and consistent with the package tone.

## II. Visual Tokens To Keep

| Token | Measurement / Value | Use |
|---|---:|---|
| Canvas | `1280 x 720` | `ppt169` only |
| THU Env logo slot | `x=840.63 y=16.33 w=391.62 h=61.22` | Top-right brand mark on content pages |
| Header title position | `x=47.8 y=62.24`, source font `37.33px`, blue `#1971D3` | Map to EasySlides page title; keep concise |
| Header rule | `x1=47.74 y1=89.62 x2=1232.26 y2=89.62`, color `#5B84D8` | Thin institutional divider |
| Core blue | `#1971D3` | Page title, active labels, mid-stage bars |
| Deep blue | `#114B8D` | First stage, dark label bars, strong section labels |
| Soft blue | `#68A4C6` | Third stage, secondary labels |
| Stage numeral fill | white -> transparent vertical gradient, stop `0=#FFFFFF`, stop `0.7=#FFFFFF alpha 0` | Must be preserved for `three_phase_photo_timeline` |

Do not carry over every decorative line, shadow, and fixed photo by default.
The package tone should remain EasySlides academic: clean shells, fewer fixed
ornaments, capacity-aware text, and native editable PowerPoint output.

## III. Module Audit

| Source slide | Audit decision | Measurement / density | Keep as |
|---:|---|---|---|
| 1 | Asset only | 3 images; translucent title band; bottom blue rail | Cover photo treatment, not a body page |
| 2 | Asset only | split agenda image; 3 numbered entries | Optional TOC style; use existing agenda logic |
| 3 | Distill | 8 text objects, 10 rects, 2 images; top panel `x=105.65 y=150.32 w=1091.34 h=265.21`; bottom panel `x=105.66 y=463.45 w=1091.34 h=198.39` | `stacked_evidence_blocks` |
| 4 | Distill | 16 text objects, 14 rects, 5 images, 12 ellipse markers; 3 photo cards across page; stage numeral gradient required | `three_phase_photo_timeline` |
| 5 | Distill | 10 text objects, 14 rects, 5 images; 3 equal columns with card text above and image strip below | `three_card_with_image_strip` |
| 6 | Distill with caution | 20 text objects, 20 rects, 6 decorative paths; too dense for blind reuse | `dense_multi_block_matrix` after capacity gate |
| 7 | Distill with caution | 5 text objects, 8 images, 13 paths; image-heavy | `photo_gallery_narrative` only when images carry evidence |
| 8 | Asset only | 2 images; closing photo band and logo placement | Closing treatment, not a body page |

## IV. Body Variants

Machine-readable variant contracts live in `body_variants.json`.

### `stacked_evidence_blocks`

Use for two grouped argument blocks: background + question, method + data,
finding + implication. Render as two clean white blocks with THU Env blue label
bars inside an EasySlides academic content shell.

Capacity:

- Page title: <= 18 Chinese chars.
- Block 1 body: <= 5 lines, about 34 Chinese chars per line.
- Block 2 body: <= 3 lines, about 34 Chinese chars per line.

Project bridge:

- `academic_scqa.flexible_canvas`
- `defense_topnav.flexible_canvas`

### `three_phase_photo_timeline`

Use for three-stage work plans, technical routes, fieldwork schedules, or
method pipelines. Preserve the source's large stage numerals with the
white-to-transparent gradient over photos.

Capacity:

- Stage title: 4-8 Chinese chars.
- Date label: <= 14 chars.
- Bullets: 2 per stage, each <= 18 Chinese chars per visual line.

Project bridge:

- `templates/charts/timeline.svg`
- `templates/charts/numbered_steps.svg`
- `templates/charts/gantt_chart.svg`

### `three_card_with_image_strip`

Use for three parallel findings, deliverables, applications, or
recommendations. Keep cards only when content is genuinely parallel.

Capacity:

- Card title: <= 8 Chinese chars.
- Card body: <= 6 lines, about 13 Chinese chars per line.

Project bridge:

- `defense_topnav.three_card_summary`
- `templates/charts/labeled_card.svg`
- `templates/charts/kpi_cards.svg`

### `dense_multi_block_matrix`

Use only when the content needs 4 compact blocks. The source slide is dense and
should not be copied literally. Prefer EasySlides' cleaner grids.

Capacity:

- Max blocks: 4.
- Block title: <= 8 Chinese chars.
- Body: <= 5 lines per block.

Project bridge:

- `defense_topnav.four_quadrant_grid`
- `templates/charts/vertical_pillars.svg`
- `templates/charts/matrix_2x2.svg`

### `photo_gallery_narrative`

Use for field images, visual cases, before/after panels, or site-photo
evidence. Do not use as a generic text page.

Capacity:

- Summary: <= 3 lines.
- Caption: <= 18 Chinese chars.

Project bridge:

- `academic_scqa.image_grid`
- `templates/charts/image_grid.svg`

## V. Capacity And Editability Gates

This template must use:

- `text_fit_policy.json` before rendering any slide.
- Native editable export (`svg_to_pptx.py --only native`) for final PPTX.
- A capacity report for each generated deck.
- A preview render pass for any body variant with images, gradients, or dense
  text.

Hard rule: if content exceeds a slot, compress, choose a lower-density body
variant, or split across slides before rendering. Do not silently shrink text
below the declared floor, and do not let fixed template geometry dictate bad
slide writing.

## VI. What Not To Reuse

- Do not use the original 8 PPT pages as the final reusable template.
- Do not preserve large photo backgrounds on every content slide.
- Do not copy dense page 6 literally.
- Do not use image-heavy page 7 for text-only content.
- Do not convert to whole-slide SVG when the user expects editable PPT.

## VII. Implementation Notes

- `module_audit` measurements were derived from
  `templates/reference/template_asset_sources/thu_env_2025/svg-flat/*.svg`.
- The source SVG for slide 4 was patched to restore the original PPTX
  gradient number treatment (`01/02/03` white -> transparent), because the
  first import flattened it to black text.
- The source asset bank remains useful as evidence, but downstream generation
  should prefer the distilled variant contracts above.
