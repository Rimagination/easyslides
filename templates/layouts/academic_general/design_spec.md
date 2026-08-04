---
template_id: academic_general
display_name_zh: 学术通用
category: general
summary: General academic base for research talks, course reports, progress reviews, paper explainers, and scholarly exchange.
keywords:
  - general_academic
  - Audience-State-Transfer
  - SCQA
  - research-oriented
  - neutral_base
primary_color: "#003366"
canvas_format: ppt169
replication_mode: classic
use_cases: Research talks, course reports, progress reviews, paper explainers, scholarly exchange
design_tone: Professional, rigorous, audience-facing, AST/SCQA-guided
---

# Academic General - Design Specification

> Neutral general-purpose academic shells for research talks, course reports,
> progress reviews, paper explainers, scholarly exchanges, and thesis-adjacent
> summaries when no narrower scenario template is selected.

---

## I. Template Overview

| Property | Description |
|---|---|
| Template Name | `academic_general` |
| Category | General academic base |
| Use Cases | General academic presentations, research progress reports, course reports, paper explainers, thesis-adjacent summaries, scholarly exchange |
| Design Tone | Professional, rigorous, research-oriented, audience-facing, clear hierarchy |
| Theme Mode | Light theme with white background and dark-blue title bar |

## I-A. Academic Orchestration Contract

Read `references/academic-orchestration.md` before planning with this template.
`academic_general` follows a human-centered academic contract:

- Start with **Audience-State-Transfer**: identify the audience, initial state,
  desired state, core tension, and slide-by-slide transfer path.
- Use **SCQA** as the default academic spine: Situation, Complication,
  Question, Answer. Treat it as a story path, not as visible section labels.
- Each content page should create one audience-state shift and carry one
  defensible claim supported by source-linked evidence or clear reasoning.
- Visible slide text is audience-facing. Avoid developer-facing language such
  as template, slot, placeholder, executor, renderer, generation, pipeline, or
  implementation unless the talk is explicitly about software development.

---

## II. Canvas Specification

| Property | Value |
|---|---|
| Format | Standard 16:9 |
| Dimensions | 1280 x 720 px |
| viewBox | `0 0 1280 720` |
| Page Margins | Left/right 40px, top 0px, bottom 35px |
| Safe Area | x: 40-1240, y: 70-665 |

---

## III. Color Scheme

| Role | Value | Usage |
|---|---|---|
| Primary dark blue | `#003366` | Header background, chapter surfaces, main headings |
| Accent blue | `#0066CC` | Card borders, icons, secondary decorations |
| Accent red | `#CC0000` | Key emphasis and left decorative bar |
| Light blue-gray | `#E8F4FC` | Key-message bar and calm evidence surfaces |
| Background white | `#FFFFFF` | Main page background |
| Primary text | `#333333` | Body content |
| Secondary text | `#666666` | Captions and annotations |
| Muted gray | `#999999` | Footer and auxiliary info |
| Card gray | `#F5F7FA` | Card inner backgrounds |
| Border gray | `#D0D7E0` | Dividers and soft borders |

---

## IV. Typography System

Use `"Microsoft YaHei", Arial, sans-serif`.

| Level | Usage | Size | Weight |
|---|---|---|---|
| H1 | Cover main title | 56px | Bold |
| H2 | Page title | 28px | Bold |
| H3 | Chapter title | 56px | Bold |
| H4 | Card title | 24px | Bold |
| Body | Main content | 18px | Regular |
| Highlight | Data or key number | 36px | Bold |
| Caption | Notes and sources | 14px | Regular |
| Footer | Page number and copyright | 12px | Regular |

---

## V. Page Structure

| Area | Position / Height | Role |
|---|---|---|
| Header | y=0, h=70px | Page title and section identity |
| Key Message Bar | y=70, h=50px | Conclusion or audience-state shift |
| Content Area | y=135, h=515px | Main claim, evidence, and explanation |
| Footer | y=665, h=55px | Source, section name, page number |

Decorative elements:

- Left red bar: `#CC0000`, 6px wide, used for header and emphasis.
- Blue border: `#0066CC`, used for card borders and selected rules.
- Decorative divider: `#0066CC`, paired with restrained dots or line accents.

---

## VI. Page Types

| SVG | Role | Description |
|---|---|---|
| `01_cover.svg` | cover | Title, subtitle, presenter, affiliation, date, and optional logo. |
| `02_toc.svg` | toc | Two-column agenda for major audience steps or academic sections. |
| `02_chapter.svg` | chapter | Major audience-state transition or section opener. |
| `03_content.svg` | content | Reusable claim-plus-evidence shell with key-message bar and footer. |
| `04_ending.svg` | ending | Takeaway, thanks, contact, or next-step closing page. |

---

## VII. Layout Patterns

| Pattern | Use Cases |
|---|---|
| Single column centered | Cover, ending, one key point |
| Two-column cards | TOC, paired concepts, two evidence groups |
| Left-right split 5:5 | Comparison display |
| Left-right split 4:6 | Image-text or figure-explanation layout |
| Card grid | Research content list or categorized evidence |
| Timeline | Research progress or chronological development |
| Table | Data comparison and experiment results |
| Claim + evidence | One main finding with figure, table, or reasoning block |
| SCQA transition | Situation-to-gap, gap-to-question, or answer synthesis |

