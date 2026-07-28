# PPT Master Toolset

This directory contains user-facing scripts for conversion, project setup, SVG processing, export, recorded narration, PPTX-native workflows, and image generation.

## Directory Layout

- Top-level `scripts/`: runnable entry scripts
- `scripts/source_to_md/`: source-document → Markdown converters (`pdf_to_md.py`, `doc_to_md.py`, `excel_to_md.py`, `ppt_to_md.py`, `web_to_md.py`)
- `scripts/image_backends/`: internal provider implementations used by `image_gen.py`
- `scripts/tts_backends/`: internal TTS provider implementations used by `notes_to_audio.py`
- `scripts/template_import/`: internal PPTX reference-preparation helpers used by `pptx_template_import.py`
- `scripts/svg_finalize/`: internal post-processing helpers used by `finalize_svg.py`
- `scripts/docs/`: topic-focused script documentation
- `scripts/assets/`: static assets consumed by scripts

## Quick Start

Typical end-to-end workflow:

```bash
python3 scripts/easyslides.py --help
python3 scripts/source_to_md/pdf_to_md.py <file.pdf>
# or
python3 scripts/source_to_md/ppt_to_md.py <deck.pptx>
python3 scripts/source_to_md/excel_to_md.py <workbook.xlsx>
python3 scripts/project_manager.py init <project_name> --format ppt169
python3 scripts/project_manager.py import-sources <project_path> <source_files...> --move
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/animation_config.py scaffold <project_path>  # optional object-level animation overrides
python3 scripts/svg_to_pptx.py <project_path>
python3 scripts/visual_measure_gate.py --pptx <output.pptx> --report <project_path>/reports/visual_measure_report.json
```

Repository update:

```bash
python3 scripts/update_repo.py
```

## Script Index

| Area | Primary scripts | Documentation |
|------|-----------------|---------------|
| Command hub | `easyslides.py`, `workflow_manifest.py` | [Architecture](../ARCHITECTURE.md), [routing](../workflows/routing.md) |
| Conversion | `source_to_md.py`, `source_to_md/pdf_to_md.py`, `source_to_md/doc_to_md.py`, `source_to_md/excel_to_md.py`, `source_to_md/ppt_to_md.py`, `source_to_md/web_to_md.py` | [docs/conversion.md](./docs/conversion.md) |
| Project management | `project_manager.py`, `batch_validate.py`, `generate_examples_index.py`, `error_helper.py`, `pptx_template_import.py`, `pptx_source_graph.py`, `pptx_distill_registry.py`, `pptx_design_system_compiler.py`, `pptx_template_distill.py` | [docs/project.md](./docs/project.md), [pptx-to-easyslides-template](../workflows/pptx-to-easyslides-template.md) |
| SVG pipeline | `finalize_svg.py`, `svg_to_pptx.py`, `total_md_split.py`, `svg_quality_checker.py`, `validate_svg_text_slots.py`, `template_geometry_qa.py`, `validate_pptx_text_layout.py`, `render_pptx_png.py`, `pptx_visual_diff.py`, `visual_measure_gate.py`, `animation_config.py`, `notes_to_audio.py` | [docs/svg-pipeline.md](./docs/svg-pipeline.md) |
| Page layout recipes | `page_recipe.py`, `page_recipe_preview.py` | [templates/page_layouts/ppt-master-page-recipes-manual.md](../templates/page_layouts/ppt-master-page-recipes-manual.md) |
| Card components | `card_library.py`, `card_recipe.py` | [templates/cards/assembly-manual.md](../templates/cards/assembly-manual.md), [templates/cards/visual-recipes-manual.md](../templates/cards/visual-recipes-manual.md) |
| Template and slide compilation | `template_compiler.py`, `slide_compiler.py`, `template_package.py`, `template_capabilities.py` | [Architecture](../ARCHITECTURE.md), [presentation contracts](../references/presentation-production-contracts.md) |
| Body variant composition | `body_variant_contract.py`, `body_variant_adapter.py`, `component_registry.py` | [body variant component contract](../references/body-variant-component-contract.md) |
| Component marketplace and choice review | `component_marketplace.py`, `component_workflow.py`, `component_selection_review.py`, `renderer_governance.py` | [component packs](../templates/components/packs/README.md), [Architecture](../ARCHITECTURE.md) |
| Chart asset library | `chart_library.py`, `component_registry.py`, `component_selector.py` | [templates/charts/README.md](../templates/charts/README.md), [verify-charts](../workflows/verify-charts.md) |
| Icon asset library | `icon_library.py`, `component_registry.py`, `component_selector.py`, `svg_finalize/embed_icons.py` | [templates/icons/README.md](../templates/icons/README.md) |
| PPT Master compatibility | `ppt_master_pipeline.py` | [workflows/ppt-master-compat.md](../workflows/ppt-master-compat.md) |
| Native PPTX template fill | `template_fill_pptx.py` | [template-fill-pptx](../workflows/template-fill-pptx.md) |
| Native PPTX enhancement | `native_enhance_pptx.py` | [native-enhance-pptx](../workflows/native-enhance-pptx.md) |
| Native PPTX beautify | `beautify_pptx.py` | [beautify-pptx](../workflows/beautify-pptx.md) |
| Confirmation page | `confirm_ui.py` | [confirm-ui](../workflows/confirm-ui.md) |
| Clarification gate | `clarification_gate.py` | [clarification-gate](../workflows/clarification-gate.md) |
| Visual review | `visual_review.py`, `render_pptx_png.py`, `visual_measure_gate.py` | [visual-review](../workflows/visual-review.md) |
| Brand presets | `create_brand.py` | [create-brand](../workflows/create-brand.md) |
| Slide image reconstruction | `image_reconstruction_pipeline.py`, `slide_image_inventory.py`, `validate_image_reconstruction_pptx.py`, `validate_split_assets.py`, `compare_source_render.py` | [slide-image-to-editable-pptx](../workflows/slide-image-to-editable-pptx.md) |
| Spec maintenance | `update_spec.py`, `template_palette.py` | [docs/update_spec.md](./docs/update_spec.md) |
| Image tools | `image_gen.py`, `analyze_images.py`, `gemini_watermark_remover.py` | [docs/image.md](./docs/image.md) |
| Repo maintenance | `update_repo.py` | README install/update section |
| Troubleshooting | validation, preview, export, dependency issues | [docs/troubleshooting.md](./docs/troubleshooting.md) |

