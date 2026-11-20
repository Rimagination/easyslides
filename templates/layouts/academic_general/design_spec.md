---
template_id: academic_general
display_name_zh: 学术通用汇报
category: scenario
summary: Default native academic report template with discipline assets, confirmed colors, visual methods and exact typography.
keywords: [paper_reading, journal_club, research_report, light_navy]
primary_color: "#102F4A"
canvas_format: ppt169
replication_mode: slot_guided_mirror
---

# Academic General — Design Specification

This official native-default template adapts Academic PPT Master's ten
`academic_paper_report` source pages to EasySlides named slots and adds six
reusable content variants and two user-requested cover/ending shells. Its
identity combines a blue-band cover and ending, an image-led contents page,
two-part content headers, and an evidence-first academic visual style. Content
headers omit the original vertical title marker; the chapter-transition layout
can retain its own marker and large pale number. Content pages use the available
canvas for evidence and diagrams, with comfortable margins. Upstream pages and
specifications may be kept locally in `source/` for maintainer reference; the
runtime does not require them. The package carries the upstream MIT license
and attribution at its root.

See [user_requirements_zh.md](user_requirements_zh.md) for the consolidated
user requirements and [rules.md](rules.md) for the authoring rules. The
current slot geometry and capacities remain defined by `layouts.json`.
For a new deck, confirm native versus image production first, then the palette
and source-located presenter/discipline information; record `theme_palette`. The
`theme_palettes.json` catalog declares the supported theme variants. The colors
listed below describe the original academic-blue appearance.

## Canvas and colors

Use a 1280 × 720 canvas with PowerPoint's default white slide background; do
not place a slide-sized background shape or picture. Titles are deep navy
`#102F4A`, body copy is near-black `#171C22`, and secondary copy and footers use
`#53616E`. Use blue `#2F759B`, teal `#3B817B`, warm amber `#B98B4F`, and muted
violet `#7473A1` as restrained accents. Organize content on the white slide with
typography, alignment, meaningful connectors and occasional fine rules. Avoid
repeated tinted rectangular cards, outlines and colored sidebars around individual
facts. Keep rectangles that encode actual data or serve the explicitly requested
header and cover/ending bands. Do not reintroduce fabricated chart values or the
original decorative progress bar.

Use native editable text and the font stacks specified in the SVGs. Follow
`layouts.json` for slot capacities; split or shorten copy when it exceeds a
slot. `TITLE` accepts up to two explicitly separated lines. The existing
`04_background.svg` layout combines three short points with a titled, three-step
editable diagram and a full-width takeaway; use it only when the source supports
that structure. Other background layouts can use different evidence and
geometry. Supply real labels for diagrams; do not invent content simply to fill
space. Method pages can include an additional factual detail for each step. The
table, conclusion and outlook layouts use the content area vertically so that
short content does not cluster in one corner.

Content pages use a two-part header: a chapter name of at most five
characters in white on a dark theme-colored rectangle on the left, and the
dark page title on a pale background on the right, both Microsoft YaHei
28 pt. Center the chapter name horizontally and vertically in its rectangle.
Both title boxes share the same top, height and vertical midpoint of the header,
with identical font, size and weight and PowerPoint vertical centering.
Place a focused crop of the cover asset under a 75%-opaque dark theme overlay;
keep the crop, overlay, and label separately editable. With no selected image,
the header is solid. An explicit `CHAPTER_IMAGE` overrides the cover image.
The table of contents retains its own layout. Below each content header,
one editable text box holds one or two concise paragraphs in Microsoft YaHei
20 pt, with a native solid-square PowerPoint bullet at 20 pt and 1.3 line
spacing. The SVG square is only a preview and is not exported as a shape. The
figure caption uses KaiTi for Chinese and Times New Roman for Latin text, both
at 14 pt. Content headers have no vertical separator. Leave a clear gap between
the header and the hint box, and reserve enough room for two bullet paragraphs.
The chapter layout retains its existing title marker; the table of contents
uses its own bilingual header and gold rule without a title marker.
The cover has no horizontal divider above its presenter details.
The fixed body hierarchy is declared in `layouts.json#text_hierarchy`: hints
20 pt, ordinary body and bold body subheadings 18 pt, subordinate explanations
16 pt. Use semantic roles consistently; shorten or relayout content instead of
shrinking fonts. Titles remain 28 pt, captions 14 pt and counters 16 pt. Source
metadata, standalone quantitative emphasis and cover/TOC/ending display type
retain their own roles. Preserve typography embedded in original paper figures.
Place figures directly on the slide without an added background rectangle or
border. Keep the picture and caption as separately selectable objects.

## Page roster

