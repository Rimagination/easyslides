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

Use this skill when a new/regenerated PPT lacks an explicit production scheme,
or another result-affecting ambiguity remains. Notes-only, narration-only and
preview-only tasks do not require a production scheme; ask only about unresolved
details within the requested editing scope.

## Mandatory production-scheme choice

An unspecified scheme is always blocking for a new or regenerated PPT. MUST ask
the user to choose native editable PPT or images followed by editable
reconstruction, using the two default user-facing choices in
`workflows/clarification-gate.md`. No automatic default; wait for the user's answer
before slide planning, image generation, SVG reconstruction or PPTX production.
An explicit choice already made for the same task must not be asked again.
An explicit partial-image reconstruction request is still supported; do not
require switching it to full reconstruction.

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

For academic tasks, read `references/academic-orchestration.md` before asking.
Use its evidence-aware intake and internal handoffs across all templates and
production schemes. Catalog completion alone does not establish readiness:
resolve the academic brief's material gaps and conflicts before planning.

Default to an adaptive interview in the conversation, using native popup
questions. Never open an in-app browser, HTML guide, questionnaire, or require
copy/paste to discover requirements unless the user explicitly requests that UI.

1. Inspect the conversation and available source metadata first. Maintain
   confirmed facts, unresolved decisions and contradictions internally. Do not
   ask for information already visible in the user's files or messages.
2. Ask ONE highest-impact question with the host's native question tool
   (`request_user_input_async` in Codex Default mode; use a synchronous question
   tool only where available). Wait for the answer before dependent work. Group
   up to three questions only when their answers are genuinely independent.
3. Give concise context-specific options and a justified recommendation; allow
   free text. Ask for a missing fact directly when choices would distort it.
   Explain route/mode tradeoffs without internal IDs; retain token/time disclosure.
4. Use each answer to choose the next question. Narrow broad goals, identify
   what the audience should understand or decide, and surface contradictions
   such as exhaustive evidence versus a five-minute talk. Offer concrete
   tradeoffs. Do not mechanically exhaust a catalog or ask for detail that
   would not change the result.
5. Persist explicit answers and skip resolved items. Handle free-text answers
   faithfully; never coerce them into an inaccurate canned option. Check source
   access, research scope, length, route, applicable editability/template choices
   and any preserve/rewrite boundary before execution.
6. Stop when the task can be executed without a material guess. Briefly restate
   the agreed outcome and proceed. No confirmation of the confirmation. Resolve
   conflicts first. Missing files call for the specific file, not more options.

For a new PPT with PowerPoint capture available, use `clarify init
--offer-recording`. Before producing slides, present the `recording` question
from `clarify next` on its own, separate from evidence scope, audience and
design. Its wording must say whether the PowerPoint elements will appear in
live capture or a finished-deck replay. Use `--recording-mode live` only once
the selected authoring method can write to the visible PowerPoint window.
In `--known-json`, carry explicit choices as `recording: "record"` for replay,
`"live"` for live capture, or `"skip"` for PPT only. See the
[recording workflow](../../workflows/powerpoint-replay.md) when a requested
mode is unavailable or for the follow-up after recording.

Do not ask open-ended “请再描述一下” questions when a choice set can expose
the ambiguity. Do not ask again for a value the user already made explicit.

## State contract

Use the repository question catalog and state machine:

The first unresolved production question is the route. After `direct_editable`
is chosen for a new deck and no template was specified, the state machine
selects the official default `academic_general`. Explicit templates take
precedence. The next question is theme color: record `theme_palette` as a preset
or confirmed `#RRGGBB`; skip known choices. Read
`references/default-academic-template.md` for the complete intake and method.

Next ask how to obtain the “主题图”: reuse the template's 14 discipline theme
images (`template_assets`, recommended), or generate a dedicated topic image
(`generate_new`, extra generation time/usage). This question is independent of
theme color and production route. Skip an already explicit choice or supplied
theme image (`user_provided` and `theme_image_path`). Generate only after the
topic is understood; save the output path and reuse it across page crops.
Do not silently fall back to the library after a custom image was requested.

For this template, `presentation_identity` is a source-inspection task covering
discipline, presenter, presenter institution and date. Read materials first,
ask only about missing/conflicting fields, and record facts with sources or
explicit omissions. Never infer the presenter's school from paper authors or
reference branding. Pass identified fields with the confirmed brief to the
deck plan. Existing approved tasks are not reopened for this new default or
the newly added theme-image question.

When `clarify next` returns a theme question with a `preview`, show the provided
local image inline before asking the native popup question. The existing image
is a reusable example, so do not regenerate or re-inspect it for each deck;
the illustrated color–discipline pairings are optional and user choices take
precedence. If the preview file is missing, ask with text options instead of
generating a replacement automatically. Generate or revise example previews
only when the user requests a new visual example.

For new academic content tasks, add `--academic` to `clarify init`. This extends
the same blocking state machine with academic goals, evidence policy, audience,
timing, style and content boundaries. It conditionally requires research scope
and/or a material inventory. Keep this off for notes-only edits and faithful
reconstruction of an already approved deck with no new content planning.
Older saved requests remain compatible; do not restart an approved task.

Free-text questions have no `option_ids`: save the actual response with
`clarify answer ... --answer "field=actual response"`. Populate explicit facts
via `--known-json` first. Record inspected file content with `--by
"inspection:file:page"`; record user answers with `--by "user:message"`.
`needs_material_inspection` has an empty popup payload: inspect the files,
resolve essential missing sources, then record the source-located inventory.
Never mark a missing/unreadable required file as an inspected usable source.
Copy the confirmed `decisions` into `deck_plan.json` as `academic_brief` and
retain the sibling `clarification_request.json` for the existing plan gate.

```powershell
python scripts/easyslides.py clarify init --route new_deck --out <project>/clarification_request.json
python scripts/easyslides.py clarify answer <project>/clarification_request.json --answer purpose=defense
python scripts/easyslides.py clarify next <project>/clarification_request.json
python scripts/easyslides.py clarify require <project>/clarification_request.json
```

The request is confirmed only when every blocking question has an answer. The
machine-readable state is the source of truth for the later deck plan and
execution lock.

`next` is a read-only catalog adapter. Its `questions` array matches Codex's
`request_user_input_async` payload; map the actual answer using `option_ids`.
For a different host or a synchronous tool, convert to that tool's declared
schema (including required question IDs, headers and structured options); never
call an unavailable tool. If no popup tool is available, ask one concise question
with options directly in chat and wait. A browser is not the fallback.
The adapter does not display a popup itself. `ready_for_summary` means catalog
choices and enabled academic requirements are recorded; still check their
substance, contradictions, source rights and partial regions. The program
checks completeness, not the truth of an inspection or scientific claim.
Follow interview examples in `workflows/clarification-gate.md`.
