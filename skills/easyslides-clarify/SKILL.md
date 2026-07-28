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

Use this skill only when an EasySlides request still contains a blocking,
result-affecting ambiguity.

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
