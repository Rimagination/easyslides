---
description: Plan, acquire, place, and review context-aware visual assets.
---

# Visual Asset Workflow

Use this workflow after the content plan and before SVG authoring. It decides
whether a page needs source evidence, a generated hero image, a local
illustration, or no image at all.

## 1. Build the visual plan

```powershell
python scripts/easyslides.py visual-plan <project>/deck_plan.json `
  --out-dir <project>/images `
  --template-dir templates/layouts/academic_general `
  --palette academic_green `
  --imagegen `
  --write-deck-plan --json
```

The planner preserves source-linked figures, tables, screenshots, and
experiments; recognizes cover, chapter, transition, and ending pages; and only
uses AI generation for declared decorative opportunities or image-capable slots.

Capability detection is automatic. If `CODEX_HOME/skills/.system/imagegen/SKILL.md`
or `EASYSLIDES_IMAGEGEN_SKILL` is present, the planner records a host-native
handoff; `IMAGE_BACKEND` takes precedence. Use `--no-imagegen` when a run must
be deterministic and provider-free.

The visual policy controls how much decoration is requested:

- `auto_decorative`: hero backgrounds and explicitly declared local image slots.
- `ai_rich`: the same resources plus template-declared decorative hero elements
  and explicit replaceable visual surfaces.
- `source_only`: no invented visuals; source assets and the template shell only.

For a one-command, reviewable build that keeps the source plan untouched:

```powershell
python scripts/easyslides.py build <project>/deck_plan.json `
  --template academic_general `
  --palette academic_green `
  --out-dir <project>/build `
  --json
```

The selected palette is inherited by image prompts and runtime SVG/PPTX theme
replacement. Inspect the resolved semantic contract with:

```powershell
python scripts/easyslides.py theme validate academic_general --palette academic_green
```

User color choices override the selected palette by semantic role and are
validated before they reach SVG/PPTX:

```powershell
python scripts/easyslides.py build project/deck_plan.json `
  --template literature_minimal --palette literature_blue `
  --theme-token primary=#7A1FA2 `
  --theme-token accent=#D97706
```

## 2. Resolve acquisition capability

```powershell
python scripts/easyslides.py doctor --json
python scripts/easyslides.py image-acquire prepare <project>/images/image_prompts.json
```

The path is selected in this order: configured API, host-native imagegen, then
manual handoff. A missing or failed resource falls back to the template shell.

## 3. Compile and bind

Declare the generated manifest in `deck_plan.json`. A planner-written plan may
bind several resources to one page through `image_bindings`; a background is
selected as `background_asset` and local art is listed in `image_assets`. The
Executor never needs to know which provider produced an image.

Template-declared decorative art may use `placement.layer: shell_overlay` to
sit above shell chrome while remaining below editable shell text; source
evidence keeps its explicit placement contract.

## 4. Check readability

Backgrounds with `text_tone: auto` are sampled in their declared safe area. The
renderer chooses the stronger of `text_on_light` and `text_on_dark`, adds a
local scrim when the region is mixed or fails the contrast target, and writes a
readability report. Use the standalone gate for custom assets:

When a template owns an opaque hero band or panel, it can declare
`readability_mode: template_shell` and a semantic `text_color`. The shell's
visible contrast then wins over the hidden image underneath it.

```powershell
python scripts/easyslides.py readability <image> --regions <regions.json> `
  --report <project>/reports/readability_report.json
```

Do not use AI-generated visuals as evidence. If the image cannot achieve a safe
text area after one retry, keep the template background and report the fallback.
Pending, failed, unavailable, and unreadable decorative images always fall back
to the declared template shell and are listed in the build/readability reports;
they never block an otherwise valid editable PPTX export.

## 5. Template-specific guardrails

For `literature_minimal`, keep the visual route deliberately asymmetric:

- Cover, chapter, transition, and ending pages may request a thematic background and, under `ai_rich`, a declared right-side decorative illustration.
- TOC and content/evidence pages are `source_only`; preserve source figures, tables, screenshots, and citations.
- Pass user theme tokens into the planner. The sidecar palette contract is user tokens > selected palette > template defaults.
- Keep the generated frame outside the title and metadata safe areas. The ending metadata row is a centered two-column group with at least 64px clearance.
- If the safe-area contrast target fails, use the shell's semantic text token or retain the template shell; do not repair readability by recoloring source evidence.

After a template or visual policy change, run:

```powershell
python scripts/easyslides.py template-compile templates/layouts/literature_minimal --write --json
python scripts/template_production_gate.py templates/layouts/literature_minimal --no-cross-material --json
```
