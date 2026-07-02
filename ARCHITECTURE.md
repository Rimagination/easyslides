# EasySlides Architecture

EasySlides is a project-backed Codex skill for producing editable PowerPoint
decks. The skill entrypoint tells an agent how to route the task, but the real
capability lives in this repository: workflows, scripts, templates, references,
tests, and local runtime dependencies.

In short:

```text
Skill = task router and operating guide
Workflows = task-specific protocols
Scripts = local execution engine
Templates/assets = reusable design system
QA gates = delivery contract
```

## Architectural Principle

EasySlides has one production PPTX backend:

```text
normalized SVG / shape IR -> DrawingML / OOXML -> editable PPTX
```

Multiple authoring paths can feed this backend, but they should not introduce a
second production exporter unless a dedicated spike proves better editability,
Office compatibility, and maintainability.

This rule keeps the project understandable: different inputs, one output
contract.

## Four Layers

### 1. Skill Layer

Files:

- `SKILL.md`

Purpose:

- Route user requests into the right EasySlides path.
- State project rules, hard boundaries, and required QA.
- Tell Codex or another local agent which scripts and workflows to use.

What it is not:

- It is not a standalone PPT generator.
- It is not the whole product.
- It should not duplicate the full implementation.

### 2. Workflow Layer

Files:

- `workflows/*.md`

Purpose:

- Describe task routes such as topic research, template reuse, PPT Master
  compatibility, HTML/JSX upstream authoring, and slide-image reconstruction.
- Keep task-specific protocols readable before an agent touches scripts.
- Preserve boundaries between mature paths and experiments.

Important workflows:

- `workflows/topic-research.md`
- `workflows/ppt-master-compat.md`
- `workflows/template-asset-bank.md`
- `workflows/pptx-to-easyslides-template.md`
- `workflows/html-jsx-authoring.md`
- `workflows/slide-image-to-editable-pptx.md`

### 3. Runtime / Scripts Layer

Files:

- `scripts/project_manager.py`
- `scripts/svg_to_pptx.py`
- `scripts/finalize_svg.py`
- `scripts/ppt_master_pipeline.py`
- `scripts/image_reconstruction_pipeline.py`
- `scripts/visual_measure_gate.py`
- supporting conversion, rendering, QA, and asset scripts

Purpose:

- Create and validate project workspaces.
- Convert source material into markdown/assets where appropriate.
- Export SVG/shape content into editable PPTX.
- Run quality gates before delivery.

This layer is the local engine. If it is missing, the skill can explain the
workflow but cannot produce a real deck.

### 4. Assets / Templates Layer

Files and folders:

- `templates/`
- `references/`
- `templates/cards/`
- `templates/page_layouts/`
- `templates/layouts/`

Purpose:

- Provide layout packs, page recipes, card recipes, icons, charts, style
  constraints, and reusable template assets.
- Keep design decisions reusable instead of scattering them through prompts.
- Give agents fixed capacity contracts for dense academic content.

## Main Capability Paths

### Path A: Create From Scratch

Use when the user supplies a topic, paper, report, markdown, or source material
and wants a new editable deck.

```text
source material -> project workspace -> deck plan -> SVG pages -> PPTX
```

Primary scripts:

- `scripts/project_manager.py`
- `scripts/source_to_md/*`
- `scripts/finalize_svg.py`
- `scripts/svg_to_pptx.py`
- `scripts/visual_measure_gate.py`

### Path B: Edit Existing PPTX

Use when a real PPTX must be preserved or modified.

```text
PPTX -> unpack/edit OOXML -> validate -> repack
```

Primary tools:

- `scripts/source_to_md/ppt_to_md.py`
- OOXML unpack/edit/repack helpers where available
- `scripts/validate_pptx_text_layout.py`
- `scripts/render_pptx_png.py`

### Path C: HTML/JSX Authoring

Use as an experimental upstream measurement layer for complex layouts,
dashboards, reports, or browser-native components.

```text
HTML/JSX -> browser measurement -> normalized SVG/shape IR -> PPTX
```

Boundary:

- HTML/JSX is not the production PPTX backend.
- Use it to measure and author upstream, then normalize into EasySlides.

Workflow:

