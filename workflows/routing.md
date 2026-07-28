---
description: Deterministic route selection rules for EasySlides deck work.
---

# Routing Rules

Use this file before entering the main EasySlides pipeline or any standalone
workflow. If this file conflicts with a short route summary elsewhere, this
file wins for route selection; the selected workflow then owns execution.

## Routing Discipline

| Rule | Behavior |
|---|---|
| Deterministic routes | Do not ask a redundant route question when the request already supplies the required decisions. Otherwise run the clarification gate first. |
| Missing prerequisite | State the missing prerequisite and stop that route. Do not invent an alternate route that violates the prerequisite. |
| Result-affecting ambiguity | Ask the user to choose from two to four explicit options; do not silently choose a default. |
| Question batching | Ask no more than three high-value blocking questions per round. |
| Explicit user override | Honor it only when the target route prerequisites are satisfied. |

## Clarification Gate

Before route selection, read `workflows/clarification-gate.md` and the
route-specific catalog in `scripts/clarification_gate.py`. A value is blocking
when different reasonable answers would change the route, story, page count,
template, visible wording, or visual fidelity. Harmless implementation details
may remain assumptions, but must be recorded as such.

The chat interaction is authoritative: show choices, mark a recommendation,
explain the consequence, and wait for the user's selection. Persist the result
in `<project>/clarification_request.json`; do not write `deck_plan.json`,
`design_spec.md`, `spec_lock.md`, SVG pages, or an exported PPTX until the
request is confirmed.

## Main Routes

| Request shape | Route | Forbidden route | Preconditions | Output contract |
|---|---|---|---|---|
| Topic only, no source facts | `topic-research`, then main `SKILL.md` pipeline | Main pipeline with invented facts | Web/source gathering is allowed, or user supplies facts | Research Markdown and assets imported as source material |
| Source material can become a new story | Main `SKILL.md` pipeline | Direct PPTX edit workflows | PDF/DOCX/URL/Markdown/text/conversation content exists and clarification is confirmed | `deck_plan.json`, `design_spec.md`, `spec_lock.md`, `svg_output/`, exported PPTX |
| PPTX is source material and may change page count/order | Main `SKILL.md` pipeline with PPTX Markdown/intake | Native fill/enhance routes | User allows re-outline, split, merge, drop, or reorder | New EasySlides-generated editable PPTX |
| Explicit reusable EasySlides template directory | Main `SKILL.md` template route | Fuzzy raw PPTX template use | Directory exists and has EasySlides template metadata | Template copied/bound into the project |

## PPTX-Specific Routes

| Request shape | Route | Forbidden route | Preconditions | Output contract |
|---|---|---|---|---|
| Raw PPTX template plus new material/topic | `template-fill-pptx` | Main SVG pipeline directly from raw PPTX | Source PPTX plus content material/topic brief and clarification is confirmed | New native PPTX in `exports/`, cloned and patched by OOXML |
| Raw PPTX or reference deck should become a reusable template | `pptx-to-easyslides-template` with plugin-local `easyslides-distill` first | One-off template fill or source-order DOM filling | Source PPTX exists and the user wants reusable page roles, components, or slots | Source evidence, a faithful review draft, source-scoped renderable assets, and a separately gated content-free semantic layout family |
| Existing PPTX, preserve page split and visible wording while improving look | `beautify-pptx` | Main pipeline if page count/order changes | Single source PPTX | Beautify report plus conservative native theme-color patch; stronger layout repair remains future work |
| Finished PPTX, add notes/audio/timing/transitions only | `native-enhance-pptx` | SVG regeneration | Finished PPTX exists; visible slides should stay stable | Patched PPTX through direct OOXML |
| PPTX/reference design should become reusable | `pptx-to-easyslides-template` | One-off template fill | Design source exists | Template directory under `templates/layouts/` and reference assets |

## Optional Workflows

| Request shape | Route | Preconditions | Output contract |
|---|---|---|---|
| Continue an existing split-mode project | `resume-execute` | Phase A artifacts exist | SVG generation and export continue without re-running planning |
| Data chart calibration | `verify-charts` | Generated SVG pages contain charts | Fixed chart geometry before export |
| Object-level animation tuning | `customize-animations` | SVG groups or exported context exist | Validated animation config |
| Browser preview or annotations | `live-preview` | Project exists; SVGs exist for annotation apply | Running preview or applied annotations |
| Confirmation page/checklist before execution | `confirm-ui` | Project exists | Confirmation JSON and local HTML page |
| Visual review/self-check/shareable preview | `visual-review` | PPTX exists or rendered slide PNGs exist | Review manifest, HTML page, and contact sheet |
| Brand preset creation or inspection | `create-brand` | Brand name, palette, logo, or existing brand id exists | Brand JSON and registry entry |
| Slide screenshot/image reconstruction | `slide-image-to-editable-pptx` | Source image(s) exist | Layer A/B/C inventory and editable PPTX reconstruction |
| Narration for EasySlides-generated project | `generate-audio` | Notes and generated deck exist | Audio files and optional narrated PPTX |
