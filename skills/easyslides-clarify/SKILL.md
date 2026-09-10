---
name: easyslides-clarify
description: >
  Resolve only result-affecting ambiguities in an EasySlides request through
  explicit user choices before route selection or generation. Use when two or
  more reasonable interpretations would materially change the story, page
  count, template, visible wording, or fidelity target; do not trigger for
  harmless implementation details or already explicit requests.
---

# EasySlides Clarification Gate

Use this skill whenever a PPT production scheme has not been explicitly selected,
or when another result-affecting ambiguity remains.

## Mandatory production-scheme choice

An unspecified scheme is always blocking for a new or regenerated PPT. MUST ask
the user to choose directly generated editable PPT, full-image reconstruction,
or partial-image reconstruction, using the exact user-facing labels in
`workflows/clarification-gate.md`. No automatic default; wait for the user's answer
before slide planning, image generation, SVG reconstruction or PPTX production.
An explicit choice already made for the same task must not be asked again.

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

## Blocking rule

Do not infer a value when two or more reasonable interpretations would change
the route, story, page count, template, visible wording, or visual fidelity.
Ask the user to choose. A recommendation is allowed, but it only becomes a
decision when the user explicitly chooses it or says to use the recommendation.

Do not write `deck_plan.json`, `design_spec.md`, `spec_lock.md`, SVG pages, or
an exported PPTX while a blocking clarification remains unanswered.

## Conversation protocol

1. Inspect the request and list only the unresolved decisions that affect the
   deliverable.
2. Ask at most three high-value questions in one round.
3. Give two to four mutually exclusive choices for each question.
4. Mark one choice as the recommendation and explain its consequence in one
   short sentence.
5. Accept option numbers, option ids, a combination of choices, or “按推荐”.
6. Echo the selected decisions in a compact summary and continue only after
   the user confirms them.

Do not ask open-ended “请再描述一下” questions when a choice set can expose
the ambiguity. Do not ask again for a value the user already made explicit.

## State contract

Use the repository question catalog and state machine:

```powershell
python scripts/easyslides.py clarify init --route new_deck --out <project>/clarification_request.json
python scripts/easyslides.py clarify answer <project>/clarification_request.json --answer purpose=defense
python scripts/easyslides.py clarify require <project>/clarification_request.json
```

The request is confirmed only when every blocking question has an answer. The
machine-readable state is the source of truth for the later deck plan and
execution lock.