- `workflows/html-jsx-authoring.md`

### Path D: PPT Master Compatibility

Use when the user explicitly wants PPT Master-style execution or template
faithfulness.

```text
project init -> spec lock -> hand-written SVG pages -> gates -> PPTX
```

Primary scripts:

- `scripts/ppt_master_pipeline.py`
- `scripts/validate_svg_text_slots.py`
- `scripts/page_recipe.py`
- `scripts/card_library.py`
- `scripts/card_recipe.py`

Workflow:

- `workflows/ppt-master-compat.md`

### Path E: Slide Image Reconstruction

Use when the source of truth is a screenshot, exported slide image, or AI mockup
and the user wants a visually faithful but editable PPTX.

```text
source image -> Layer A/B/C inventory -> assets + native structure + native text -> PPTX -> QA
```

Project scaffold:

```powershell
python scripts/project_manager.py init <name> --format ppt169 --kind slide_image_reconstruction
python scripts/image_reconstruction_pipeline.py init <project> <slide_001.png>
```

Layer contract:

- Layer A: complex raster assets, illustrations, figures, photos.
- Layer B: native structure such as panels, dividers, arrows, axes, shapes.
- Layer C: editable text, formulas, labels, page numbers.

Important policies:

- Do not use a full-slide screenshot as the final deck.
- Do not bake readable text into image assets.
- Use `preserve_source_frame` for complex raster illustrations that become ugly
  when forced into vectors.
- Use masked source assets with clipping checks for closed/circular shapes.
- Use native DrawingML runs for superscripts/subscripts where possible.

Primary scripts:

- `scripts/image_reconstruction_pipeline.py`
- `scripts/slide_image_inventory.py`
- `scripts/validate_image_reconstruction_pptx.py`
- `scripts/validate_split_assets.py`
- `scripts/compare_source_render.py`

Workflow:

- `workflows/slide-image-to-editable-pptx.md`

## QA Architecture

EasySlides treats QA as part of the architecture, not an afterthought.

Core gates:

- `scripts/svg_quality_checker.py`
- `scripts/validate_svg_text_slots.py`
- `scripts/validate_pptx_text_layout.py`
- `scripts/template_geometry_qa.py`
- `scripts/validate_image_reconstruction_pptx.py`
- `scripts/validate_split_assets.py`
- `scripts/compare_source_render.py`
- `scripts/pptx_visual_diff.py`
- `scripts/visual_measure_gate.py`

The unified gate is:

```powershell
python scripts/visual_measure_gate.py --pptx <output.pptx> --report <project>/reports/visual_measure_report.json
```

For image reconstruction projects:

```powershell
python scripts/image_reconstruction_pipeline.py qa <project> --pptx <project>/pptx/output.pptx --rendered-dir <project>/reports/rendered_png
```

Default image reconstruction mode is `faithful-practical`: text, structure, and
asset safety are blocking; source-vs-render pixel difference is measured and
reported. Use `--mode pixel-strict` only when near-pixel matching is required.

## Repository Layout

```text
SKILL.md                 # skill entrypoint and agent routing guide
ARCHITECTURE.md          # this architecture overview
INSTALL.md               # installation tiers and dependency setup
README.md                # user-facing overview
requirements.txt         # Python runtime dependencies
workflows/               # task protocols
scripts/                 # execution engine and QA gates
templates/               # layouts, cards, recipes, charts, icons
references/              # authoring rules and guidance
tests/                   # regression tests
projects/                # local generated workspaces, ignored by default
outputs/                 # local generated outputs, ignored by default
tmp/                     # local experiments and comparisons
```

## What To Install

Because EasySlides is project-backed, installing only the skill entrypoint is
not enough for real deck generation. See `INSTALL.md` for the three supported
installation levels:

- Minimal Skill Install: routing and documentation only.
- Full Local Runtime: recommended for real PPTX generation and QA.
- Developer Mode: full repo plus tests and contribution workflow.

## Design Boundaries

- Keep one production PPTX backend.
- Add new input modes as upstream adapters, not competing exporters.
- Keep generated private decks and source materials out of Git by default.
- Prefer measurable manifests and QA reports over prompt-only promises.
- Do not weaken QA gates to hide visual or editability failures.
