# EasySlides Codex Plugin

EasySlides is now structured as a lightweight Codex plugin while keeping its
existing repository-backed workflow intact.

## What was added

- `.codex-plugin/plugin.json` — plugin metadata and discovery configuration.
- `assets/easyslides-icon.svg` — scalable 1024×1024-viewBox Codex plugin icon.
- `skills/easyslides/SKILL.md` — the canonical plugin-facing Skill adapter.
- `skills/easyslides-distill/SKILL.md` — the source-PPTX distillation Skill.
- `skills/easyslides-distill/agents/openai.yaml` — distillation invocation metadata.
- `skills/easyslides/agents/openai.yaml` — Codex UI and invocation metadata.
- `scripts/easyslides.py` remains the single command hub for the runtime.

## Local use

Run from the repository root:

```powershell
python scripts/easyslides.py --help
python -m pytest -q
```

The plugin uses the existing `SKILL.md`, `workflows/`, `scripts/`,
`templates/`, `references/`, and `tests/` directories. No separate PPTX
backend or MCP server is introduced in this first version.

## Plugin contract

The supported user-facing capabilities are:

- create an academic presentation from source material;
- edit or enhance an existing PPTX;
- reuse and fill PPTX/SVG templates;
- distill a source PPTX into reusable template language, component slots, and
  an EasySlides template draft;
- render previews and produce visual review packages;
- validate slide geometry, text capacity, and export quality.

For rendered previews, `scripts/render_pptx_png.py` automatically uses native
Microsoft PowerPoint on Windows when it is installed, then falls back to the
LibreOffice/PyMuPDF route. The JSON report records both `backend` and
`renderer`, so visual QA can identify which layout engine produced the images.

All presentation routes pass through `skills/easyslides-clarify/SKILL.md` when
the request contains a result-affecting ambiguity. The user must choose from
explicit options before planning or generation begins; recommendations never
silently become decisions.

The distillation route is intentionally connected to the existing repository
workflow rather than implemented as a second runtime. It uses
`scripts/pptx_source_graph.py` for factual OOXML evidence,
`scripts/pptx_distill_registry.py` for source-scoped identity, layout,
component, slot, asset, policy, and review contracts,
`scripts/pptx_design_system_compiler.py` for declarative design-system packs
and registry fragments,
`scripts/pptx_projection.py` and `scripts/source_template_renderer.py` for
declared-slot SVG projection with the existing SVG-to-PPTX route,
`scripts/pptx_distill_promotion_gate.py` for the unified Phase 5 promotion
decision across projection, geometry, text layout, visual diff, and
cross-material evidence,
`scripts/pptx_distill_promote.py` for turning the faithful review draft into a
content-free reusable template plus a source-scoped component/symbol kit,
`scripts/pptx_template_distill.py` for the compatibility template build, the
existing template contract and geometry QA tools, and the same SVG-to-PPTX
export paths used by the rest of EasySlides. The staged contract is documented
in `references/distill-v2-schema.md`; `source_graph.json` is factual evidence,
while semantic component registration is a later derived layer.

PPTX distillation is fail-closed. The default command produces source evidence
and a faithful review template only. `--promote-assets` is accepted only when
the complete promotion report is `pass` and `promotable=true`; even then,
`<id>_reusable/` is a source-order review candidate, not the main production
template.

Production assets live in a separate content-free semantic family with named
slots, capacity contracts, `body_variants.json`, real SVG component/symbol
fragments, and `template_status.json`. Run
`scripts/semantic_template_renderer.py` for content-shape routing and
`scripts/template_production_gate.py` for native PPTX, placeholder, text-layout,
and visual-review promotion. DOM-order filling and source slide numbers are
forbidden production routing signals.

Before publishing a marketplace entry, validate the local plugin with:

```powershell
python "<plugin-creator-skill>/scripts/validate_plugin.py" .
```
