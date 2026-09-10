---
description: Blocking user-choice intake before EasySlides presentation execution.
---

# Clarification Gate Workflow

Run this workflow before selecting a presentation route or starting visual
execution. It applies to new decks, paper-to-PPT work, template filling,
PPTX beautification, PPTX distillation, and native enhancement.

## Mandatory production-scheme choice

For every new or regenerated PPT, if the user has not explicitly selected a
production scheme for the same task, the assistant MUST ask the following
question and wait for the user's answer before outlining slides, writing a deck
plan, calling imagegen, reconstructing SVGs, or generating PPTX.

> 你希望采用哪种方案制作这份 PPT？
> 1. **直接生成可编辑 PPT（推荐）**：直接制作，方便修改文字、图表和布局。Token 消耗：中；耗时：中。
> 2. **图片整页重建**：先确定图片效果，再将整页重建为可编辑 PPT；配图处理方式需进一步选择。Token 消耗：高；耗时：长。
> 3. **图片局部重建**：保留原图，只把你指定的部分变成可编辑元素。Token 消耗：低至中；耗时：短至中（已有图片、少量区域时）。

No automatic default. A recommendation or preselected UI option is not user
consent. Silence, urgency, complete source materials, or a familiar template
must not bypass this question. A generic request for an editable PPT or imagegen
alone does not distinguish the schemes (imagegen alone is not a scheme choice).
Do not infer a choice from source file type, a reference screenshot, or a
preference used in another task.

An explicit route request such as “按原来的原生可编辑路线”, “把整页图片重建为
可编辑 PPT”, or “保留原图，只重建我圈出的元素” already supplies the choice.
Do not repeat this question for subsequent edits, previews, or exports in the
same task. Pure review, thumbnail export, narration-only changes, and template
asset distillation do not create a new deck and do not trigger this choice.

Once answered, echo the selected scheme and retain it as `production_scheme`
in the task's confirmed decisions (`direct_editable`, `image_full_rebuild`, or
`image_partial_rebuild`). If `clarification_request.json` is used, store it in
`decisions` and carry it through `--known-json` when opening later route-specific
clarification rounds. Record only explicit user choices. The CLI inserts the
scheme question, adds the reconstruction-mode question for an image route, and
rejects a confirmed request without these decisions. The build and image-init
entry points check the recorded choices before creating outputs.

## Mandatory reconstruction-mode choice

After image reconstruction is selected, MUST ask which treatment to use and
wait for the user's answer before reconstruction when it is unspecified:

> 配图希望怎样重建？
> 1. **全图矢量重建**：配图和结构重建为可编辑矢量，细节可能有差异。Token 消耗：高至很高；耗时：长至很长。
> 2. **保留复杂配图**：复杂配图保留原图，文字与简单结构重建，通常更接近原图。Token 消耗：中；耗时：中。

Neither mode is an automatic default. “可编辑”, “整页重建”, and “快点做”
do not select a reconstruction mode. Reuse an explicit choice only in the same
task; record `reconstruction_mode` as `full_vector` or `preserve_complex_images`.
For partial reconstruction, apply this choice only within the selected regions;
untouched source areas stay unchanged. Ask once for a deck unless page exceptions
are requested. This choice may share the initial clarification round.

In both modes all text within the reconstruction scope MUST become native PPT
text boxes. Preserve one source line in one text box; use text runs for mixed
color, bold, or fonts, never separate boxes merely because OCR split the line.
Separate genuinely independent labels or table cells even on the same baseline.
Merge OCR fragments in reading order and check baseline, spacing, cell boundaries,
and alignment. Do not convert text to outlines or leave duplicated raster text.
Full-vector mode cannot silently fall back to raster images or an embedded bitmap
inside SVG. Explain fidelity limits and ask approval for any raster exception.

## Mandatory cost and time disclosure

MUST show both Token 消耗 and 耗时 levels alongside every option in both
choice rounds, before the user chooses. The sample levels are relative planning
estimates, not measured token counts, fixed prices, or delivery-time promises.
State this caveat briefly in the question. Adjust levels for page count, source
availability, region count, illustration complexity, reuse and revision rounds.
The second-round levels describe reconstruction work within the selected scope;
do not add qualitative levels as if they were numeric costs. If source images
still need generation, disclose that additional stage separately. Image-generation
usage/charges are not equivalent to text-token usage; do not invent conversion
rates or exact counts. Urgency never bypasses choice or this disclosure.

## What else must be clarified

Ask only when the user's wording leaves multiple reasonable choices that affect
the result:

- purpose, audience, occasion, or presentation duration;
- source-of-truth material and content scope;
- preserve versus restructure page order and visible wording;
- page budget, canvas format, or template fidelity;
- editable-first versus visual-fidelity-first treatment;
- whether text, images, or page structure may be changed.

Do not block on harmless implementation details. Record those as assumptions.

## Question format

Each round contains no more than three questions. Every question must provide
two to four choices, one recommendation, and the impact of the choice. Use
the route-specific catalog in `scripts/clarification_gate.py`.

Good question:

> 这份 PPT 是否允许重排页面？
> 1. 保留页数、顺序和可见文字
> 2. 允许重排但不改变事实（推荐）
> 3. 允许重新组织内容

Bad question:

> 请再详细描述一下你想要什么。

## Blocking and confirmation

The user may answer with option numbers, ids, a combination of choices, or
`按推荐`. Echo the resulting decision summary before execution. A missing,
conflicting, or unanswered blocking choice keeps the workflow at
`needs_confirmation`.

Do not create or modify final slide files while the gate is unresolved. The
state is stored in `<project>/clarification_request.json` and can be checked:

```powershell
python scripts/easyslides.py clarify validate <project>/clarification_request.json
python scripts/easyslides.py clarify require <project>/clarification_request.json
```

`confirm_ui.py` may package the confirmed decisions into a local review page;
it does not replace the chat clarification step.
