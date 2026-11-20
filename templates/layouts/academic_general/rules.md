# Academic General — Usage Rules

The consolidated Chinese record of user requests and current implementation
parameters is [user_requirements_zh.md](user_requirements_zh.md). These rules
and the slot contracts below remain the authoring requirements; visual review
and source verification are not automatically guaranteed by the text itself.

1. This is the official default for a new native editable deck when the user
   has not specified another template. Use `templates/layouts/academic_general/`.
   Confirm production route first, then theme color and theme-image source
   (reuse the 14 discipline theme images or generate a dedicated topic image);
   inspect discipline,
   presenter, presenter school and date, asking only missing/conflicting facts.
   Explicit templates and supplied visual assets take precedence. Follow
   `references/default-academic-template.md` for the shared intake method.
2. Render through `scripts/semantic_template_renderer.py`, then use the shared
   SVG-to-DrawingML exporter. Bind content to declared `data-slot` IDs; never
   bind by DOM order or source page number.
3. Select content layouts from `body_variants.json` by story role and content
   shape. Repeat or omit layouts as necessary. The optional roadmap accepts one
   to nine consecutive real section names.
4. `TITLE` takes one or two explicit lines, as a string or list. Never rely on
   automatic wrapping of an overlong line. Follow every slot's declared capacity.
   On `cover_blue_band`, center the title block horizontally and vertically in
   the visible title band. A two-line title is one block. When `SUBTITLE` is
   supplied, center the title and subtitle together and retain their spacing
   and font sizes. Check the rendered text against the actual band bounds.
   Put a secondary topic or explanatory line in `SUBTITLE` when it serves as a
   subtitle. Use two `TITLE` lines for a main title that needs a line break.
   Do not add a horizontal divider above the cover presenter details.
5. Supply an actual figure path for the `result_figure` layout. Tables, values,
   conclusions and source citations must come from the user's evidence. Remove
   empty optional slots; do not invent data or citations. The legacy
   reference-focused ending requires `REF_1`, a real reference for the paper.
6. Pagination is deck-wide: physical slide index without zero padding; no number
   on cover, table of contents or ending. The renderer fills `PAGE_NUM`; a
   conflicting value is an error. Use a light theme-colored 48 × 48 px square
   flush with the bottom-right corner, rounded only at top-left; center the
   editable Cambria bold 16 pt numeral in both directions. Do not add a footer
   rule. Show each source on the left at its first appearance; suppress later
   repetitions while retaining evidence and figure locators in the plan.
7. Before delivery, run the shared PPTX text-layout validator and inspect the
   rendered PPTX, including the footer on every numbered page.
8. Keep the chapter title bar centred on its title text frame. The TOC uses its
   own bilingual title and gold rule. Do not add a separator bar to content headers. Render the figure-page
   `TAKEAWAY` as a native PowerPoint solid-square paragraph bullet; do not type
   the bullet into the content or add a separate PPTX marker shape.
9. Use the default PowerPoint slide background; do not add a full-canvas solid
   shape or a background image. Keep main text dark; use the selected theme and
   restrained supporting accents. The original unthemed appearance is navy blue.
10. The roadmap uses a topic-matched image on the left and gold numbered
    section titles on the right, separated by a clear gutter of at least 40
    canvas pixels. Use a separate `TOC_IMAGE` override only when
    appropriate; otherwise reuse the cover image. Crop natively in PowerPoint.
    Supply consecutive `TOC_ITEM_n_TITLE` slots starting at 1; the renderer
    distributes one to nine items vertically. When classification is uncertain,
    use the editable neutral illustration and record `needs_review`.
11. Content pages should use the page width and height to organize real
    information and vary layouts according to evidence. The existing
    `04_background.svg` variant has slots for three points, a titled three-step
    editable diagram and a takeaway; select it only when the source supports
    that structure. Do not require three points or a three-step diagram on all
    background pages, and never invent labels to fill the space. Method stages
    can carry one additional concise factual detail each.
12. Place pictures directly on the slide, without an added background panel or
    border. Keep the picture and its caption independently selectable.
13. On content pages, use a short chapter label (at most five characters) and
    the page title in the two-part header, both in Microsoft
    YaHei 28 pt. Center the white chapter label horizontally and vertically in
    its dark theme-colored rectangle. Crop the cover image to a focused central
    region behind a 75%-opaque dark theme overlay; keep the image, overlay, and
    text separately editable. An explicit `CHAPTER_IMAGE` takes priority. With
    no available image, use a solid dark header. Align both title text boxes to
    the exact same vertical position, height and header midpoint; keep their
    font, size and weight consistent and use native vertical centering. The
    contents has its own layout.
