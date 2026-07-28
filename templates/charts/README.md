# SVG Visualization Template Library

This directory contains the standardized SVG visualization templates used by PPT Master — charts, infographics, process diagrams, relationship diagrams, and strategic frameworks. The directory name `charts/` is kept for backward compatibility; the library scope is broader than charts.

## Source of truth

[`charts_index.json`](./charts_index.json) is the single source of truth for the library: total count + one selection-rule `summary` per template (format: `"Pick for X. Skip if Y (use other_key)."`). Both human readers and AI roles read it in full — there is no category/keyword sub-index. Selection is done by semantic match against the summary list in one pass.

To browse the library, open `charts_index.json` and scan the `charts` block top-to-bottom; each entry's `summary` answers "when do I pick this, when do I skip" directly.

## EasySlides product layer

`charts_index.json` remains the visual catalog source of truth. EasySlides
normalizes it through `scripts/chart_library.py` into stable `chart/<chart_id>`
assets in the unified component registry. Each normalized asset carries:

- `family`: quantitative, table, workflow, framework, structural, or diagram;
- `selection`: content shapes, page roles, density, and the original pick/skip rule;
- `data_model` and `slots`: the minimum contract for replacing chart content;
- `render_backend`, `renderer_id`, and `editability`: the current SVG boundary;
- `required_gates` and upstream provenance for validation and future upgrades.

The SVG assets stay intentionally separate from native PowerPoint chart objects.
This lets the default renderer preserve cross-renderer visual fidelity while a
future native backend can opt in by `renderer_id` without changing chart IDs.

Useful commands:

```bash
python scripts/chart_library.py validate
python scripts/chart_library.py list --family quantitative
python scripts/chart_library.py search "trend" --limit 10
python scripts/component_registry.py list --granularity chart_asset
python scripts/component_selector.py query --content-shape chart --limit 10
```

## Style rules

See [`CHART_STYLE_GUIDE.md`](./CHART_STYLE_GUIDE.md) for color palette, typography, and SVG authoring conventions all templates must follow.

## Usage

Before generating a chart page, open the corresponding `<key>.svg` file to read its structure and layout. Files are named after the `key` field in `charts_index.json` (e.g. `bar_chart.svg`, `quadrant_bubble_scatter.svg`). Templates are named by visual structure, not by business-model name — keywords like SWOT, BCG, PEST, OKR, Porter's Five Forces, Value Chain are matched via each template's `summary` field.
