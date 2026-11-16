# Academic General

Default native EasySlides adaptation of Academic PPT Master's academic template.
The user-requested palette uses the default white PowerPoint background,
near-black body text and deep navy titles, with restrained blue, teal, amber
and muted violet accents. It is an official template at
`templates/layouts/academic_general/`, selected automatically after a native
production choice when no other template was specified. Explicit user templates
take precedence. The former ID `academic_paper_report` remains a compatibility
alias; new projects use `academic_general`. See `references/default-academic-template.md` for the full method.

The [Chinese user requirements](user_requirements_zh.md) consolidate the
requested cover, contents, content, ending, typography and evidence rules.
For new decks, confirm production route first, then theme color, discipline and
presenter metadata from inspected material. `theme_palettes.json` declares
`academic_blue`, `academic_purple`, `academic_green` and `technology_blue`;
record the chosen id as `theme_palette` in the plan (or `academic_brief`). A
confirmed custom color can be supplied as `#RRGGBB`; dark shades are derived
as needed to keep white text readable. The
semantic renderer applies the selected colors across the deck and records the
choice in its manifest. Existing plans with no color retain their original look.
The `preview_example` color–discipline pairs are illustrative only: the user
can choose any pairing or provide an image. For real decks the image follows
the user's choice or the actual subject, not the selected color.
Reuse [the saved color preview](assets/theme_palette_preview.png) when asking
for the theme; do not regenerate example slides for each new deck. The
clarification adapter exposes this asset as `preview` before the color question.
After color, ask whether to reuse the 14 discipline theme images (“主题图”)
or generate a dedicated topic image. Record `theme_image_source`; skip an
explicit prior choice or supplied image. Generate once, record `theme_image_path`
and reuse its crops across cover, TOC, chapter headers and ending. Disclose
additional generation time/usage and never silently substitute a library image.
`design_spec.md`, `layouts.json`, `body_variants.json`, `story_structure.json`
and `rules.md` are the authoring contracts. The layout SVGs have semantic slots
and are rendered by the existing `scripts/semantic_template_renderer.py`:

```powershell
python scripts/semantic_template_renderer.py templates/layouts/academic_general templates/layouts/academic_general/examples/deck_plan.json --out tmp/academic_paper_example/svg_output
python scripts/svg_to_pptx.py tmp/academic_paper_example --only native -t none -a none -o tmp/academic_paper_example/preview.pptx
python scripts/validate_pptx_text_layout.py tmp/academic_paper_example/preview.pptx
```

Each slide in `deck_plan.json` supplies a role, an optional `content_shape` or
explicit `layout_id`, and a `slot_payload`. Read slot names, required fields,
capacity and automatic numbering from `layouts.json`. The figure slot takes a
local file path relative to the deck plan. See `rules.md` before use.

For the user-requested blue-band cover, set the cover slide's `layout_id` to
`cover_blue_band`. When a topic image is selected and no cover layout is
specified, the renderer also selects this cover automatically if the supplied
fields fit it. Explicitly selected layouts and covers with incompatible legacy
fields retain their original layout. Its reusable slots are `RESEARCH_FIELD`, `TITLE`,
`SUBTITLE`, `REPORTER`, `AFFILIATION`, `DATE` and the optional
`BAND_IMAGE`; see
`examples/blue_band_cover.json`. This is the default image-enabled cover when
its fields fit; explicit alternative layouts are preserved.
When `BAND_IMAGE` is supplied, it is cropped within the blue band and exported
as a separately editable PowerPoint picture at 30% transparency.
An independently editable navy gradient rectangle sits above the picture and
below the white title: it is more transparent at both edges and opaque at the
center to improve text contrast. Its gradient stops can be adjusted in PowerPoint.
Choose imagery and colors to suit the topic; a dark-blue image is not required.
For the evolution visual, see `examples/evolution_cover.json`. Its newly
generated photographic panorama is `assets/evolution_cover_photographic.png`;
the user's earlier visual remains at `assets/evolution_cover_original.png`.
Cropping is applied by PowerPoint and can be adjusted without altering either
source image. The panorama is a conceptual illustration, not evidence of a
linear evolutionary lineage or a photograph of one historical ecosystem.

