# Template Resources

## Directory Map

- `layouts/`: page layout packs only.
- `page_layouts/`: PPT Master-style whole-page layout recipes for SVG execution.
- `style_packs/`: archived non-legacy style migrations; not part of the current project library.
- `cards/`: fixed-size card components with slot capacity contracts and an agent assembly manual.
- `charts/`: chart, diagram, and framework SVG templates.
- `icons/`: shared icon libraries.
- `reference/`: reusable authoring references and generated lookup assets.

## Design Specification & Outline Reference

`design_spec_reference.md` is an all-in-one reference template for defining:
1.  **Visual Specifications**: Canvas dimensions, color scheme, typography, layout principles
2.  **Content Outline**: Slide-by-slide page structure planning
3.  **Technical Constraints**: Hard requirements for SVG generation and PPT compatibility

[View Design Spec Reference](./reference/design_spec_reference.md)

## Page Layout Templates

The `layouts/` directory exposes the current formal template library. The
canonical project policy is [template_policy.json](./template_policy.json):
only `academic_general`, `academic_scqa`, `defense_leftnav`, `defense_topnav`,
`literature_minimal`, `nsfc_defense`, and `thu_speech` are official and may be
selected by default.

The broader brand, government, enterprise, domain-specific, and special-style PPT Master packs
were moved out of the active library for review because EasySlides is focused
on academic scenarios.

- **Human browsing**: [layouts/README.md](./layouts/README.md)
- **Slim lookup (discovery only)**: [layouts/layouts_index.json](./layouts/layouts_index.json) — used to answer "what academic templates exist?". Step 3 triggers on an explicit directory path supplied by the user, not on names from this index.

## Archived Non-Legacy Templates

Review, quarantined, and unregistered style-pack assets are intentionally kept
outside this project and managed as a separate archive. They are not selected
by the default EasySlides template route.

## Template Asset Bank

Use a Template Asset Bank when the source is a large set of real `.pptx`
template files and the goal is manual-template-substitution quality: fixed page
structure, fixed decorative geometry, and only text/image/chart data replaced.

Build it from `pptx_template_import.py` workspaces:

```bash
python scripts/template_asset_bank.py build tmp/template_imports/<template_id> \
  --output templates/reference/template_asset_bank.json
```

The bank is a module harness, not a style pack. Each source slide becomes an
exact-reuse module with `flat_svg`, `layered_svg`, slot metadata, and explicit
allowed/forbidden edit rules. See
[`workflows/template-asset-bank.md`](../workflows/template-asset-bank.md).

## Visualization Templates

The `charts/` directory contains 71 standardized visualization templates. For backward compatibility, the directory name remains `charts/`, but its scope includes charts, infographics, process diagrams, relationship diagrams, strategic frameworks, and system architecture diagrams:

- KPI Cards
- Bar Chart / Stacked Bar Chart
- Line Chart / Dual-Axis Line Chart
- Donut Chart
- Radar Chart
- Funnel Chart
- Matrix (2x2)
- Timeline
- Gantt Chart
- Process Flow
- Org Chart
- Layered Architecture / Module Composition / Hub with Described Spokes / Pipeline with Stages / Client-Server Flow

- **Library index (single source of truth)**: [charts/charts_index.json](./charts/charts_index.json)
- **Directory overview**: [charts/README.md](./charts/README.md)

## PPT Master Page Layout Recipes

The `page_layouts/` directory contains whole-page archetypes for the
PPT Master-compatible route:

- **Registry**: [page_layouts/ppt_master_page_recipes.json](./page_layouts/ppt_master_page_recipes.json)
- **Agent manual**: [page_layouts/ppt-master-page-recipes-manual.md](./page_layouts/ppt-master-page-recipes-manual.md)
- **Query, validate, and prompt**: `python scripts/page_recipe.py --help`
- **Preview project generator**: `python scripts/page_recipe_preview.py --help`

Use these recipes before card selection. They decide the page-level structure,
visual hierarchy, text slots, and diversity pattern; card recipes are only
nested inside a selected page region.

## Card Components

The `cards/` directory contains reusable fixed-size card styles for slide assembly:

- **Registry**: [cards/card_library.json](./cards/card_library.json)
- **Agent assembly manual**: [cards/assembly-manual.md](./cards/assembly-manual.md)
- **PPT Master-style visual recipes**: [cards/visual_recipes.json](./cards/visual_recipes.json)
- **Visual recipe manual**: [cards/visual-recipes-manual.md](./cards/visual-recipes-manual.md)
- **Query, validate, and preview**: `python scripts/card_library.py --help`
- **Recipe query and prompt contracts**: `python scripts/card_recipe.py --help`

Use these cards when the content has a clear component shape such as metrics,
parallel points, comparisons, processes, evidence stacks, method modules,
literature notes, or one emphasized takeaway. Every card slot declares its text
capacity; payloads should be validated before rendering.

Use the visual recipes when the user wants PPT Master-like card composition:
layered vector backgrounds, decorative geometry, fixed content slots, and
prompt-ready SVG skeletons. The recipes are selected by content shape, density,
and visual intent, then validated before SVG execution.

## Icon Library

The `icons/` directory contains 11,600+ vector icons across six libraries:

| Library | Style | Count |
|---------|-------|-------|
| `chunk-filled` | fill / straight-line geometry | 640 |
| `lucide` | stroke / clean interface icons | 3 |
| `tabler-filled` | fill / bezier-curve forms | 1000+ |
| `tabler-outline` | stroke / line | 5000+ |
| `phosphor-duotone` | duotone / single color + 0.2 opacity backplate | 1200+ |
| `simple-icons` | brand logos (company / product marks) | 3400+ |

- **Usage & style rules**: [icons/README.md](./icons/README.md)
- **Search icons**: `ls templates/icons/<library>/ | grep <keyword>`