## High-Frequency Commands

Unified command hub:

```bash
python3 scripts/easyslides.py --help
python3 scripts/easyslides.py source-to-md <source-file-or-url> -o <output-dir>
python3 scripts/easyslides.py template-fill analyze <template.pptx> -o <project_path>/analysis/slide_library.json
python3 scripts/easyslides.py enhance init <source.pptx> --name <project_name>
python3 scripts/easyslides.py beautify inspect <source.pptx> --out <project_path>/reports/beautify
python3 scripts/easyslides.py workflow write-manifest <project_path> --route template-fill-pptx --stage analyze --status completed
```

Conversion:

```bash
python3 scripts/source_to_md.py <source-file-or-url> -o <output-dir>
python3 scripts/source_to_md/pdf_to_md.py <file.pdf>
python3 scripts/source_to_md/ppt_to_md.py <deck.pptx>
python3 scripts/source_to_md/doc_to_md.py <file.docx>
python3 scripts/source_to_md/excel_to_md.py <workbook.xlsx>
python3 scripts/source_to_md/web_to_md.py <url>
```

Project setup:

```bash
python3 scripts/project_manager.py init <project_name> --format ppt169
python3 scripts/project_manager.py init <project_name> --format ppt169 --kind slide_image_reconstruction
python3 scripts/project_manager.py import-sources <project_path> <source_files...> --move
python3 scripts/project_manager.py validate <project_path>
```

Slide image reconstruction:

```bash
python3 scripts/image_reconstruction_pipeline.py init <project_path> <slide_001.png>
python3 scripts/slide_image_inventory.py validate <project_path>/analysis/_analysis.json --report <project_path>/reports/slide_image_inventory_report.json
python3 scripts/image_reconstruction_pipeline.py qa <project_path> --pptx <project_path>/pptx/output.pptx --rendered-dir <project_path>/reports/rendered_png
python3 scripts/image_reconstruction_pipeline.py qa <project_path> --mode pixel-strict --pptx <project_path>/pptx/output.pptx --rendered-dir <project_path>/reports/rendered_png
```

Template source import:

