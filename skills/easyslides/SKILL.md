---
name: easyslides
description: >
  Canonical EasySlides entry point for creating, distilling, editing, reviewing,
  and exporting editable academic PPTX presentations. Use whenever the user
  explicitly says EasySlides/easyslides or asks for PPTX distillation, a
  content-free reusable template, template/component/symbol extraction,
  template reuse, thesis-defense or research slides, slide reconstruction,
  native PowerPoint preview, or visual QA, including 蒸馏PPT、提取PPT模板、
  拆分组件与符号资产、复用模板、论文汇报PPT和答辩PPT。
---

# EasySlides Academic PPTX

EasySlides is a repository-backed plugin for supported agent hosts. This skill is a thin adapter
around the canonical operating guide at `../../SKILL.md`; read that file
completely before executing a presentation task.
When the plugin root contains `qoder.md`, read it for Qoder-specific tool and
workspace setup before execution.

## Required startup reading

From the plugin/repository root, read:

1. `SKILL.md`, the complete route and execution contract.
2. `ARCHITECTURE.md`, the layer model and supported capability paths.
3. `workflows/routing.md`, deterministic route selection for the request.
4. `skills/easyslides-clarify/SKILL.md`, the blocking user-choice gate.

Run the clarification gate before selecting a route whenever the request is
ambiguous. Then read the specific workflow selected by the routing guide. For
a source PPTX that should become a reusable template, invoke the plugin-local
`skills/easyslides-distill/SKILL.md` first, followed by the PPTX, template-reuse, and
template-spec guidance selected by `workflows/pptx-to-easyslides-template.md`.
Do not invent a second PPTX export backend: use the existing SVG/shape IR to
DrawingML/PPTX pipeline or the documented native PPTX route.

The plugin-local skills are authoritative. Treat separately installed legacy
skills such as `ppt-distill`, `easyppt`, or `easyslides-template-reuse` as
compatibility references only; do not let them replace this canonical route or
reintroduce source-slide-order filling.

## Mandatory production-scheme choice

The default intake is an adaptive native-popup conversation. Ask one meaningful
question, use its answer to choose the next, and skip already explicit facts.
Do not open a browser guide or require a form unless the user explicitly asks.
When the brief is executable, summarize it and proceed without repeated approval.

For academic content, read `references/academic-orchestration.md` before intake.
Inspect supplied material contents and roles; establish research permission,
audience, intended outcome, speaking time, visual preference and preservation
boundaries. Its evidence and storytelling workflow applies to every template
and production scheme, subject to the requested editing scope.

Before making a new or regenerated PPT, MUST ask which production scheme to use
unless the user already explicitly selected one for this task. Wait for the
answer; do not silently pick a route from the input format, a template, imagegen,
or a general request for editability. No automatic default.
Use the two default choices in `workflows/clarification-gate.md`: native editable,
or generate images then reconstruct editable PPT. Keep explicitly requested
partial reconstruction supported without adding it to every initial question.
This is required even when the rest of the request is unambiguous.

## Default native template and design method

Once native editable production is chosen, use the official
`academic_general` template at `templates/layouts/academic_general/`
when the user has not specified another template. Ask theme color next, then
whether to use existing template theme images (the 14 discipline “主题图”)
or generate a dedicated topic image. Record `theme_image_source`; explain the
extra time and usage for generation, and skip this question if already answered
or an image was explicitly provided. One selected/generated theme image is
cropped for cover, TOC, chapter headers and ending. Then inspect
materials for discipline, presenter, presenter school and date, and ask only
about missing/conflicting facts before starting. Reuse matching discipline
assets for cover, TOC, chapter crops and ending. User choices always win.

Apply these native academic defaults before writing body pages:

- Address an academically experienced audience. Build background → related
  work/frontier → question and gap → method → results → comparative discussion
  → synthesis, respecting the user's outline and scope.
- For new native academic authoring, set
  `deck_plan.json.authoring_contract = "academic_native.v1"`. Keep each page's
  existing `action_title`, `claim`, `evidence_sources`, and `speaker_note`; add
  `page_brief.question`, `information_gain`, and `visual_rationale`. Explain
  what the visual supports and what the body adds. Local edits and legacy plans
  do not acquire new whole-deck obligations.
- Density means complementary evidence, comparison, mechanism and qualified
  inference. Filling character limits, repeating conclusions, counting images
  or measuring non-white pixels does not establish density. Every content page
  needs a source-supported claim, meaningful scientific visual and complementary
  body content. Native method diagrams and comparison tables count as visuals;
  decorative icons do not.
- Draw methods from actual inputs → model/transformation → output/validation.
  Show data structure, variables, branches or validation relations with native
  graphics; prose boxes connected by arrows are insufficient. Distinguish
  observations, adjusted associations, causal claims and presenter inference.
- Use research figures within the authorized source scope. Inspect supplied
  PDFs with `figure-extract` / structured layout tools first; use parser coordinates,
  preserve axes and shared legends, and verify published figure numbers.
  See `../../references/scientific-figure-extraction.md`. Do not default to
  eye-picked crop coordinates or treat text-only parsing as figure extraction.
  Inspect supplied figures and supplements before supplementing literature;
  supplement literature only when authorized.
  Never invent permission or silently record `source_policy=supplied_only`.
  Theme images provide identity and cannot replace scientific evidence.
