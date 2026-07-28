---
description: Registry of standalone EasySlides workflows.
---

# Workflow Registry

When adding or changing a standalone workflow, update this registry and
`workflows/routing.md` together. The workflow file owns step-by-step execution;
this registry owns discoverability and trigger boundaries.

| ID | Path | Trigger | Preconditions | Route exclusion | Output contract |
|---|---|---|---|---|---|
| `topic-research` | `workflows/topic-research.md` | Topic-only deck request with no source facts | Topic or requirements exist | Do not invent facts in main pipeline | Source Markdown/assets suitable for import |
| `template-fill-pptx` | `workflows/template-fill-pptx.md` | Raw PPTX template plus new content/topic | Source PPTX and content/topic brief | No SVG generation from raw PPTX | Native PPTX in project `exports/` |
| `native-enhance-pptx` | `workflows/native-enhance-pptx.md` | Existing PPTX needs notes/audio/timings/transitions while preserving visible slides | Source PPTX exists | No SVG regeneration | Enhanced PPTX in project `exports/` |
| `beautify-pptx` | `workflows/beautify-pptx.md` | Existing PPTX should keep slide count/order/visible wording while improving look | Single source PPTX exists | Do not route to main pipeline if slide structure must stay fixed | Beautify report plus conservative native theme-color patch |
| `pptx-to-easyslides-template` | `workflows/pptx-to-easyslides-template.md` | Build reusable EasySlides template from PPTX | PPTX or design reference exists | Not a one-off fill route | Template pack and reference assets |
| `resume-execute` | `workflows/resume-execute.md` | Continue Phase B for an existing project | Phase A artifacts exist | Do not re-run planning | SVG generation and export |
| `verify-charts` | `workflows/verify-charts.md` | Generated deck contains charts needing calibration | SVG pages exist | Not needed without data charts | Verified/fixed chart geometry |
| `customize-animations` | `workflows/customize-animations.md` | User asks for animation order/effect/timing | Target SVG groups exist | Do not add object builds by default | Animation config consumed by export |
| `live-preview` | `workflows/live-preview.md` | User asks for browser preview or annotations | Project exists | Do not apply annotations before SVGs exist | Preview service or applied edits |
| `confirm-ui` | `workflows/confirm-ui.md` | User asks for a confirmation page/checklist before execution | Project exists | Does not replace plan/spec artifacts | Confirmation JSON and local HTML page |
| `clarification-gate` | `workflows/clarification-gate.md` | Presentation request has a result-affecting ambiguity | Request context exists | Do not guess or start generation | Confirmed user-choice state in `clarification_request.json` |
| `visual-review` | `workflows/visual-review.md` | User asks for visual review/self-check/shareable preview | PPTX exists, or rendered PNGs exist | Not a replacement for blocking QA | Review manifest, HTML page, contact sheet |
| `create-brand` | `workflows/create-brand.md` | User asks for brand preset/palette/logo registration | Brand name or palette exists | Does not generate a deck by itself | Brand JSON and registry entry |
| `slide-image-to-editable-pptx` | `workflows/slide-image-to-editable-pptx.md` | Source of truth is slide image/screenshot/mockup | Source image exists | No full-slide screenshot final deck | Editable reconstruction and QA reports |
| `generate-audio` | `workflows/generate-audio.md` | User asks for narration/voiceover/video-style export | Notes and generated deck exist | Do not call TTS directly | Audio files and optional narrated PPTX |
