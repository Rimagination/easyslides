---
template_id: defense_topnav
display_name_zh: 顶栏答辩
category: scenario
summary: Source-faithful academic-blue thesis defense template with a dynamic top navigation bar.
keywords:
  - thesis_defense
  - defense
  - academic_blue
  - top_navigation
  - source_geometry
primary_color: "#183A6A"
canvas_format: ppt169
replication_mode: classic
use_cases: Thesis defense, proposal defense, opening defense, research progress reports
design_tone: Academic, calm, blue-white, structured, source-faithful
placeholders:
  01_cover: ["{{TITLE}}", "{{SUBTITLE}}", "{{PRESENTER}}", "{{ADVISOR}}", "{{DATE}}"]
  02_toc: ["{{SECTION_1}}", "{{SECTION_2}}", "{{SECTION_3}}", "{{SECTION_4}}", "{{SECTION_5}}", "{{SECTION_6}}"]
  02_chapter: ["{{CHAPTER_NUM}}", "{{CHAPTER_TITLE}}", "{{CHAPTER_DESC}}"]
  03_content: ["{{ACTIVE_SECTION_LABEL}}", "{{PAGE_TITLE}}", "{{KEY_MESSAGE}}", "{{CONTENT_BODY}}", "{{PAGE_NUM}}"]
  04_ending: ["{{CLOSING_TITLE}}", "{{CLOSING_SUBTITLE}}", "{{PRESENTER}}", "{{ADVISOR}}", "{{CONTACT}}"]
---

# Defense Topnav Template - Design Specification

`defense_topnav` distills the academic-blue top-navigation PPTX source into five reusable EasySlides shells while preserving the source deck's fixed geometry where it matters: the cover horizontal blue band, the TOC left blue panel, the six-part top navigation, and the gray key-message bar. The content page intentionally leaves one open, unframed body canvas so figures, card groups, comparisons, timelines, and tables can be composed per slide instead of being locked to one visible box. The content footer keeps only the page number so slide-level synthesis lives in `KEY_MESSAGE`, not in a second bottom summary strip. The closing page is intentionally differentiated with an asymmetric left blue panel and right-side closing text so it does not feel like a duplicate cover.

## Template Contract

| Property | Value |
|---|---|
| Template ID | `defense_topnav` |
| Source Style | academic-blue top navigation defense deck |
| Replication Mode | `classic` |
| Canvas | 1280 x 720, 16:9 |
| Primary Color | `#183A6A` |
| Accent Surface | `#E7E6E6` |
| Runtime Surface | five SVG shells plus top-navigation state JSON |
| Dynamic Component | `navigation_states.json` controls the dynamic top navigation active tab |

## Theme Palettes

`defense_topnav` defaults to `academic_blue`, matching the source PPTX and the `primary_color` frontmatter. It also exposes three alternate academic color families through `theme_palettes.json`:

| Palette ID | Display Name | Primary |
|---|---|---|
| `academic_blue` | Academic Blue | `#183A6A` |
| `wine` | Academic Red | `#8B0012` |
| `academic_purple` | Academic Purple | `#80308B` |
| `academic_green` | Academic Green | `#016F35` |

The opt-in `thesis_navy_v4` style profile is declared in
`component_styles.json`. It is intended for the `cn_degree_defense_v4`
scenario variant and keeps the editable SVG/DrawingML route unchanged. Its
content typography target is 32pt page titles, 21pt body text, and 14pt
captions/tables; its semantic colors are title `#0A3476`, body/caption/table
text `#000000`, secondary text `#333333`, accent `#1C8B92`, light border
`#C8D5E6`, white page background, and `#F5F6F8` panels.

Palette switching is semantic. Replace the five theme roles as a set: `primary`, `primary_dark`, `soft_surface`, `border`, and `emphasis_text`. Do not recolor immutable white surfaces, black body text, muted gray inactive text, or raster source figures when applying an alternate palette.

## Page Shells

| SVG | Role | Source-Faithful Fixed Geometry |
|---|---|---|
| `01_cover.svg` | cover | source blue horizontal band, centered title/subtitle divider, three equally spaced bottom metadata columns |
| `02_toc.svg` | table of contents | source left blue panel plus six large numbered TOC items |
| `02_chapter.svg` | section opener | TOC-style blue left panel adapted for chapter breaks |
| `03_content.svg` | reusable content page | source six-item top nav, gray key-message bar, invisible expanded content-area guide, bottom page number only |
| `04_ending.svg` | closing | asymmetric left blue panel, right-side closing title/subtitle, three equally spaced bottom metadata columns; default `CLOSING_TITLE` is `恳请老师批评指正！`, and the third metadata item labels `CONTACT` as `专业：` |

## Dynamic Top Navigation

The content shell uses one shared top navigation bar and ships with section 1 active. The generator selects a `navigation_variants` entry from `navigation_states.json`, then updates the active tab position, active label/subtitle text, and active/inactive text fills.

Shape invariants:

- Keep `top-nav-surface`, `nav-logo-frame`, `nav-logo-mark`, and all nav label x positions fixed.
- Treat `nav-logo-frame` as a circular school-emblem placeholder; keep the doctoral cap mark unless a real logo is supplied.
- Move only `nav-active-tab` when switching the active section.
- Keep the active tab white with blue title/subtitle text.
- Keep inactive titles white and inactive English subtitles at 40% opacity.
- Do not duplicate `03_content.svg` for each chapter.

Default section order:

1. 研究背景及现状
2. 研究目标和内容
3. 研究方法与思路
4. 关键技术与创新
5. 已开展工作
6. 预期成果

## Layout Patterns

`03_content.svg` intentionally contains only one open `CONTENT_AREA`. The area marker is invisible in the SVG; it exists as a layout guide for generators, not as visible slide chrome. The footer keeps only `PAGE_NUM`; do not add a fixed bottom keyword, source, or summary strip. Choose one body model from `body_variants.json` after deciding the slide's claim and evidence shape:

- Use `PAGE_TITLE` as the short running title, not the full slide claim.
- Use `KEY_MESSAGE` as the more detailed one-sentence claim; it must not simply repeat `PAGE_TITLE`.
- Align `PAGE_TITLE` and `KEY_MESSAGE` to the same vertical center line with text boxes set to middle vertical alignment; keep `KEY_MESSAGE` inset at least 24px from the gray bar's left edge.
- `flexible_canvas` for default text, mixed text/image, or custom figure composition.
- `three_card_summary` for three parallel findings, needs, contributions, risks, or feasibility points.
- `figure_with_notes` for one dominant figure and concise interpretation notes.
- `two_column_compare` for contrastive arguments.
- `figure_left_text_right` for one evidence object plus explanation.
- `process_timeline` for methods, workflows, or schedules. Sequential circular nodes must be visibly connected by a line through the actual node centers; calculate the line from the rendered first and last nodes so variable counts remain connected.
- `table_matrix` for structured evidence.
- `four_quadrant_grid` for four modules, metrics, or contribution blocks.

Layout selection must vary with the information being expressed. Dense argument pages should be text-first with hierarchy; relationship or process pages should become flows, timelines, mechanism diagrams, or mind-map-like groupings; image-led pages should let the figure occupy the dominant area with concise notes. Do not make every content page feel like the same sparse card layout.

When source material includes a figure or table image, preserve a short visible name for that exhibit. Put figure names below the image and table names above the image.

## Visual Rules

- Preserve source coordinates for the TOC left panel, top navigation, key-message bar, page number, and cover band. Keep the ending page visually distinct from the cover by using the left-panel closing composition.
- Keep cover and ending metadata text in the canvas coordinate system: the three text boxes must be centered on x=320, 640, and 960, while decorative icons may remain in translated groups. Do not place an editable metadata text box with `data-pptx-box-x="0"` inside a translated column group.
- Use `#183A6A` for all primary bars, card labels, metadata icons, and active navigation text.
- Use `#E7E6E6` only for the key-message bar and restrained internal composition surfaces.
- Use `theme_palettes.json` as the source of truth when generating an alternate colorway; keep the default `academic_blue` source-faithful.
- Keep content below y=118 so it never collides with the navigation bar.
- Body text should remain at or above 18px in final PPTX output.
- Prefer splitting dense material over shrinking text below the floor.
- Closing pages must not contain the Chinese word `聆听` or any Chinese expression containing `聆听`. English `listening` remains allowed. Use `恳请老师批评指正！` as the default Chinese closing title unless the user provides another academically appropriate line.

## Required QA

- Run `python scripts/svg_quality_checker.py templates/layouts/defense_topnav --template-mode --format ppt169`.
- Run the template library test that covers `defense_topnav`.
- For generated decks, inspect rendered previews for all active navigation states used in the deck.

## SVG Technical Constraints

1. Every SVG uses `width="1280"`, `height="720"`, and `viewBox="0 0 1280 720"`.
2. Use inline SVG attributes only. Do not use `<style>`, `class`, `foreignObject`, `mask`, `script`, external raster dependencies, or animation tags.
3. Use `{{PLACEHOLDER}}` text tokens inside `<text>` or `<tspan>`.
4. Bounded editable text should carry `data-pptx-textbox="true"` and explicit `data-pptx-box-*` metadata.
5. The active navigation state must match the slide chapter.

## Sidecars

| File | Purpose |
|---|---|
| `layouts.json` | Declares the five-shell classic template surface and slot lists. |
| `navigation_states.json` | Machine-readable top-navigation tab geometry and active states. |
| `body_variants.json` | Reusable compositions inside the open content area. |
| `component_styles.json` | Shared geometry tokens for navigation, flexible body compositions, TOC, and footer. |
| `theme_palettes.json` | Built-in semantic color families for academic blue, wine, academic purple, and academic green. |
| `rules.md` | Hard generation rules for preserving source geometry. |