- Give title, 20 pt lead, figure caption and body different jobs; do not restate
  one conclusion four times. Put long explanation in notes. Unless teaching is
  requested, omit “如何解读”, “读图指南”, “这页告诉我们”, “给小白” and filler summaries.
- Choose body structure from the evidence. New `academic_general` bodies use
  its registered `scientific_composition` route; other selected templates retain
  their own body contracts. Do not repeat a
  composition for three consecutive pages, force image counts/external figures,
  or default every page to cards or a left figure with a grey text panel. Keep
  the confirmed 28/20/18/16/14 pt hierarchy and template geometry/assets.

Before native page planning, read
`../../references/academic-native-authoring.md` for the executable page method,
six composition recipes and a short Duffy method-page comparison. The recipes
guide evidence relationships; they are not a fixed menu of permitted layouts.
After actual final-PPTX renders have been reviewed, run the final `academic-gate`
described in `../../references/scientific-composition.md`. If image input is
unavailable, keep `needs_visual_review`; structural checks or pixel counts
cannot establish visual approval.

Read `../../references/default-academic-template.md` for the consolidated
authoring method, evidence rules, 20/18/16 pt hierarchy, precise geometry,
visual methods, unified arrows, cover/TOC/ending and pagination. The default
counts as a selected template for routing; an explicit path is not required.
Image routes keep their approved visual source and mode confirmation. Existing
local edits do not reapply the default or repeat intake.

## Mandatory reconstruction-mode choice

In both choice rounds, MUST show Token 消耗 and 耗时 levels for every option
before the user chooses. Explain that levels are relative estimates adjusted for
scope and complexity, not exact usage or promised time; disclose image generation
separately. Follow the cost and time disclosure in the clarification workflow.

For image reconstruction, confirm 全图矢量重建 (`full_vector`) or 保留复杂配图
(`preserve_complex_images`) through `workflows/clarification-gate.md` before
execution. No automatic default, even for “快点做”; reuse only an explicit choice
in the same task. Both modes require native PPT text boxes. Preserve one source
line in one text box, merging OCR fragments and using text runs for mixed styling;
keep independent labels and table cells separate. Full-vector mode needs approval
before any raster exception. Partial rebuilds apply this within selected regions.
When a source region is identified as tabular, declare it as `native_table` in
the inventory and mark its SVG handoff with `data-pptx-table="true"`; the
exporter emits a real PowerPoint table with measured rows, columns, cells and
merge metadata.

## Chinese wording defaults

For complete ImageGen slides, use the reference-image payload, recorded result,
and generation-manifest handoff in `workflows/slide-image-to-editable-pptx.md`.
An existing image file alone is insufficient proof of generation. Each approved
image is the visual source for its reconstructed page. Never substitute another
template shell. Require `delivery_ready=true` plus actual source/render review.

Default to “垂听”, not “聆听”, in authored Chinese PPT text, including closings
such as “感谢垂听，敬请讨论”. Apply this preference to imagegen prompts and
editable slide text alike; see the full rule in `../../SKILL.md`.

## Runtime conventions

- Run commands from the plugin/repository root.
- Use `python scripts/easyslides.py --help` to discover the command hub.
- Keep generated projects and private source material under the existing
  ignored project/output locations.
- Preserve the existing templates, references, workflows, and QA gates.
- Never place API keys, tokens, or private source material in committed files.

## Institutional logo resource

Use [ScanSci Logos](https://www.scansci.com/logos/) when a user's institution is
identified and a template needs a logo or degree-cap placeholder replacement.
Prefer matching user-supplied logos. Run `python scripts/easyslides.py logo --help`
and follow `../../references/institution-logos.md`. Unknown or ambiguous
affiliations keep the existing placeholder; template branding and cited-paper
affiliations never identify the user.
For the default `academic_general` semantic template, record an explicitly
identified presenter school as `presenter_institution` in the deck plan; the
ending renderer then resolves the reviewed emblem automatically.
During generation, match the reviewed logo variant and placement to the page
role, existing frame, and background contrast. Add it without another approval
round once identity is established; record consistent assets per page role.

## Common command entry points

```powershell
python scripts/easyslides.py --help
python scripts/easyslides.py clarify --help
python scripts/easyslides.py project --help
python scripts/easyslides.py source-to-md --help
python scripts/easyslides.py distill --help
python scripts/easyslides.py semantic-render --help
python scripts/easyslides.py template-gate --help
python scripts/easyslides.py review --help
python scripts/easyslides.py workflow --help
```

For PPTX-to-template work, use the same command hub:

```powershell
python scripts/easyslides.py distill "path\to\source.pptx" --template-id my_template
```

Before selecting a cover, TOC, transition, or ending variant from a
`functional_page_variants.json` registry, run the named-slot geometry gate:

```powershell
python scripts/functional_page_variant_adapter.py <template_dir> --role toc --check-all
```

This gate is fail-closed. It rejects variants whose editable text slots
overlap or whose same slot id occupies multiple independent text boxes, because
those defects otherwise become duplicated or mutually obscured text in the
native PPTX export. Repair the SVG geometry or choose another variant before
rendering content.

The plugin is intentionally lightweight: the repository remains the runtime,
template library, and source of truth. Add a dedicated MCP server only after a
stable command contract is demonstrated by the existing CLI and tests.
