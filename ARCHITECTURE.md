# EasySlides Architecture

## Component Pack Contract

EasySlides separates a template's page shells from reusable content expression.
`research-core` is a versioned global component pack: every component declares
an input schema, capacity, renderer contract, stories, and an error-level
vertical-center invariant. It is a library of candidates, not an implicit
fallback for a named template.

Production templates may also declare `component_pack.json`. This is a
template-scoped contract that locks the template component catalog, primitive
manifest, body-variant recipes, design tokens, and optional global-pack
dependencies. The template compiler materializes that relationship in Template
IR and the production gate rejects missing tokens, unresolved recipe components,
or incomplete variant coverage.

The user-facing `deck_plan` stays semantic: it specifies the claim, evidence,
content shape, density, and optional component preference. Component selection
then resolves a shell/body variant and records both renderable component refs
and source-derived recipe dependencies. It never asks a user to provide raw
coordinates.

### Template Capability Profiles

Every directory under `templates/layouts/` owns a generated-and-validated
`capability_profile.json`, indexed by `capability_registry.json`. The profile
is the executable answer to "what may this template compose?" It records the
directory lifecycle, whether automatic generation is permitted, which component
granularities are legal, and which local contracts exist. Named templates are
fail-closed: a component must be local to the named template and allowed by its
profile. A manual `selected_asset_id` cannot bypass this rule. Unscoped global
assets remain available only to untemplated plans unless a future profile
explicitly whitelists a pinned pack.

The current modes are deliberately conservative:

- `shell_only`: public page modules only.
- `body_variant_only`: local page modules and declared local body variants.
- `template_bounded`: local variants, modules, and template components.
- `template_composable`: the bounded set plus a verified local component-pack contract.
- `disabled` and `non_template`: source/intermediate directories that cannot be used for automatic generation.

The component builder enforces the profile during selection; the component-plan
contract repeats the check for externally authored plans; template compilation
embeds the profile in Template IR and its lock; and the production gate blocks
promotion when the profile is invalid or generation is disabled.

### Component Delivery And Selection

`templates/components/marketplace.json` is the discoverable catalog of
versioned declarative packs. Marketplace entries may resolve to a repository
path or a pinned Git source, but installation still runs the existing pack,
dependency, token, asset-hash, and no-code validation before activation.

The component workflow emits a `component_choice_review.json` and HTML review
surface beside `component_plan.json`. Each slide retains one executable choice
plus up to two alternatives, their fit reasons, capacity, and preview fixture
when available. A human or calling agent can lock an approved choice with
`component_requirements.selected_asset_id`; it is still checked against the
template and payload contract.

Selection is sequential rather than independent per slide. It scores narrative
role, evidence confidence, available material type, template affinity, and
recent visual-family or asset reuse. The reuse terms are penalties, not bans,
so a deliberate user lock remains authoritative.

### Renderer And Promotion Governance

Component packs remain declarative. Renderer identifiers and handlers are
owned by the EasySlides repository and verified by
`scripts/renderer_governance.py`; native PPTX handlers may register lazily when
the trusted preview renderer starts. A pack cannot execute code to add a
renderer.

PPTX distillation emits `component_candidates.json` in addition to its factual
component catalog. It separates replaceable slots, repeated template primitives,
candidate template components, and unresolved source-only references. A
candidate is never a global asset merely because it repeats: geometry, explicit
text-centre/container alignment, mirror-safe decoration symmetry, visual difference, cross-material, renderer governance, and
cross-renderer regression evidence must all pass before promotion.

`scripts/cross_renderer_visual_regression.py` renders the same native PPTX with
PowerPoint and LibreOffice and compares their PNG output. If either renderer is
unavailable, the result is `review_required`, not a false pass. This gate is
included in the distilled-template promotion report.

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

- `workflows/routing.md`
- `workflows/index.md`
- `workflows/topic-research.md`
- `workflows/beautify-pptx.md`
- `workflows/ppt-master-compat.md`
- `workflows/template-asset-bank.md`
- `workflows/pptx-to-easyslides-template.md`
- `workflows/template-fill-pptx.md`
- `workflows/native-enhance-pptx.md`
- `workflows/confirm-ui.md`
- `workflows/visual-review.md`
- `workflows/create-brand.md`
- `workflows/html-jsx-authoring.md`
- `workflows/slide-image-to-editable-pptx.md`

### 3. Runtime / Scripts Layer

Files:

- `scripts/project_manager.py`
- `scripts/easyslides.py`
- `scripts/workflow_manifest.py`
- `scripts/source_to_md.py`
- `scripts/svg_to_pptx.py`
- `scripts/finalize_svg.py`
- `scripts/ppt_master_pipeline.py`
- `scripts/template_fill_pptx.py`
- `scripts/native_enhance_pptx.py`
- `scripts/beautify_pptx.py`
- `scripts/confirm_ui.py`
- `scripts/visual_review.py`
- `scripts/create_brand.py`
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
- `templates/brands/`

Purpose:

- Provide layout packs, page recipes, card recipes, icons, charts, style
  constraints, and reusable template assets.
- Keep design decisions reusable instead of scattering them through prompts.
- Give agents fixed capacity contracts for dense academic content.

### Executable Template Model

An EasySlides template is a versioned design-and-execution package, not a set
of copied source slides:

```text
canonical sources -> Template Compiler -> Template IR
deck plan + Template IR -> Slide Compiler -> Slide IR
Slide IR -> SVG or native PPTX -> promotion gates
```

Canonical ownership is fail-closed:

- `template_package.json`: identity, version, capability level, entrypoints,
  source ownership, and dependency-lock location.
- `layouts.json`: the 3-5 public shells and their named regions/slots.
- `body_variants.json`: content composition, variant regions, and ordered
  component instances.
- `component_catalog.json` or component packages: reusable modules, local
  slots, renderer metadata, geometry, and QA.
- `qa_policy.json`: alignment invariants and promotion requirements. Explicit
  `data-center-lock` text boxes and declared mirror pairs are checked by
  `template_visual_invariants.py`; text only receives a container-centre rule
  when it names that container, so source-faithful unboxed labels are preserved.
- `story_structure.json`: scenario profiles, page responsibilities, and reviewed
  narrative-to-variant bindings; it is compiled into Template IR and checked
  before Slide IR is created when a deck selects a scenario.
- `source_page_roster.json`: provenance only; source pages are evidence, not
  runtime layouts.

`template.json`, `page_catalog.json`, flattened slot/geometry contracts,
template status, indexes, and registries are compatibility projections. New
runtime code consumes `compiled/template_ir.json`; resolved component versions
and hashes live in `compiled/template.lock.json`.

Capability levels let legacy and production templates coexist:

| Level | Contract |
|-------|----------|
| `shell` | Stable public page shells. |
| `semantic` | Shells plus selectable body variants. |
| `composable` | Variants bind real component slots into named regions. |
| `production` | Composable runtime plus QA policy, dependency lock, and promotion gates. |

The executable slide relation is:

```text
slide = shell + body variant + bound component instances + user material
```

`scripts/template_compiler.py` and `scripts/slide_compiler.py` own this
boundary. Renderers must not independently reinterpret template source files.

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

### Path F: Native PPTX Template Fill

Use when the user provides a raw PowerPoint template and wants a generated deck
that preserves the original native template design.

```text
template.pptx -> slide library -> fill_plan.json -> patched native PPTX
```

Primary script:

- `scripts/template_fill_pptx.py`

Workflow:

- `workflows/template-fill-pptx.md`

Current V1 boundary:

- Analyze/scaffold/validate plans.
- Apply text and table replacements after selecting, reordering, and reusing
  source slides through native slide-part cloning.
- Apply chart cache edits with per-output-slide chart XML cloning and embedded
  workbook synchronization.
- Deep-clone slide-local structured dependencies while sharing masters,
  layouts, themes, and reusable media.
- Preserve visible slide design by copying and patching the native PPTX package.
- Preserve SmartArt and embedded objects as native package parts; semantic
  editing of those object internals is outside the fill-plan schema.

### Path G: Native PPTX Enhancement

Use when the user provides an existing PPTX and asks for append-only additions
such as speaker notes, narration audio, timings, or transitions.

```text
source.pptx -> enhancement project -> plan -> package patch -> enhanced PPTX
```

Primary script:

- `scripts/native_enhance_pptx.py`

Workflow:

- `workflows/native-enhance-pptx.md`

Current V1 boundary:

- Initialize a project, archive the source PPTX, index slides, and validate the
  enhancement contract.
- Apply notes, optional narration audio, audio-duration timings, and transitions
  by patching a copied PPTX package without regenerating visible slides.

### Path H: Native PPTX Beautify

Use when a finished PPTX should preserve slide count, slide order, and visible
wording while receiving conservative visual polish.

```text
source.pptx -> beautify report -> native theme color patch -> verified PPTX
```

Primary script:

- `scripts/beautify_pptx.py`

Workflow:

- `workflows/beautify-pptx.md`

Current V1 boundary:

- Inspect PPTX package risks and visible text by slide.
- Apply only theme color patches to native theme-bound colors.
- Verify slide count and visible text are unchanged after patching.
- Deeper typography, alignment, spacing, and layout repair remain future work.

### Path I: Confirmation, Visual Review, and Brand Presets

Use when the user needs a confirmation page, human-readable visual review
package, or reusable brand palette before deck generation.

```text
project artifacts -> confirm.json + index.html
deck.pptx -> rendered PNGs -> visual_review.json + index.html + contact sheet
brand brief -> templates/brands/<brand-id>/brand.json -> design inputs
```

Primary scripts:

- `scripts/confirm_ui.py`
- `scripts/visual_review.py`
- `scripts/create_brand.py`

Workflows:

- `workflows/confirm-ui.md`
- `workflows/visual-review.md`
- `workflows/create-brand.md`

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