The [cover banner library](cover_banners/manifest.json) contains one
user-approved, AI-generated image for each of the 14 discipline categories,
plus a topic-specific evolution image. Browse the [preview](cover_banners/preview.html).
Content pages reuse the cover or selected topic image as a focused chapter-bar
crop under a 75%-opaque dark theme overlay. Set `CHAPTER_IMAGE` on a content
page to override the image, or set it to an empty string for a solid bar. The
PowerPoint picture crop, colored shape, and white title remain editable.

For the blue-band cover, TOC and ending, the semantic renderer selects the same
image from the declared discipline or from recognizable topic keywords. Set
`discipline_code` (e.g. `"09"` for 农学) or `discipline` (e.g. `"农学"`) at
the top of the deck plan to give the category explicitly. A manually supplied
`BAND_IMAGE` on the cover takes priority and is also used for the TOC and
ending unless either slide provides its own image. An explicit empty image slot
disables that slot's image. If the cover has no image, the ending stays blank
unless a separate image is explicitly supplied; a standalone ending can use the
topic-selected image.
The selection and matching terms are recorded in `render_manifest.json`.
If the topic is missing or ambiguous, the renderer reports `needs_review` and
uses a neutral editable TOC illustration rather than guessing a discipline.
Keyword inference is a visual aid, not an authoritative classification; set the
category explicitly when the field is cross-disciplinary or uncertain.
Paths in supplied image slots are relative to the deck plan or absolute.
The original image is preserved; the cover and TOC use different native picture
crops, adjustable in PowerPoint. Only the selected banner is copied to the deck.
See `examples/auto_discipline_cover_toc.json` for automatic selection and
`examples/discipline_cover.json` for an explicit image example.

The background layout combines three points, a titled three-step diagram and a
takeaway; fill these diagram slots with information supported by the source.
The method, table, conclusion and outlook pages also use the content area more
fully. Explicit content variants include parallel branches, a conceptual flow,
a four-stage grid, a timeline with two comparisons, comparison scorecards and
a side-by-side contrast diagram.
Choose the layout that best explains the source evidence, and vary consecutive
pages. See the included example for the diagram and optional step details.
The table of contents uses a topic-matched cropped native picture and one to
nine editable, automatically spaced section names. A clear gutter separates
the image from the list.

The default `ending_blue_band` ending adapts the supplied reference: a centered
white closing message and paper title on a navy band, with optional reporter
and date fields below. Its neutral academic mark is replaced by a supplied
`INSTITUTION_LOGO`, or by a reviewed ScanSci emblem when the presenter's school
is identified from their own institution metadata or cover affiliation. For
example, set `presenter_institution: "浙江大学"` in the plan. Paper-author and
template identity are not presenter evidence. Unclear or conflicting schools,
unavailable logos, and network failure retain the neutral mark. Manual logo
slots take priority; an explicit empty slot keeps the neutral mark without a
lookup. The logo selection and source metadata are recorded in
`render_manifest.json` and the project's `assets/logos/` inventory. See
`examples/ending_school_logo.json` for a named-school example. Its 1280 × 330
band uses the cover image with the same native crop, 30% picture transparency,
and an independently editable navy gradient. The text,
icons, band and logo remain editable, and the ending has no footer or page
number. See `examples/ending_blue_band.json`. Existing plans that contain the
legacy reference fields continue to use the previous `ending` layout.

The example plan contains labeled illustrative content, not research data.
Content pages use a two-part chapter and page header, followed by a single
native PowerPoint bullet text box with 1.3 line spacing. The square in the SVG
is an export-excluded preview. Figure captions use KaiTi for Chinese and Times
New Roman for Latin text. Content headers omit a separator bar; the chapter
title bar is centred to its title frame. Center white content-page
chapter names in a dark navy header rectangle. Each source appears in the
footer on first use only. Visible page numbers use unpadded physical indices,
centered in a light, top-left-rounded square at the bottom-right corner; the
table of contents has neither source nor page number.
The [MIT license](LICENSE) and [upstream attribution](ATTRIBUTION.md) accompany
this package. Maintainers may keep upstream SVGs and specifications locally in
`source/` for comparison during review. This optional reference folder is not
required by the runtime and is omitted from the plugin bundle.
