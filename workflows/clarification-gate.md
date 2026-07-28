---
description: Blocking user-choice intake before EasySlides presentation execution.
---

# Clarification Gate Workflow

Run this workflow before selecting a presentation route or starting visual
execution. It applies to new decks, paper-to-PPT work, template filling,
PPTX beautification, PPTX distillation, and native enhancement.

## What must be clarified

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