```bash
python3 scripts/pptx_template_import.py <template.pptx>
python3 scripts/pptx_template_import.py <template.pptx> --manifest-only
python3 scripts/pptx_template_import.py <template.pptx> --inheritance-mode both
python3 scripts/pptx_source_graph.py <template.pptx> --output tmp/source_graph.json
python3 scripts/pptx_distill_registry.py tmp/source_graph.json --template-id <template_id> --output-dir tmp/distill_contracts
python3 scripts/pptx_design_system_compiler.py tmp/distill_contracts --template-id <template_id>
python3 scripts/pptx_projection.py build tmp/distill_contracts --template-id <template_id>
python3 scripts/pptx_template_distill.py <template.pptx> --template-id <template_id>
```

Template palette materialization:

```bash
python3 scripts/template_palette.py defense_leftnav academic_blue --output-dir tmp/defense_leftnav_academic_blue
```

Card component lookup and preview:

```bash
python3 scripts/page_recipe.py count
python3 scripts/page_recipe.py query --content-shape causal_chain --item-count 4
python3 scripts/page_recipe.py prompt --recipe-id pm_causal_map
python3 scripts/page_recipe_preview.py --output-dir outputs/page_recipe_preview_project
python3 scripts/card_library.py count
python3 scripts/card_library.py query --content-shape parallel_points --item-count 3
python3 scripts/card_library.py preview --output outputs/card_library_preview.pptx
python3 scripts/card_recipe.py count
python3 scripts/card_recipe.py query --content-shape sequence --item-count 3
python3 scripts/card_recipe.py prompt --recipe-id pm_flow_strip
```

Chart asset lookup:

```bash
python3 scripts/chart_library.py validate
python3 scripts/chart_library.py list --family quantitative
python3 scripts/chart_library.py search "trend" --limit 10
python3 scripts/component_registry.py list --granularity chart_asset
python3 scripts/component_selector.py query --content-shape chart --limit 10
```

Icon asset lookup and project preparation:

```bash
python3 scripts/icon_library.py validate
python3 scripts/icon_library.py list --family tabler-outline
python3 scripts/icon_library.py search "environment" --family tabler-outline
python3 scripts/icon_library.py sync <project_path> tabler-outline/leaf simple-icons/github
python3 scripts/component_selector.py query --content-shape icon --limit 10
```

Declarative component packs:

```bash
python3 scripts/easyslides.py component validate <pack-directory>
python3 scripts/easyslides.py component install <pack-directory>
python3 scripts/easyslides.py component install github:<owner>/<repo>@<tag>
python3 scripts/easyslides.py component list
python3 scripts/easyslides.py component update <pack-directory>
python3 scripts/easyslides.py component rollback <pack-id>
python3 scripts/easyslides.py component remove <pack-id>
python3 scripts/easyslides.py component-market search research --tag academic
python3 scripts/easyslides.py component-market install research-core
python3 scripts/easyslides.py component-workflow deck_plan.json --out build/component_workflow
python3 scripts/easyslides.py renderer-governance
```

Component packs use `pack.json` plus `components/<component_id>/component.json`
and `stories/*.json`. Packs are declarative: JSON, SVG, and image assets are
accepted, while executable pack code and runtime permissions are rejected. The
EasySlides renderer remains the trusted execution surface.

Executable template compilation:

```bash
python scripts/easyslides.py template-package rebuild --json
python scripts/easyslides.py template-capabilities validate --json
python scripts/easyslides.py template-capabilities sync --json
python scripts/easyslides.py template-compile templates/layouts/nsfc_defense --write --json
python scripts/easyslides.py slide-compile deck_plan.json --template nsfc_defense --out slide_ir.json --svg-out rendered_svg --pptx-out output.pptx --json
```

`template_package.json`, `layouts.json`, `body_variants.json`,
`component_catalog.json`, `qa_policy.json`, and `capability_profile.json` are
canonical sources. `capability_profile.json` fail-closes named-template
selection to declared local assets; use the capability command to regenerate
it after changing a template's local contracts.
`compiled/template_ir.json`, `compiled/template.lock.json`, compatibility
sidecars, and template registries are generated outputs.

PPT Master-compatible workflow gates:

```bash
python3 scripts/ppt_master_pipeline.py status <project_path>
python3 scripts/ppt_master_pipeline.py validate-phase-a <project_path>
python3 scripts/ppt_master_pipeline.py export <project_path> --dry-run
python3 scripts/ppt_master_pipeline.py export <project_path> --render-png-preview
```

Native PPTX template fill:

```bash
python3 scripts/template_fill_pptx.py analyze <template.pptx> -o <project_path>/analysis/slide_library.json
python3 scripts/template_fill_pptx.py scaffold <project_path>/analysis/slide_library.json -o <project_path>/analysis/fill_plan.json
python3 scripts/template_fill_pptx.py validate <project_path>/analysis/fill_plan.json --library <project_path>/analysis/slide_library.json
python3 scripts/template_fill_pptx.py apply <project_path>/analysis/fill_plan.json -o <project_path>/exports/filled.pptx
```

Native PPTX enhancement:

```bash
python3 scripts/native_enhance_pptx.py init <source.pptx> --name <project_name>
python3 scripts/native_enhance_pptx.py plan <project_path>
python3 scripts/native_enhance_pptx.py validate <project_path>
python3 scripts/native_enhance_pptx.py apply <project_path> --force
```

Native PPTX beautify:

```bash
python3 scripts/beautify_pptx.py inspect <source.pptx> --out <project_path>/reports/beautify
python3 scripts/beautify_pptx.py apply <source.pptx> -o <project_path>/exports/beautified.pptx --report-dir <project_path>/reports/beautify --primary "#2454A6" --accent "#E9B44C"
```

Confirmation page:

```bash
python3 scripts/confirm_ui.py <project_path> --out <project_path>/reports/confirm_ui
python3 scripts/confirm_ui.py <project_path> --out <project_path>/reports/confirm_ui --brand academic-blue
```

Visual review:

```bash
python3 scripts/visual_review.py <deck.pptx> --out <project_path>/reports/visual_review
python3 scripts/visual_review.py <deck.pptx> --out <project_path>/reports/visual_review --rendered-dir <project_path>/reports/rendered_png --skip-render
```

Brand presets:

```bash
python3 scripts/create_brand.py list
python3 scripts/create_brand.py show academic-blue
python3 scripts/create_brand.py init <brand-id> --name "<Brand Name>" --primary "#2454A6" --accent "#E9B44C"
```

Post-processing and export:

```bash
python3 scripts/validate_svg_text_slots.py <project_path>/svg_output --strict-unboxed --require-valign --check-canvas
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/svg_to_pptx.py <project_path>
python3 scripts/template_geometry_qa.py templates/layouts/<template_id> --pptx <project_path>/exports/<deck>.pptx --report <project_path>/reports/geometry_report.json
python3 scripts/validate_pptx_text_layout.py <project_path>/exports/<deck>.pptx --report <project_path>/reports/text_layout_report.json
python3 scripts/render_pptx_png.py <project_path>/exports/<deck>.pptx --out <project_path>/reports/rendered_png --report <project_path>/reports/rendered_png_report.json
python3 scripts/visual_measure_gate.py --template-dir templates/layouts/<template_id> --pptx <project_path>/exports/<deck>.pptx --report <project_path>/reports/visual_measure_report.json
python3 scripts/pptx_distill_promotion_gate.py templates/reference/template_asset_sources/<template_id> templates/layouts/<template_id> --pptx <project_path>/exports/<deck>.pptx --out <project_path>/reports/<template_id>_promotion_gate --json
python3 scripts/cross_renderer_visual_regression.py <project_path>/exports/<deck>.pptx --out <project_path>/reports/cross_renderer
```

On Windows, `render_pptx_png.py` automatically prefers installed Microsoft
PowerPoint for Office-faithful PNG export; use `--renderer soffice` to force
the LibreOffice fallback or `--renderer powerpoint` to require native
PowerPoint.

Image generation:

```bash
python3 scripts/image_gen.py "A modern futuristic workspace"
python3 scripts/image_gen.py --list-backends
python3 scripts/analyze_images.py <project_path>/images
```

Repository update:

```bash
python3 scripts/update_repo.py
python3 scripts/update_repo.py --skip-pip
```

## Recommendations

- Keep one user-facing entry point per workflow at the top level of `scripts/`
- Move provider-specific or helper internals into subdirectories
- Prefer the unified entry points `project_manager.py`, `finalize_svg.py`, and `image_gen.py`
- Prefer `svg_final/` over `svg_output/` when exporting

## Related Docs

- [Architecture](../ARCHITECTURE.md)
- [Installation](../INSTALL.md)
- [Conversion Tools](./docs/conversion.md)
- [Project Tools](./docs/project.md)
- [SVG Pipeline Tools](./docs/svg-pipeline.md)
- [Image Tools](./docs/image.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [Skill Entry](../SKILL.md)

_Last updated: 2026-04-09_