14. Place one or two explanatory paragraphs in a single editable text box below
    the content-page header. Use native solid-square PowerPoint bullets and
    Microsoft YaHei 18 pt for both bullet and text, with 1.3 line spacing.
    Align each bullet visually with its first text line. Do not type a square
    as text, add a second PowerPoint marker shape, or stack duplicate text boxes
    over the hint. Leave at least 24 canvas pixels between the header and the
    top of that text box.
15. Figure captions use KaiTi for Chinese and Times New Roman for Latin text,
    both at 14 pt. Do not force these caption fonts onto the slide footer.
16. The blue-band cover can be selected with `layout_id: cover_blue_band`;
    an unspecified, compatible cover also selects it when a topic image is
    available. Preserve explicitly selected and incompatible legacy layouts.
    Use the slot capacities in `layouts.json`,
    and keep its title, subtitle, presenter, affiliation and date editable.
    Do not copy the institution or presenter shown in the reference image.
    Its optional `BAND_IMAGE` is topic-specific, confined to the blue band,
    placed behind the text, and rendered as an editable picture with 30%
    transparency. Do not generate or bind an unrelated decorative image.
    Place a separately editable dark, theme-colored gradient rectangle over the
    picture and behind the white title: both ends are 18% opaque and the center
    is fully opaque, with a symmetric gradual transition across the band. Keep the
    existing 30% picture transparency independently adjustable.
    Choose photographic, scientific or abstract imagery and its colors to match
    the topic instead of forcing a dark-blue or technology-only motif. Check
    the white title's contrast against the selected image.
17. `cover_banners/manifest.json` is the user-approved image library. Prefer
    an explicit `discipline_code` or `discipline`, then an unambiguous topic
    match. Explicit `BAND_IMAGE` and `TOC_IMAGE` values take priority. Record
    the selection in the render manifest and review matches whose subject is
    not representative of the research. Preserve the original image; cover,
    TOC and ending slots own their native crops, with cover transparency unchanged.
18. Use `ending_blue_band` for the reference-inspired ending. `THANK_YOU` is
    required; `PAPER_TITLE`, `REPORTER`, `DATE`, `BAND_IMAGE` and
    `INSTITUTION_LOGO` are optional. Reuse the actual cover image in the ending,
    crop both to 1280 × 330, and preserve the 30% picture transparency and the
    editable symmetric dark-blue overlay. Respect an explicit ending override.
    The neutral mark is editable. Prefer an explicitly supplied logo; otherwise,
    resolve a reviewed ScanSci emblem from the presenter's unambiguous school
    metadata or affiliation. Unknown, conflicting or unavailable identities
    retain the neutral mark. Record the logo source and matching evidence.
    Never infer the presenter school from paper authors or the reference. Omit an
    unused metadata icon with its text. The lower metadata contains only the
    presenter and date; do not add a supervisor field. No source footer or page number is shown.
    Legacy reference-heavy ending payloads continue to select `ending`.
19. Do not wrap individual facts or comparison entries in repeated tinted
    rectangular cards, outlined cards, or decorative colored sidebars. Arrange
    facts through typography, alignment, whitespace, and restrained separators.
    Keep shapes that carry data, meaningful diagrams, the specified chapter
    header, and the cover/ending image bands.
20. Keep chart-adjacent annotation concise. Prefer direct data labels and avoid
    explanatory gray notes that repeat the chart, its axes, or the page's
    takeaway. Retain figure captions, source, units, comparison baselines, and
    any limitations needed to interpret the evidence; phrase them briefly and
    place them close to the relevant content. Put supporting detail in presenter
    notes when appropriate rather than adding more on-slide commentary.
21. Scientific figures and charts must be traceable to the user's materials or
    to a relevant scientific paper or scholarly tutorial. Prefer the original
    figure when it explains the subject well. Redraw a chart only from verified
    source data, preserve its meaning and mark it as redrawn or adapted; record
    the exact work and figure/table in the source manifest and cite it on the
    slide. Do not invent chart values, heatmaps, examples, or evidence to fill a
    layout, even if labelled illustrative, unless the user explicitly asks for
    a hypothetical example. If a suitable empirical figure is unavailable,
    use a source-supported, editable conceptual diagram, technical route or
    comparison table; distinguish it from an empirical result.
22. At the beginning of a new deck using this template, ask the user to confirm
    the theme color before visual planning. Present `academic_blue` (学术深蓝),
    `academic_purple` (清华风紫), `academic_green` (深绿色), and
    `technology_blue` (科技蓝) as examples; a confirmed `#RRGGBB` can also be
    used to derive a custom palette. If a color was already explicitly
    chosen, do not ask again. Record the selected `theme_palette` in the deck
    plan or `academic_brief`. Use the same palette across the cover, contents,
    content headers, and ending, while preserving white backgrounds, contrast,
    actual image colors, and figure data. Existing plans without a theme retain
    their original appearance for compatibility.
