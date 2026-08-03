# EasySlides Template Library

`templates/layouts/` contains the formal template library. In this project,
formal means one of the seven IDs in `templates/template_policy.json`.

- **Canonical policy**: [template_policy.json](../template_policy.json) defines
  the seven official IDs and the development-only IDs.
- **Package registry**: [template_registry.json](../template_registry.json)
  records package metadata, capability levels, and QA status; QA status does
  not override the official-template policy.
- **Generated index**: [layouts_index.json](./layouts_index.json) is the
  human-facing projection of the retained formal library. Non-legacy packages
  are archived outside the project.
- **Selection rule**: templates are opt-in. A deck uses a layout only when the
  user gives an explicit directory path such as
  `templates/layouts/literature_minimal/`. Bare names remain discovery hints, not
  triggers.
- **Legacy aliases**: [aliases.json](./aliases.json) maps old IDs such as
  `defense_s01` and `literature_s01` to their maintained replacements.

## Quick Template Index

<!-- quick-index:begin -->
| Template Name | Category | Use Cases | Primary Color | Design Tone |
|---------------|----------|-----------|---------------|-------------|
| `academic_general` | General | Research talks, course reports, progress reviews, paper explainers, scholarly exchange | `#003366` | Professional, rigorous, audience-facing, AST/SCQA-guided |
| `academic_scqa` | Scenario | Academic reports, laboratory technical briefings, research progress reviews, project reviews | `#0046A5` | Formal, institutional, data-driven, audience-facing, AST/SCQA-structured |
| `defense_leftnav` | Scenario | Thesis defense, graduation defense, proposal defense, research progress reports | `#8B0012` | Compact, formal, burgundy, left navigation, reusable |
| `defense_topnav` | Scenario | Thesis defense, proposal defense, opening defense, research progress reports | `#183A6A` | Academic, calm, blue-white, structured, source-faithful |
| `literature_minimal` | Scenario | Literature reports, paper reading, academic reports, research progress reviews | `#0D5DBE` | Minimal, blue-white, restrained, spacious, academic |
| `thu_speech` | Scenario | Tsinghua annual speeches, academic talks, institutional research presentations | `#912C8D` | Purple-blue, source-faithful, image-led, structured |
<!-- quick-index:end -->

## Active Families

### Core Academic

| Template | Role |
|----------|------|
| `academic_general` | Neutral general academic shells with shared Audience-State-Transfer and SCQA orchestration. |
| `academic_scqa` | Blue-cyan structured academic and technical report shells with AST/SCQA body-variant guidance. |
| `defense_leftnav` | Compact left-navigation thesis defense shells with wine, academic-blue, academic-purple, and academic-green palettes. |
| `defense_topnav` | Academic-blue thesis defense shells with dynamic top navigation and flexible content canvas. |
| `literature_minimal` | Classic five-page minimal blue literature report shells. |
| `thu_speech` | Tsinghua speech shells with functional-page variants, a shared transition series, and fifteen reviewed content variants. |

## Template Modes

| Mode | Use When | Core Contract |
|------|----------|---------------|
| `classic` | The template is a flexible visual style with reusable shells. | `design_spec.md` plus canonical placeholders. |
| `mirror` | A source PPTX deck must be visually preserved. | Fixed SVG roster, replace only existing text/image content. |
| `slot_guided_mirror` | A mirror template also needs story-role page selection. | `layouts.json`, `page_catalog.json`, `rules.md`, optional `story_structure.json`. |

## Capability Levels

| Level | Runtime contract |
|-------|------------------|
| `shell` | Stable public shells only. |
| `semantic` | Shells plus selectable body variants. |
| `composable` | Body variants bind executable components into named regions. |
| `production` | Composable runtime plus QA policy, lock file, and promotion gates. |

Managed packages compile to `compiled/template_ir.json` and
`compiled/template.lock.json`. Render decks through `slide_compiler.py` so SVG
and native PPTX consume the same resolved slide definition.

## Composition Boundaries

Each layout directory also contains `capability_profile.json`, with a generated
summary in [capability_registry.json](./capability_registry.json). This profile
is separate from a template's visual capability level: it defines which local
assets may be selected for a named template. Profiles never silently fall back
to the global component registry. A template with body variants must receive a
declared local `layout_id` or explicit local component; distilled and raster
reference directories are marked non-generative.

The current project route uses only the seven official templates in
`template_policy.json`. Review, quarantined, distilled, and style-pack assets
are development-only and must not be selected by default.

## Development

Create new active templates only when they serve repeatable academic scenarios.
Run these checks after editing a template:

```bash
python scripts/svg_quality_checker.py templates/layouts/<template_id> --template-mode --format ppt169
python scripts/easyslides.py template-package rebuild --json
python scripts/easyslides.py template-capabilities validate --json
python scripts/easyslides.py template-compile templates/layouts/<template_id> --write --json
```

`layouts_index.json` is a discovery index, not a routing gate. A template kept
outside `templates/layouts/` can still be used when the user provides its
explicit path.