| File | Role | Best for |
| --- | --- | --- |
| `01_cover.svg` | cover | Paper title, authors and presenter metadata |
| `17_cover_blue_band.svg` | cover | User-requested centered cover with a deep-blue title band and optional topic image |
| `02_toc.svg` | toc | Numbered paper-reading roadmap with one to nine sections |
| `03_chapter.svg` | chapter | A section transition with a pale large numeral |
| `04_background.svg` | content | Research background, gap and core question |
| `05_method_pipeline.svg` | content | Four-stage study or method pipeline |
| `06_result_figure.svg` | content | One supplied figure, caption and takeaway |
| `07_result_table.svg` | content | A comparison table and one evidenced result |
| `08_conclusion.svg` | content | Conclusions, implications and a highlighted finding |
| `09_outlook.svg` | content | Reference value, limitation and next step |
| `10_ending.svg` | ending | Legacy closing, key references and presenter contact |
| `18_ending_blue_band.svg` | ending | Centered closing statement, paper title and optional presenter details |
| `11_background_parallel.svg` | content | Three facts and an editable four-branch diagram |
| `12_background_equation.svg` | content | Concept flow and three concise explanations |
| `13_method_grid.svg` | content | Four stages presented in a two-by-two grid |
| `14_method_timeline.svg` | content | Four-stage timeline and two contextual comparisons |
| `15_result_scorecards.svg` | content | An open comparison table with four rows and two measured outcomes |
| `16_background_contrast.svg` | content | Side-by-side comparison with an editable schematic |

Select and repeat pages according to content; the original ten-page sequence is
not a required deck length. Follow `story_structure.json` and `rules.md`.
The optional blue-band cover reproduces the user-supplied reference
`source/blue_band_cover_reference.jpg`: its top
research-field line, full-width blue title panel, centered white title and
subtitle, and lower presenter, affiliation and date. The band and labels are
editable; no personal or institutional information is copied from the reference.
The title uses a 116 px frame for one line and a 180 px frame for two lines at
the same font size. The semantic renderer centers the full title block within
the 330 px band after resolving optional slots. A visible subtitle joins the
block with its existing spacing. The SVG baselines and editable PowerPoint
frames move together.
Select it with `layout_id: cover_blue_band`. When a topic image is selected
and the cover layout is unspecified, the renderer also chooses this cover if
the supplied fields fit; an explicit layout or incompatible legacy fields keep
their existing layout. The slide background remains PowerPoint's default white.
An optional `BAND_IMAGE` slot places a topic-relevant image strictly inside
the blue band, center-cropped and in front of the blue fill but behind all
text, with PowerPoint picture transparency set to 30% (70% opacity).
The supplied image remains a separately editable native picture. An independent
native gradient rectangle covers the band above the image and below the title.
In the original blue palette it is navy `#08264D`; other selected palettes
replace the hue while retaining the same opacity stops: 18% at both edges and
fully opaque at the horizontal center. Keep the symmetric gradient and its stops
editable in PowerPoint. When the image is omitted, retain the gradient over the band.
Select the image's subject, medium and colors from the actual presentation
topic: it may be a photograph, a scientific illustration, or an abstract visual.
Do not impose a dark-blue image or reuse technology imagery for unrelated
subjects. Check that the title remains legible at the specified transparency.
`cover_banners/manifest.json` lists 14 user-approved generated images by
discipline and a topic-specific evolution image. Use the deck's explicit
discipline when provided, otherwise infer from the topic and field when the
keyword evidence is unambiguous. The semantic render manifest records the
selection and its basis. User-provided `BAND_IMAGE` and `TOC_IMAGE` slots take
priority; the actual cover image also supplies the default TOC and ending
picture. An empty cover image leaves the ending unillustrated unless overridden. An
unknown or tied subject is marked for review instead of guessed. These are
decorative visuals, not research evidence. Preserve the original image and use
native, adjustable PowerPoint crops for both frames.
The roadmap retains its bilingual title, fine gold rule and editable numbered
section names; its left image uses the matching cover asset with its own crop.
Keep at least 40 canvas pixels between the image and the section-number column.
If no image can be selected, a neutral editable network fills the visual area.
One to nine consecutive section slots are supported. The renderer distributes
occupied rows across the available height and removes unused numbers.
Select content variants according to the argument and evidence; do not repeat
the same page composition across a long run merely to fill space.

The default ending follows the supplied reference: PowerPoint's white slide
background, a fine navy line, a full-width navy middle band, a centered white
closing statement and paper title, and up to two lower metadata columns with
editable icons. A neutral editable book mark sits across the line and band;
replace it with the user-supplied `INSTITUTION_LOGO` or a reviewed ScanSci
emblem for an unambiguously identified presenter school. Record the school
evidence and logo source; do not infer it from the paper or reference image.
Unknown, conflicting or unavailable identities retain the neutral mark. The
ending band matches the cover's 1280 × 330 crop, carries the same editable image
at 30% transparency, and uses the same dark symmetric gradient for legibility.
The band, mark, icons and text remain independently editable. Omit unused metadata
and their icons; the ending has no footer or page number. Existing ending
payloads containing reference fields continue to use `10_ending.svg`.