23. The color–discipline pairs in `theme_palettes.json` are preview examples
    only. In a real deck, honor the user's image and subject choices first;
    otherwise select imagery from the actual discipline or topic. Do not infer a
    discipline, institution, or school logo from the theme color.
24. Reuse `assets/theme_palette_preview.png` when presenting theme choices;
    do not regenerate the example for each deck. After selection, render the
    actual deck locally with the chosen palette and topic-specific image.
25. Check precision throughout the deck: consistent repeated typography,
    margins and baselines, and even dimensions and gaps for parallel elements.
    Inspect the native render for optical misalignment while retaining layout
    variety appropriate to the content.
26. Assume an academically experienced audience unless the user specifies
    otherwise. Do not put teaching prompts such as “如何解读”, “读图指南”,
    or “这页告诉我们” on slides. Use substantive headings that name the
    scientific question, finding, mechanism or disagreement instead.
27. Give each content page a distinct contribution to the argument. Record
    that contribution and its evidence in the deck plan. Remove paragraphs
    that merely restate the title, axes, legend, previous slide or a nearby
    number. Revisit evidence only for a new comparison or synthesis.
28. Structure a paper report around research background, related work and
    frontier, research gap, study design and methods, results, and comparative
    discussion. Do not open the body with methods or results without first
    establishing the scientific problem. Follow relevant Introduction
    references to their original papers and figures; add later studies when
    they materially inform the discussion. Represent domestic/international
    work by actual relevant contributions, without inventing geographic
    contrasts or equating author affiliation with sampling location.
29. Every body page must combine concise scientific text with a meaningful
    visual: a source figure, verified data chart, editable model/route,
    relationship diagram, or visual comparison table. No paragraph-only page
    or uniform collection of text boxes. Convert genuinely textual material
    into a structured visual when justified; decorative imagery or empty
    shapes do not satisfy the requirement for scientific evidence.
30. Explain the actual methods visually, including model inputs, units of
    analysis, transformations, inference stages, outputs and validation.
    A native editable schematic may be drawn when the paper has none; cite
    the paper/method and label the schematic as such. Do not invent model
    settings, training samples, feature values or performance. Preserve the
    distinction between separate models used at separate stages.
    A method mentioned by the user as an example is not evidence that the focal
    paper used it. Verify the focal paper before naming or illustrating a method.
31. Increase information density through complementary panels, aligned
    comparisons, parameter/assumption tables and connected evidence, while
    preserving the agreed typography and readable source axes. Use the
    working area from below the hint to above the footer. Do not fill space
    through repetition, unnecessary commentary, tiny text or fact cards.
    Vary compositions to suit their argument; avoid three successive pages
    using the same figure-left/commentary-right arrangement.
32. Ground discussion in figures from relevant external studies and compare
    study systems, response variables, scale and methods. Separate a source's
    result from the presenter's inference or proposed experiment in the plan
    and notes. A proposal may be visualized as a design, never as fabricated
    observed data. A final synthesis must add a judgment, testable question
    or implication rather than re-listing earlier facts.
33. For a figure from a paper, write its caption as a substantive figure name
    followed by the author–year citation: “A对B的影响 (Tim et al., 2025)”.
    Use a scientifically accurate title; an association must not be renamed a
    causal effect. Do not prefix the on-slide caption with “原论文图 X” or
    put the citation before the figure name. Keep the original figure/panel
    identifier in the source manifest and presenter notes. Preserve KaiTi for
    Chinese and Times New Roman for Latin text, both 14 pt. A long caption may
    break before the parenthesized citation; do not reduce its font size.
34. Use editable solid block arrows for connections between layout stages,
    matching the user reference's broad rectangular shaft and triangular head.
    Use the theme accent, no outline, and a restrained soft shadow. Keep the
    arrow centered in its inter-stage gap with space from text. The head is
    roughly one third of the total arrow length and the shaft thickness is
    44% of the head's height. At 1280 × 720, use a head height of half the arrow
    length, clamped to 16–30 px. Preserve original-paper arrows, tree branches,
    network edges and meaningful dashed/causal/feedback relations; styling a
    layout connection must not alter the scientific meaning of a diagram.
