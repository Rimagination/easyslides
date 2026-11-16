# Scientific body payloads

Use `authoring_contract: "academic_native.v1"` on new native academic plans.
Keep the existing deck-plan fields. For a body slide set
`layout_id: "scientific_composition"`, `content_shape: "scientific_composition"`,
`page_brief: {question, information_gain, visual_rationale}` and `composition`.
Header payload contains `CHAPTER_LABEL` (≤5 Chinese characters), `PAGE_TITLE`
(28 pt), `KEY_MESSAGE` (20 pt, one textbox, explicit 1–2 lines), and optional
`SOURCE`. Pagination is template-owned. The renderer inherits the chosen
discipline image and theme color. It does not invent scientific content.

Scientific figures have this record shape:

```json
{"path":"assets/figure.png", "source_id":"paper", "aspect_ratio":1.6,
 "caption":"环境校正前后的多样性—生产力关联 (Author et al., 2025)"}
```

Use actual author/year, not this placeholder. `source_id` must resolve to
`source_map` and be cited by the page's `evidence_sources`, with a locator.
Paths resolve relative to deck_plan.json. Preserve axes, units, uncertainty,
legends and the scientific meaning of crops. `aspect_ratio` is width/height.

Composition shapes (replace explanatory placeholders with source-backed data).
Counts are supported capacity ranges, not evidence quotas. Choose another
structure rather than inventing figures, metrics or stages to meet a range.

```text
figure_analysis:
  figure: <figure record>
  facts: [<18 pt complementary statement>,
          {value: <prominent estimate>, label: <denominator / condition>}]

figure_comparison:
  figures: [<2–4 figure records, each may also have a title>]
  legend: <shared legend if panels lose it when separated>

evidence_atlas:
  metrics: [{value: <count>, label: <sampling unit>}, ...]  # 2–4
  figures: [<1–3 figure records>]

evidence_matrix:
  figures: [<0–3 figure records>]
  headers: [<2–5 comparison dimensions>]
  rows: [[<actual cell values>], ...]  # 1–6; fewer rows when figures above
  figure_label: <optional text in the comparison-dimension column>

method_diagram:
  flow: sequential | parallel
  input: <shared input for parallel branches>
  stages:  # 2–4, source-supported operations, never a generic prose list
    - title: <operation>
      visual: {type: matrix, rows: [...], columns: [...]}
      facts: [<assumption / unit / output>]
    - title: <transformation>
      visual: {type: formula, lines: [<actual expression>, ...]}
      facts: [<parameter meaning / validation>]
    - title: <output>
      visual: {type: groups, labels: [<actual outputs>, ...]}
      facts: [<interpretive boundary>]
  caption: <operation / relationship (Author et al., year)>
```

Parallel branches share an input and have no arrows suggesting a false sequence.
Sequential stages use one closed block-arrow silhouette between stages.
Tables become native PowerPoint tables; prose, labels, expressions and arrows
remain editable. Scientific source images remain images. No decoration cards or
image background boxes are added. Body uses 18 pt, subordinate text 16 pt,
captions 14 pt with KaiTi Chinese and Times New Roman Latin runs. Text that
does not fit raises an error; shorten, split or change structure, never shrink.

These are initial executable compositions, not a demand to make every paper
look identical. For evidence requiring other geometry, extend and register the
composer before using it, or use a compatible registered source-figure layout.
Never solve layout repetition by relabeling an identical arrangement.

## Render and review

```powershell
python <runtime>/scripts/easyslides.py semantic-render <runtime>/templates/layouts/academic_general <project>/deck_plan.json --out <project>/svg_output
python <runtime>/scripts/svg_to_pptx.py <project> --only native -o <project>/report.pptx
python <runtime>/scripts/render_pptx_png.py <project>/report.pptx --out <project>/rendered --report <project>/render_report.json
python <runtime>/scripts/easyslides.py academic-gate <project> --pptx <project>/report.pptx --image-input available --review <project>/visual_review.json --report <project>/delivery_report.json
```

`visual_review.json` records actual review, not automatic pixel measurements:
`{status:"pass", reviewer:"image_model"|"human", pptx_sha256:<final hash>,
reviewed_slides:[1,...], findings:<review observations>}`. Inspect every final
render; check headers, bullet baselines, chart labels/crops, scientific meaning,
composition rhythm and footers. Resolve findings before a pass record.
Rendering receipts bind each final PNG to the actual PPTX.

When the model cannot read images, use `--image-input unavailable`; leave the
deck awaiting visual review and provide previews for user review. Do not claim
an image review from RGB/ink/whitespace counts. `academic-gate` then reports
`needs_visual_review`, even if all structural checks pass. These checks verify
declared structure and geometry, not the truth of scientific claims.