## Scientific narrative and body composition

Deck-wide variety concerns the composition of the whole page: image/text
placement and proportion, hierarchy, and the choice of comparison, diagram,
process or figure-led arrangements. Changing only decorative details does not
change the layout. Review thumbnails for overuse throughout the deck, including
alternating repeats, while matching each page to its content and retaining a
coherent theme and substantive information.

Visual variety includes image subject and provenance, not only placement.
For researched subjects, gather a diverse, relevant source set: for example,
field photographs, aerial images, maps, archival objects, and scientific
diagrams when each helps explain its page. Review the full deck for reused or
visually near-identical body images. Reuse a visual only for a clear narrative
reason, such as a deliberately continued case, and prefer a different view when
that preserves meaning. Legitimate same-place temporal comparisons and the
template's common theme imagery remain intact. Document credits and image dates.

Give evidence space according to the feature the audience needs to see.
Use the fitted picture area to judge scale. On a two- or three-panel comparison,
the template sizes the title, caption and interpretation bands to their actual
text. It gives the remaining space to aligned, aspect-preserving figures and
keeps their lower edges next to the caption band. Use a larger composition or
fewer panels if source annotations remain too small. For a visual with no
independent evidence or relationship, use readable native copy and choose
another relevant visual when appropriate.

Connections between layout stages use editable solid block arrows: broad shaft,
triangular head, theme accent, no outline and a light soft shadow. Center them
in the available gap. The head occupies one third of the length; the shaft is
44% of the head height. On the 1280 × 720 canvas, head height is half the arrow
length, clamped to 16–30 px. Scientific relations retain their meaning: preserve
original-paper arrows, tree branches, network edges and meaningful dashed or
feedback connections.

Paper-derived figure captions use a substantive name followed by a citation,
for example “A对B的影响 (Tim et al., 2025)”. Use wording appropriate to the
evidence, including “关系” or “关联” for an association. Original figure and
panel identifiers belong in the notes and source manifest, rather than a
prefix such as “原论文图 X”. Captions retain KaiTi for Chinese and Times New
Roman for Latin text at 14 pt; wrap before the citation when necessary.

The default audience is academically experienced. Write scientific claims and
questions, not classroom prompts such as “如何解读” or “读图指南”. Each page
must add a distinct piece of evidence, comparison, mechanism or judgment;
repeating a title, legend, number or prior conclusion is not information gain.

For a paper report, establish the background and related frontier before the
research gap and design, then present methods, results and comparative
discussion. Follow the Introduction's references to original figures and use
relevant external-study figures in discussion. Record actual locations and
affiliations separately; do not manufacture national contrasts.

Every body slide combines concise text with scientific visual content.
Source figures, verified data plots, native model schematics, technical routes,
relationship diagrams and visual comparison tables are valid; paragraph-only
pages and decoration standing in for evidence are not. Method schematics must
faithfully show the study's actual inputs, analysis units, model stages and
outputs, with no invented settings or accuracy. Identify a newly drawn
explanation as a schematic based on its scientific source.

Use complementary panels and structured comparisons to fill the working area
between hint and footer. Preserve readable typography and source axes; do not
use tiny fonts, repeated fact cards or redundant prose as density. Match each
composition to its role and avoid three consecutive figure-left/commentary-right
pages. Keep figure-specific detail in notes when it does not advance the argument.
Distinguish source results, presenter's inference and proposed experiments in
the plan and notes; proposed work must never be depicted as observed data.

## Pagination

The cover, table of contents and ending omit page numbers. The table of
contents also omits the source footer. Every other page uses its physical
slide index without padding or a total: for example `3` or `11`. A 48 × 48 px
square sits flush at (1232, 672), with only its top-left corner rounded. Use
the light theme border color for the square and the theme accent for a native,
centered Cambria bold 16 pt numeral. The semantic renderer owns `PAGE_NUM` and
rejects inconsistent caller values. There is no footer divider. Show a source
on the left on first appearance only; retain distinct citations and scientific
figure locators in the content and source records. Validate the exported PPTX
and inspect rendered footers before delivery.

For content-rich explanations, use clearly separated heading–paragraph groups;
on the 1280×720 scientific body, keep group text boxes at least 16 px apart
and vertical headings 4 px from their own paragraph. Inline headings can retain
the explanation and a clear group gap when a vertical stack cannot fit. Check
actual PowerPoint renders and keep numbers and Chinese punctuation together.
When there is a real grouping relationship, a brace can join related points on
at most one page across the deck.
Filled labels use consistent geometry and centered text in both directions;
text inside a circle is also centered horizontally and vertically within it,
without an ornamental vertical line. Retain the relevant explanation at the
specified type sizes; choose a different composition or split the page if needed.
The editable figure-analysis variants and constraints are defined in
`references/scientific-composition.md`.
