# EasySlides project rules

## Official template policy (mandatory)

The official academic PPT template set is exactly these eight canonical IDs:

- `academic_general`
- `academic_classic`
- `academic_scqa`
- `defense_leftnav`
- `defense_topnav`
- `literature_minimal`
- `nsfc_defense`
- `thu_speech`

First confirm the production scheme. After the user chooses native editable
production, select `academic_general` when no other template is specified,
then confirm the theme color and theme image source (existing template theme
images or a newly generated topic-specific image), and inspect discipline, presenter,
presenter institution and date. Ask only for unresolved information; respect
explicit omissions and user-provided images. Explicit templates take precedence.
Read `references/default-academic-template.md` for this default's working rules.

Only these eight templates may be selected by default for a new deck or template
reuse task. `nsfc_defense` is official even though its internal QA/package
status may still say `review`; package review status does not change its project
classification. `thu_speech` is the official Tsinghua speech template and is
selected through its five-shell functional-page contract.

All other template directories, distilled variants, source-faithful candidates,
and style packs are development assets. They are not part of the default
template library and require an explicit user request before restoration or use.
Their current archive is documented outside the repository on F drive.

## Naming rule (mandatory)

Template IDs use one consistent lowercase `snake_case` naming rule. Preserve the
canonical IDs exactly; do not invent fuzzy aliases, rename official templates,
or select a development asset because its visual name appears similar.

The machine-readable source of truth is
`templates/template_policy.json`, including `default_native_template_id`.
The package registry and capability registry
must not be interpreted as permission to use a template outside the official
eight-item set. `academic_paper_report` is the former ID of `academic_general`, retained only
for compatibility. The semantic renderer resolves the historical
`templates/layouts/academic_paper_report` and
`templates/development/academic_paper_report` paths in clean clones; local
Windows checkouts may also retain compatibility junctions. New work uses
`templates/layouts/academic_general`.
The former `academic_general` pack is preserved as `academic_classic`.

## Deck-wide pagination (mandatory, all templates and production routes)

Choose one pagination contract per deck: visible/omitted slides, physical or
logical numbering, total, format, fixed textbox, alignment, font family, size,
weight and color. Do not infer these independently for each page. Explicitly
record cover/ending omissions and any intentional contrasting-footer variant.
For ImageGen, send the exact page counter and footer placement alongside the
template reference on every call. For editable reconstruction, remove source
OCR counters and create one native counter from the deck contract. Preserve the
original reference images and document this normalization in visual review.
Run the shared PPTX text-layout validator and inspect rendered footers before
delivery. Inconsistent counters are blocking. Raster-only or unrecognized
counter formats require manual contract review; an automated pass alone does
not establish pagination compliance.

## Body figures

For academic and teaching decks, use the
[image acquisition and review rules](references/image-acquisition.md#research-led-visual-variety).
Review figure-to-content fit and legibility in the final PPTX renders. Check
the full sequence for unnecessary reuse, including nonadjacent pages.
Use the selected template's rules for placement and text grouping.
