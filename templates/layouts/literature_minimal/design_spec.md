---
template_id: literature_minimal
display_name_zh: 极简文献
category: scenario
summary: Minimal blue-white literature report and paper-reading template with five reusable classic page shells.
keywords:
  - academic_report
  - literature_report
  - paper_reading
  - minimal_blue_white
  - research_report
primary_color: "#0D5DBE"
canvas_format: ppt169
replication_mode: classic
use_cases: Literature reports, paper reading, academic reports, research progress reviews
design_tone: Minimal, blue-white, restrained, spacious, academic
placeholders:
  01_cover: ["{{TITLE}}", "{{SUBTITLE}}", "{{AUTHOR}}", "{{DATE}}"]
  02_toc: ["{{TOC_ITEM_1_TITLE}}", "{{TOC_ITEM_1_DESC}}", "{{TOC_ITEM_2_TITLE}}", "{{TOC_ITEM_2_DESC}}", "{{TOC_ITEM_3_TITLE}}", "{{TOC_ITEM_3_DESC}}", "{{TOC_ITEM_4_TITLE}}", "{{TOC_ITEM_4_DESC}}", "{{TOC_ITEM_5_TITLE}}", "{{TOC_ITEM_5_DESC}}", "{{LOGO_IMAGE}}"]
  02_chapter: ["{{CHAPTER_NUM}}", "{{CHAPTER_TITLE}}", "{{CHAPTER_DESC}}", "{{LOGO_IMAGE}}"]
  03_content: ["{{PAGE_TITLE}}", "{{CHAPTER_TITLE}}", "{{KEY_MESSAGE}}", "{{CONTENT_BODY}}", "{{SOURCE}}", "{{PAGE_NUM}}"]
  04_ending: ["{{THANK_YOU}}", "{{ENDING_SUBTITLE}}", "{{AUTHOR}}", "{{DATE}}"]
---

# Literature Minimal Template - Design Specification

> A five-page classic EasySlides template for literature reports and paper-reading presentations. It is the maintained compact blue-white literature-report template.

---

## I. Template Overview

| Property | Description |
|---|---|
| **Template Name** | literature_minimal |
| **Chinese Name** | Literature Report 01 |
| **Use Cases** | 学术汇报、文献汇报、论文阅读、科研进展复盘 |
| **Design Tone** | 极简、蓝白、克制、留白充足、适合正式科研汇报 |
| **Replication Mode** | classic |

---

## II. Canvas Specification

| Property | Value |
|---|---|
| **Format** | 16:9 |
| **Dimensions** | 1280 x 720 px |
| **viewBox** | `0 0 1280 720` |
| **Background** | White |
| **Safe Area** | x: 54-1226, y: 90-660 |

---

## III. Color Scheme

| Role | Value | Usage |
|---|---|---|
| **Primary Blue** | `#0D5DBE` | Footer rule, page accents, section marks |
| **Deep Text** | `#000000`, `#0E2841` | Cover title, page title, chapter title |
| **Body Text** | `#1F2937`, `#4B5563` | Content body and metadata |
| **Muted Gray** | `#6B7280`, `#A6A6A6` | Source, English labels, secondary copy |
| **Soft Blue Surface** | `#F5F9FE` | Key message bar |
| **Light Border** | `#D9E4F2` | Flexible content container |

Use blue as structural punctuation only. Do not turn the deck into a heavy blue block layout.

---

## IV. Typography System

**Font Stack**: `Microsoft YaHei, Arial, sans-serif`

| Level | Usage | Size | Weight |
|---|---|---:|---|
| H1 | Cover / ending title | 62px | Bold |
| H2 | Chapter title | 60px | Bold |
| H3 | Content page title | 34px | Bold |
| Lead | Key message | 25px | Bold |
| Body | Main content body | 24px | Regular |
| Meta | Author, source, date | 14-20px | Regular |

Body text should not be reduced below 18px in final generated decks. Split dense material across slides instead.

### Native text-slot safety contract

The editable PPTX layer must preserve the shell geometry after PowerPoint reflows text:

- Every editable text element declares all four `data-pptx-box-*` coordinates and an explicit `data-pptx-valign`.
- Shell labels, compact controls, titles, metadata, and footer text use `data-pptx-valign="middle"` with `data-center-lock="true"`.
- `CONTENT_BODY` is the only shell slot that may use top anchoring; it remains inside the body frame and follows the declared line budget.
- One-line slots use `data-pptx-no-wrap="true"`; the slot contract truncates or redirects over-capacity copy before export.
- A text slot reserves at least 1.6 times its font size in height for one line, and multiline slots reserve the declared line count plus the line-height ratio.
- Adjacent title/description rows and ending metadata columns keep a measurable gap. Native PPTX rendering is required before delivery.

---

## V. Page Structure And Page Types

### 1. Cover Page (`01_cover.svg`)

- Centered title and subtitle.
- Uses the old wave-style blue footer with a quiet top rule; keep this cover as an abstract slot shell rather than a paper-specific instance.
- Author and date metadata only; do not show institution/unit on the cover.
- Metadata sits as two centered open-text lines above the wave footer; do not draw a surrounding metadata rectangle.

### 2. Table of Contents Page (`02_toc.svg`)

