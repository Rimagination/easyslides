# EasySlides Installation

EasySlides is a project-backed Codex skill. The skill entrypoint is useful for
agent routing, but the actual PPTX generation and QA capabilities require this
repository and its local runtime.

## Installation Levels

### Level 1: Minimal Skill Install

Use this when an agent only needs to understand how EasySlides should be used.

Install or expose:

- `SKILL.md`
- `ARCHITECTURE.md`
- `workflows/`
- selected `references/` documents

Capabilities:

- Route tasks into EasySlides paths.
- Explain the architecture and required project workflow.
- Tell the user which commands should be run.

Limitations:

- Cannot generate PPTX.
- Cannot run QA gates.
- Cannot use templates, scripts, or local assets unless the repo is also
  present.

This level is documentation-only.

### Level 2: Full Local Runtime

Recommended for normal users who want real decks.

Install or clone the whole repository:

```powershell
git clone https://github.com/Rimagination/easyslides.git
cd easyslides
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify the local runtime:

```powershell
python scripts/project_manager.py help
python scripts/image_reconstruction_pipeline.py --help
python scripts/easyslides.py doctor --json
```

Capabilities:

- Create local EasySlides projects.
- Import source material.
- Generate editable PPTX through the SVG/DrawingML backend.
- Reuse templates, page recipes, cards, icons, and chart modules.
- Run text, structure, asset, render, and visual QA gates.
- Run slide-image reconstruction projects.

This is the default installation mode.

Python 3.10 or newer is required. On macOS/Linux activate the environment with
`source .venv/bin/activate`. On Windows, requirements include the PowerPoint COM
bridge; Microsoft PowerPoint itself must be installed separately. LibreOffice
is the alternative renderer. `doctor` reports unavailable or unverified optional
capabilities explicitly; it does not generate images or consume an image quota.

### Portable Plugin Bundle

Maintainers can build a physical plugin directory without local materials:

```powershell
python scripts/build_plugin_bundle.py --out build/plugin-bundle/easyslides
```

Use a new output directory each time; existing directories are never replaced.
The bundle contains the runtime, three skills, seven native templates, thirteen
image-reference styles, and installation/license documents. It excludes private
source documents, local projects, browser caches, tests, and deck outputs.
Install its `requirements.txt` in a fresh environment and run the commands above
from the bundle root. Building a bundle does not register it in Codex, install
host tools, or publish anything online.

### Level 3: Developer Mode

Use this when editing EasySlides itself.

Start with Full Local Runtime, then run the broader test set relevant to your
change:

```powershell
python -m pip install pytest opencv-python-headless
python -m pytest
```

Useful targeted tests:

```powershell
python -m pytest tests/test_cli_entrypoints.py
python -m pytest tests/test_image_reconstruction_pipeline.py
python -m pytest tests/test_validate_pptx_text_layout.py
python -m pytest tests/test_visual_measure_gate.py
```

Developer mode includes:

- Full repository.
- Tests.
- Local generated examples in `projects/`, `outputs/`, and `tmp/`.
- Template and QA development.

Do not commit private source documents, generated decks, rendered previews, or
real credentials.

## Optional External Tools

Different workflows need different tools.

### PowerPoint / Office

Useful for:

- Manual inspection.
- COM-based rendering on Windows when LibreOffice is unavailable.
- Final compatibility checks.

### LibreOffice

Useful for:

- Headless PPTX rendering.
- CI-style render checks.

The wrapper is:

```powershell
python scripts/render_pptx_png.py <deck.pptx> --out <project>/reports/rendered_png
```

### Poppler

Useful when rendering via PDF intermediates. Install `pdftoppm` if your render
path depends on it.

### MinerU / PDFFigures2

Useful for scholarly paper ingestion with structured figures and tables.

Setup helper:

```powershell
python scripts/project_manager.py setup-pdf-tools --install
```

Strict paper workflows can use:

```powershell
python scripts/project_manager.py import-sources <project> <paper.pdf> --require-structured-pdf
```

### OCR / Image Backends

Slide-image reconstruction may benefit from OCR and image processing backends.
Keep API keys in environment variables or local `.env`; never commit real
tokens.

The optional annotation-assisted tracing scripts additionally need
`opencv-python-headless` and `vtracer`. These experiment helpers are separate
from the default SVG/DrawingML export and do not replace source-image review.

## Common Workflows

### Create A Normal Deck Project

```powershell
python scripts/project_manager.py init my_presentation --format ppt169
python scripts/project_manager.py import-sources projects/my_presentation <source_files...> --copy
python scripts/project_manager.py validate projects/my_presentation
```

After authoring SVG pages:

```powershell
python scripts/finalize_svg.py projects/my_presentation
python scripts/svg_to_pptx.py projects/my_presentation
```

### Create A Slide Image Reconstruction Project

```powershell
python scripts/project_manager.py init screenshot_case --format ppt169 --kind slide_image_reconstruction
python scripts/image_reconstruction_pipeline.py init projects/screenshot_case_ppt169_<date> slide_001.png --production-scheme <confirmed_scheme> --reconstruction-mode <confirmed_mode>
```

Ask the user first. `confirmed_scheme` is `image_full_rebuild` or
`image_partial_rebuild`; `confirmed_mode` is `full_vector` or
`preserve_complex_images`. Neither choice has an automatic default.

After assembly/export:

```powershell
python scripts/image_reconstruction_pipeline.py qa projects/screenshot_case_ppt169_<date> --pptx projects/screenshot_case_ppt169_<date>/pptx/output.pptx --rendered-dir projects/screenshot_case_ppt169_<date>/reports/rendered_png
```

Use strict pixel acceptance only when required:

```powershell
python scripts/image_reconstruction_pipeline.py qa projects/screenshot_case_ppt169_<date> --mode pixel-strict --pptx projects/screenshot_case_ppt169_<date>/pptx/output.pptx --rendered-dir projects/screenshot_case_ppt169_<date>/reports/rendered_png
```

## Skill Installation Boundary

Run `python scripts/easyslides.py doctor` for environment diagnostics.
`needs_verification` means a capability still needs a real invocation, such as
PowerPoint rendering. Installing `win32com` or an imagegen skill file alone does
not establish that the corresponding application/tool is callable. The host may
explicitly declare native imagegen with `EASYSLIDES_HOST_IMAGEGEN=1`; this declares
a handoff path and does not test generation or report an image quota.

If a platform asks to install "the EasySlides skill", be explicit about what is
being installed:

- Installing only `SKILL.md` installs the routing guide.
- Installing the full repository installs the runtime.
- Real PPTX generation requires the repository runtime or its complete portable bundle.

Recommended wording:

```text
EasySlides is a project-backed skill. Install the skill entrypoint for routing,
but install the full EasySlides repository for PPTX generation, template reuse,
slide-image reconstruction, and QA gates.
```

## Environment And Secrets

- Use environment variables or local `.env`.
- Use `.env.example` only as a template.
- Do not commit API keys, tokens, private source documents, generated PPTX
  files, rendered previews, or unpacked Office XML.

## Troubleshooting

If a command cannot import modules:

```powershell
python -m pip install -r requirements.txt
```

If rendering fails:

- Check whether LibreOffice is installed and on `PATH`.
- Use PowerPoint COM on Windows when available.
- Run `python scripts/render_pptx_png.py --help`.

If image reconstruction QA fails:

- Inspect `reports/source_render_diff/source_render_contact.png`.
- Fix Layer A/B/C inventory before hiding issues in the final deck.
- Use `preserve_source_frame` for complex raster illustrations.
- Use masked source assets with transparent padding for closed shapes.

If text layout QA fails:

- Inspect `reports/text_layout_report.json`.
- Shorten text, split slides, or choose a larger slot.
- Do not shrink readable text below the configured floor.
