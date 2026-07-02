# PPT Master Toolset

This directory contains user-facing scripts for conversion, project setup, SVG processing, export, recorded narration, and image generation.

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
| Conversion | `source_to_md/pdf_to_md.py`, `source_to_md/doc_to_md.py`, `source_to_md/excel_to_md.py`, `source_to_md/ppt_to_md.py`, `source_to_md/web_to_md.py` | [docs/conversion.md](./docs/conversion.md) |
| Project management | `project_manager.py`, `batch_validate.py`, `generate_examples_index.py`, `error_helper.py`, `pptx_template_import.py`, `pptx_template_distill.py` | [docs/project.md](./docs/project.md), [pptx-to-easyslides-template](../workflows/pptx-to-easyslides-template.md) |
| SVG pipeline | `finalize_svg.py`, `svg_to_pptx.py`, `total_md_split.py`, `svg_quality_checker.py`, `validate_svg_text_slots.py`, `template_geometry_qa.py`, `validate_pptx_text_layout.py`, `render_pptx_png.py`, `pptx_visual_diff.py`, `visual_measure_gate.py`, `animation_config.py`, `notes_to_audio.py` | [docs/svg-pipeline.md](./docs/svg-pipeline.md) |
| Page layout recipes | `page_recipe.py`, `page_recipe_preview.py` | [templates/page_layouts/ppt-master-page-recipes-manual.md](../templates/page_layouts/ppt-master-page-recipes-manual.md) |
| Card components | `card_library.py`, `card_recipe.py` | [templates/cards/assembly-manual.md](../templates/cards/assembly-manual.md), [templates/cards/visual-recipes-manual.md](../templates/cards/visual-recipes-manual.md) |
| PPT Master compatibility | `ppt_master_pipeline.py` | [workflows/ppt-master-compat.md](../workflows/ppt-master-compat.md) |
| Slide image reconstruction | `image_reconstruction_pipeline.py`, `slide_image_inventory.py`, `validate_image_reconstruction_pptx.py`, `validate_split_assets.py`, `compare_source_render.py` | [slide-image-to-editable-pptx](../workflows/slide-image-to-editable-pptx.md) |
| Spec maintenance | `update_spec.py`, `template_palette.py` | [docs/update_spec.md](./docs/update_spec.md) |
| Image tools | `image_gen.py`, `analyze_images.py`, `gemini_watermark_remover.py` | [docs/image.md](./docs/image.md) |
| Repo maintenance | `update_repo.py` | README install/update section |
| Troubleshooting | validation, preview, export, dependency issues | [docs/troubleshooting.md](./docs/troubleshooting.md) |

## High-Frequency Commands

Conversion:

```bash
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

PPT Master-compatible workflow gates:

```bash
python3 scripts/ppt_master_pipeline.py status <project_path>
python3 scripts/ppt_master_pipeline.py validate-phase-a <project_path>
python3 scripts/ppt_master_pipeline.py export <project_path> --dry-run
python3 scripts/ppt_master_pipeline.py export <project_path> --render-png-preview
```

Post-processing and export:

```bash
python3 scripts/validate_svg_text_slots.py <project_path>/svg_output --strict-unboxed
python3 scripts/total_md_split.py <project_path>
python3 scripts/finalize_svg.py <project_path>
python3 scripts/svg_to_pptx.py <project_path>
python3 scripts/template_geometry_qa.py templates/layouts/<template_id> --pptx <project_path>/exports/<deck>.pptx --report <project_path>/reports/geometry_report.json
python3 scripts/validate_pptx_text_layout.py <project_path>/exports/<deck>.pptx --report <project_path>/reports/text_layout_report.json
python3 scripts/render_pptx_png.py <project_path>/exports/<deck>.pptx --out <project_path>/reports/rendered_png --report <project_path>/reports/rendered_png_report.json
python3 scripts/visual_measure_gate.py --template-dir templates/layouts/<template_id> --pptx <project_path>/exports/<deck>.pptx --report <project_path>/reports/visual_measure_report.json
```

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