- Five section title + short description pairs.
- Uses `{{TOC_ITEM_1_TITLE}}` / `{{TOC_ITEM_1_DESC}}` through `{{TOC_ITEM_5_TITLE}}` / `{{TOC_ITEM_5_DESC}}`.
- Descriptions should stay one short line in muted gray. Keep them explanatory, not paragraph-like, so the page remains sparse and scannable.

### 3. Chapter Page (`02_chapter.svg`)

- Section transition page with `{{CHAPTER_NUM}}`, `{{CHAPTER_TITLE}}`, and `{{CHAPTER_DESC}}`.
- White canvas, centered section block, blue number tile.

### 4. Content Page (`03_content.svg`)

- Header with left `{{CHAPTER_TITLE}}` and right `{{PAGE_TITLE}}`.
- Key message bar with `{{KEY_MESSAGE}}`.
- One flexible body text box `{{CONTENT_BODY}}` inside a quiet content container.
- Footer includes `{{SOURCE}}` and `{{PAGE_NUM}}`.
- The SVG does not lock a chart, image, table, or card pattern; the generator may compose those inside the content area while preserving margins and hierarchy.

### 5. Ending Page (`04_ending.svg`)

- Centered `{{THANK_YOU}}` and `{{ENDING_SUBTITLE}}`.
- Logo image slot and compact author/date metadata.
- Uses the same blue footer shape as the cover.

---

## VI. Layout Patterns

Within the `03_content.svg` content area, the generator may use:

- Single-column body text for literature summaries.
- Two-column comparison for methods, findings, or pros/cons.
- Image plus annotation for one paper figure.
- Small card grid for three to four findings.
- Simple table for study metadata or comparison.

Keep one defensible claim per content page. If a page needs multiple figures or a dense reference table, split the material across additional `literature_minimal` content pages.

---

## VII. Spacing Guidelines

| Element | Value |
|---|---:|
| Outer page margin | 54px |
| Header height | 90px |
| Key message bar height | 74px |
| Content container padding | 34px |
| Major block gap | 28px |
| Border radius | 4-8px |

---

## VIII. SVG Technical Constraints

1. Every SVG must use `width="1280"`, `height="720"`, and `viewBox="0 0 1280 720"`.
2. Use inline SVG attributes only. Do not use `<style>`, `class`, `foreignObject`, `mask`, `script`, `textPath`, or animation tags.
3. Use `<text>` plus `<tspan>` for placeholders.
4. Use `fill-opacity` or `stroke-opacity` rather than `rgba()`.
5. Keep multiline or body-like text as a single editable PowerPoint text box with `data-pptx-textbox="true"`.
6. Image placeholders such as `{{LOGO_IMAGE}}` must remain inside the existing logo frame when provided. If no logo is specified, remove the whole logo group and do not render a default logo.
7. Rounded rectangles are hard content bounds. Any text visually paired with or overlapping a rounded rectangle must use a PowerPoint text box whose `data-pptx-box-x/y/w/h` stays fully inside that rectangle. If the text would not fit, shorten it; if there is enough space, wrap inside the same bounded text box.
8. The ending page must not use the Chinese word `聆听`; it sounds top-down in this context. Prefer `敬请批评指正！` as the default Chinese closing title. English `Thank you for listening!` is acceptable as a secondary line when useful.
9. Do not rely on PowerPoint's default top anchor or normal auto-fit to place shell text. The native text-slot safety contract above is mandatory for every new template fill.

---

## IX. Placeholder Specification

| Placeholder | Applies To | Meaning |
|---|---|---|
| `{{TITLE}}` | `01_cover.svg` | Report title |
| `{{SUBTITLE}}` | `01_cover.svg` | Report subtitle or paper topic |
| `{{AUTHOR}}` | `01_cover.svg`, `04_ending.svg` | Presenter; default to `川柏同学` when the user does not specify a presenter |
| `{{DATE}}` | `01_cover.svg`, `04_ending.svg` | Presentation date |
| `{{LOGO_IMAGE}}` | TOC, chapter, ending | Optional logo image; omit the logo group when not specified |
| `{{TOC_ITEM_N_TITLE}}` | `02_toc.svg` | One-line section title, N=1..5 |
| `{{TOC_ITEM_N_DESC}}` | `02_toc.svg` | One short muted-gray section description, N=1..5 |
| `{{CHAPTER_NUM}}` | `02_chapter.svg` | Chapter number |
| `{{CHAPTER_TITLE}}` | `02_chapter.svg`, `03_content.svg` | Chapter / section title |
| `{{CHAPTER_DESC}}` | `02_chapter.svg` | Short section description |
| `{{PAGE_TITLE}}` | `03_content.svg` | Content page title |
| `{{KEY_MESSAGE}}` | `03_content.svg` | One-sentence slide claim |
| `{{CONTENT_BODY}}` | `03_content.svg` | Flexible body/content area |
| `{{SOURCE}}` | `03_content.svg` | Citation or data source |
| `{{PAGE_NUM}}` | `03_content.svg` | Page number |
| `{{THANK_YOU}}` | `04_ending.svg` | Closing title |
| `{{ENDING_SUBTITLE}}` | `04_ending.svg` | Closing subtitle or Q&A prompt |

---

## X. Usage Instructions

Use `literature_minimal` when the user wants a sparse, reusable literature report shell. For dense evidence pages, references tables, or multi-figure analysis, keep the same template and split the material across additional content pages.
