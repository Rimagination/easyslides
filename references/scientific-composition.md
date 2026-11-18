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

## Choose by reading task

For new pages, write `composition.kind: "auto"` and choose `reading_task` from
the reader's goal. Supply the fields of the matching composition below, without
its explicit `kind`. If a page serves two goals, pick the primary evidence or
split the argument. Choose an explicit supported `kind` for a specific layout
requirement. Existing plans with explicit kinds still render directly.

| Reader's goal | `reading_task` | Evidence and resolved layout |
| --- | --- | --- |
| Trace datasets to a common analysis unit | `merge_data` | `inputs` and `output` form `data_convergence`. Use measured counts with clear units, and draw a join only for inputs that actually combine. |
| Understand what goes into a model | `explain_method` | `matrix` and `formula` form `method_model`; labeled `stages` form `method_diagram` for a real sequence or parallel branches. |
| Read a primary result and its interpretation | `read_result` | `figure` and `facts` form `figure_analysis`. Use the actual aspect ratio. Panoramic figures (≥2.35:1) go above a band of evidence; other figures go beside the explanation. |
| Compare patterns, magnitudes or ranks | `compare` | Use `figures` for aligned source panels. For comparable `series`, use bars for magnitude, set `focus: "rank"` for ranked dots, or supply two labeled values per category for paired dots. Use `panels` for two separately scaled quantities. Preserve the source figure when uncertainty or other plotting conventions are necessary for interpretation. |
| Inspect exact values across several dimensions | `lookup_values` | `headers` and `rows` give a native table. |
| Read sample coverage and its supporting figures | `show_coverage` | `metrics` and `figures` form `evidence_atlas`. Use `sequential: true` only when the metrics are ordered stages of one process. |

Record actual source references on every page. Neither the selector nor the
renderer infers scientific content from the paper title. A figure-led page can
highlight a key estimate with `{value, label}`, mark interpretive levels with
`{heading, text}`, or use plain facts for concise conditions. Counts of different
things can appear side by side as labeled metrics. Comparisons of magnitude
require a common measure and denominator. Review the actual renders when making
typographic or figure-placement decisions.

Composition shapes (replace explanatory placeholders with source-backed data).
Counts are supported capacity ranges, not evidence quotas. Choose another
structure rather than inventing figures, metrics or stages to meet a range.

```text
figure_analysis:
  figure: <figure record>
  placement: auto | left | right | above  # optional; explicit legacy kind defaults to left
  facts: [<18 pt complementary statement>,
          {heading: <brief role or claim>, text: <condition or interpretation>},
          {value: <prominent estimate>, label: <denominator / condition>}]

figure_comparison:
  figures: [<2–4 figure records, each may also have a title or interpretation note>]
  # Per-panel notes fit 2–3 panels. Use the page lead for the key comparison with four panels.
  legend: <shared legend if panels lose it when separated>

evidence_atlas:
  metrics: [{value: <count>, label: <sampling unit>}, ...]  # 2–4
  figures: [<1–3 figure records>]
  sequential: <optional boolean for ordered stages>

evidence_matrix:
  figures: [<0–3 figure records>]
  headers: [<2–5 comparison dimensions>]
  rows: [[<actual cell values>], ...]  # 1–6; fewer rows when figures above
  figure_label: <optional text in the comparison-dimension column>

bar_comparison:
  unit: <common unit or denominator>
  series: [{label: <category>, value: <nonnegative source number>}, ...]  # 2–6
  caption: <comparison title and source (Author et al., year)>

dot_comparison:
  # Same payload as bar_comparison. The renderer sorts rows by descending value.

paired_comparison:
  unit: <common unit and comparable quantity for both values>
  value_labels: [<first series label>, <second series label>]
  series: [{label: <category>, first: <number>, second: <number>}, ...]  # 2–6
  caption: <comparison title and source (Author et al., year)>

split_comparison:
  panels:  # two measures shown side by side, with separate scales
    - title: <measure and denominator, if relevant>
      unit: <unit>
      focus: rank  # optional; omit for bars
      series: [{label: <short category name>, value: <nonnegative source number>}, ...]
  caption: <comparison title and source (Author et al., year)>

data_convergence:
  inputs:  # 2–3 actual sources
    - title: <data source>
      metrics: [{value: <recorded count>, label: <unit or population>}]  # 1–2
      note: <optional inclusion or transformation detail>
  output:
    title: <shared analysis dataset or unit>
    metrics: [{value: <reported quantity>, label: <unit>}]  # 1–3
  caption: <data provenance (Author et al., year)>

method_model:
  matrix:
    title: <input and its meaning>
    rows: [<observation labels>]  # 1–5
    columns: [<feature labels>]  # 1–5
    cells: <optional rectangular boolean array for marked cells>
    note: <required with marks: explicitly schematic or a sourced subset>
  formula:
    title: <model or transformation>
    lines: [<actual model expression>]  # 1–3
    facts: [<variable definition, unit or condition>]  # 0–3
  caption: <methods provenance (Author et al., year)>

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
Use a native PowerPoint table for values and conditions that readers need to look up.
`bar_comparison` uses a common zero baseline and exact value labels. The bars
and labels are editable PowerPoint shapes. Preserve any uncertainty necessary
for interpretation using a suitable source plot or other comparison.
`paired_comparison` places both values on one shared scale and labels each pair;
use it for comparable quantities such as observed and estimated richness. Do
not use it for different units, denominators, or incomparable estimates. Record
the numerical source and conditions in the page evidence and speaker notes.
Prose, labels, expressions and arrows remain editable. Scientific source images
remain images. No decoration cards or
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
render; compare the body thumbnails for repeated text-and-table compositions,
open figure-led pages at viewing size and check exhibit prominence, axes and
legends. Verify table editability, headers, captions and footers. Resolve findings before a pass record.
Rendering receipts bind each final PNG to the actual PPTX.

When the model cannot read images, use `--image-input unavailable`; leave the
deck awaiting visual review and provide previews for user review. Do not claim
an image review from RGB/ink/whitespace counts. `academic-gate` then reports
`needs_visual_review`, even if all structural checks pass. These checks verify
declared structure and geometry, not the truth of scientific claims.