---

## VII-A. Content Composition Contract

`academic_general` is a bounded component-first template. A content page keeps
the common running title, central message, footer, and page number, then selects
one declared body variant:

| Variant | Use when the page needs |
|---|---|
| `figure_evidence` | One primary figure and three concise observations |
| `comparison_synthesis` | Two alternatives followed by a decision |
| `process_outcome` | Three ordered steps and their shared outcome |
| `metrics_evidence` | Three metrics explained by two evidence rows |
| `evidence_argument` | A text-rich claim supported by three auditable arguments |
| `table_decision` | A compact 3 by 3 decision matrix |
| `open_component_composition` | An explicitly requested arrangement of registered local components |

The last route is deliberately bounded: it may use only components registered
by `academic_general`, and every component frame must remain inside the content
body canvas. It is not a route for importing a global card library or changing
the template's visual tokens.

The body canvas is a planning region, not a visible rectangle. No helper frame,
dashed outline, or placeholder label may appear in the exported slide.

---

## VIII. Spacing Guidelines

| Element | Value |
|---|---|
| Card gap | 20px |
| Content block gap | 24px |
| Card padding | 20px |
| Card border radius | 8px |
| Icon-to-text gap | 12px |

---

## IX. SVG Technical Constraints

Mandatory rules:

1. viewBox: `0 0 1280 720`.
2. Use `<rect>` elements for backgrounds.
3. Use `<tspan>` for text wrapping; do not use `<foreignObject>`.
4. Use `fill-opacity` / `stroke-opacity` for transparency; do not use `rgba()`.
5. Prohibited: `mask`, `<style>`, `class`, `textPath`, `animate*`, and `script`.
6. `clipPath` is allowed only on `<image>` under `shared-standards.md` section 1.2.
7. `marker-start` / `marker-end` are conditionally allowed when marker shapes follow `shared-standards.md` section 1.1.

PPT compatibility:

- Do not use group opacity; set opacity on each child element individually.
- Use overlay layers for image transparency.
- Use inline styles only; do not use external CSS or `@font-face`.

---

## X. Placeholder Specification

Templates use `{{PLACEHOLDER}}` format placeholders. These are production
anchors, not visible slide copy.

| Placeholder | Description |
|---|---|
| `{{TITLE}}` | Main title |
| `{{SUBTITLE}}` | Subtitle |
| `{{AUTHOR}}` | Presenter name |
| `{{ADVISOR}}` | Optional advisor or mentor |
| `{{INSTITUTION}}` | University, lab, organization, or affiliation |
| `{{DATE}}` | Presentation date |
| `{{PAGE_TITLE}}` | Short running title |
| `{{SECTION_NUM}}` | Section number |
| `{{CHAPTER_NUM}}` | Chapter number |
| `{{CHAPTER_TITLE}}` | Chapter title |
| `{{CHAPTER_DESC}}` | Chapter description |
| `{{KEY_MESSAGE}}` | Conclusion or audience-state shift |
| `{{PAGE_NUM}}` | Page number |
| `{{SOURCE}}` | Data or source note |
| `{{SECTION_NAME}}` | Section name in footer |
| `{{TOC_ITEM_N_TITLE}}` | TOC item title |
| `{{TOC_ITEM_N_DESC}}` | TOC item description |
| `{{THANK_YOU}}` | Closing message |
| `{{ENDING_SUBTITLE}}` | Closing subtitle or takeaway |
| `{{CONTACT_INFO}}` | Contact information |
| `{{EMAIL}}` | Email address |
| `{{COPYRIGHT}}` | Copyright or source note |
| `{{LOGO}}` | Logo image or text fallback |

---

## XI. Human-Facing Composition Rules

1. Write for the audience's next judgment, not for the production process.
2. Use conclusion-style page titles; avoid vague labels such as "Background"
   unless paired with a clear claim.
3. Keep one main idea per slide. If a slide contains two state shifts, split it.
4. Prefer source-faithful figures, tables, and captions for academic evidence.
5. Use decorative tags and arrows only when they clarify the argument path.
6. Use the running title for the page topic and the key-message rail for the
   smallest defensible conclusion. Do not repeat one as the other.
7. Keep the content-page running title on one visual line. Shorten it rather
   than wrapping it into the content area.
8. Text in a declared centered container must use native middle vertical
   alignment with its text center aligned to the container center.

---

## XII. Template Boundaries

- `academic_general` is the neutral academic fallback. Prefer a narrower template
  such as `literature_minimal`, `defense_leftnav`, or `defense_topnav` when the
  user explicitly selects that scenario.
- The visual shell provides hierarchy and rhythm; the academic scenario and
  source material define the argument.
- For mature source materials, preserve source claims, figures, tables,
  captions, and citations. Add external material only when requested.
- When the requested visual form is unclear, ask the user to choose between
  the relevant declared variants before generating the page.