35. Apply the text hierarchy in `layouts.json#text_hierarchy` by semantic role:
    hint 20 pt with a 20 pt native square bullet; ordinary body 18 pt; subordinate
    explanation 16 pt. Body subheadings also use 18 pt, with weight for emphasis.
    Chapter/page titles remain 28 pt, figure captions 14 pt and page counters
    16 pt. Keep a single hint textbox and its 130% line spacing. Never reduce
    body text below its role's size to fit a slot; shorten or reorganize content.
    Cover/TOC/ending display typography, standalone quantitative emphasis,
    source metadata and the text embedded in original figures are separate roles.
36. A method diagram must encode the scientific operations with meaningful
    graphics, such as a matrix, model structure, grouping, map or comparison.
    Do not present six prose blocks connected by arrows as a visual workflow.
    Share column widths, illustration bounds and text baselines across parallel
    stages; use a single clear reading path and attach every branch to its
    actual upstream object. Keep only essential counts and labels on the slide,
    placing model details in notes. Mark an original schematic as a method
    schematic; illustrative cells, branches, nodes and gene tracks must never
    masquerade as observations, learned structure or measured quantities.
37. Build a solid branching connector as one closed silhouette, with one
    shared shaft width, identical arrowheads and clean tangent turns. Do not
    overlay separate stroked lines and arrow objects at junctions: mismatched
    thickness, exposed stubs, gaps and doubled shadows are visual failures.
    Apply any shadow once to the unified shape and inspect junctions enlarged
    in the actual PowerPoint render before delivery.

38. Choose the main exhibit for each new body page before placing text. Use a
    chart for quantities on a common scale, a paper figure for spatial or other
    shown patterns, and a diagram for an actual relationship or procedure.
    Reserve tables for exact lookups and comparisons across multiple fields.
    New tables use `scientific_composition` with `evidence_matrix`: a directly
    selectable PowerPoint table, strong theme-colored header, pale alternating
    rows, padded cells, and right-aligned numeric columns.
39. Review the deck in thumbnail view for recurring text-and-table or
    figure-and-commentary arrangements. Compare like-for-like exhibits on
    consistent axes and grids when this aids comparison. On sparse figure-led
    pages, enlarge the evidence figure with its labels and legend intact, and use
    the adjacent area for sourced interpretation, such as data origins and
    sample units. Keep picture and caption readable above the footer.
40. Organize substantive explanatory text into clear groups: keep each
    subheading close to its paragraph and leave a clearly larger gap before the
    next group. For the 1280×720 scientific body, leave at least 16 px between
    group text boxes (with 4 px inside a vertical heading–paragraph group).
    If needed, place each heading beside its paragraph, widen the text region
    or split the page; never shrink type or omit substantive content to fit.
    Inspect the final PowerPoint render and keep comma-separated numbers and
    Chinese closing punctuation from being stranded across lines.
    Use braces only for genuine group membership and on at most one page
    across the deck, and vary the arrangement
    with the material. Filled labels, when used, share consistent dimensions
    and are centered horizontally and vertically; labels inside circles must
    likewise be centered on both axes within the circle. Omit decorative vertical
    rules. Preserve meaningful content and agreed type sizes; change layout or
    split the page if it cannot fit. The `figure_analysis` stacked, inline and braced
    payloads are documented in `references/scientific-composition.md`.
41. Plan and review actual page-level variety across the whole deck, including
    alternating or nonconsecutive repeats. Vary structure, visual hierarchy,
    and relative positions and sizes of figures, diagrams and text according to
    the material. Changing only color, labels, braces or decorative lines does
    not create a new layout. The existing three-consecutive-page check is a
    minimum, not sufficient evidence of variety. Keep content density and a
    coherent template identity; do not invent decoration to meet a quota.
42. In a research-led deck, plan image diversity alongside layout diversity.
    Gather enough individually sourced, relevant visuals to explain distinct
    pages; vary perspective and medium when useful. Audit all body-page images
    for exact or near-duplicate reuse, including nonadjacent pages, and replace
    repetitions that do not serve the argument. Do not disrupt meaningful
    same-location time-series or template-owned cover/chapter theme imagery.
    Check the image's actual subject, time, source, credit and use conditions;
    ensure captions and notes match any replacement. Preserve text and readable
    paragraph grouping throughout.
43. Size the visible figure for the observation the audience needs to make.
    Check the actual fitted image, its important features, labels and legend
    at presentation size. Use a larger frame, a dedicated comparison or fewer
    panels if the evidence is too small. Keep comparison extent and scale
    aligned where they carry meaning. Keep captions close to their figures,
    preserve body type sizes and spacing, and review the rendered change.
44. Use editable text for standalone wording and a source figure or a native
    diagram for substantive evidence or relationships. Omit slide thumbnails
    and generic boxes joined by arrows from body evidence positions. When
    replacing such graphics, retain material information on the slide or
    in the speaker notes. State supported observations and limits directly.
