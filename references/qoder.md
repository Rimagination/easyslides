# EasySlides for Qoder

The Qoder Plugin ZIP contains the same four canonical skills and Python runtime
as the other host adapters. The active manifest is `.qoder-plugin/plugin.json`;
`qoder.md` is the host guide. The package adds no MCP server or background service.

## Installation and first use

In Qoder's Plugins page, choose **Add plugin → Upload Plugin** and select the
ZIP. This installs it locally. Public marketplace publication is a separate
submission and review process.

Ask Qoder to use EasySlides, provide a topic or source material, and answer the
production-scheme, theme-color and theme-image questions that remain unresolved.
The default native template is `academic_general`; the package includes eight
official native templates, fourteen discipline theme images and thirteen
image-reference styles. It also supports editing and source-PPTX distillation.

Keep generated work outside the installed plugin directory. With Qoder's shell
tool, locate Python 3.10+ and run:

```sh
python "<plugin-root>/scripts/easyslides.py" doctor --json
```

If dependencies are missing, explain the setup and create a workspace-local
`.easyslides-venv`. Install `"<plugin-root>/requirements.txt"` using that
environment's Python, following the host's permission controls. Do not modify
global Python packages. The ZIP has no install hook and does not install Python,
PowerPoint, LibreOffice or image-generation tools.

PowerPoint or LibreOffice is needed for rendered previews. Evidence research
uses the host's available search tools; image generation uses an actual host
tool or the configured backend supported by `scripts/image_gen.py`. Registration
and existing theme images need no separate EasySlides API key. Do not promise
generation when the host has no suitable tool, or silently switch an approved
production scheme. See `INSTALL.md` for the shared runtime prerequisites.

## Build and publish

Check the account and publication list in the user's Qoder region. The
international portal is `qoder.com`; use
[the China portal](https://qoder.cn/account/apphub-publications) only for
a China-site account. A publication list on one portal does not establish
submission or review status on the other.

From a source checkout:

```sh
python scripts/build_qoder_plugin.py
```

The builder creates `build/qoder-plugin/easyslides/` and
`build/easyslides-qoder-<version>.zip`. Existing destinations are never replaced.
The ZIP directly contains `.qoder-plugin/plugin.json`, `qoder.md`, `skills/`,
scripts, templates, public assets and shared guidance. It excludes user projects,
source papers, credentials, development-only templates and other hosts' active
plugin manifests. Validate both the directory and the ZIP with Qoder's bundled
`create-plugin` validator before submitting a release.

Submit through [My publications](https://qoder.com/account/apphub-publications),
choosing Plugin. Provide the archive, listing and logo, then follow the current
form's requirements. Submission does not guarantee approval or public listing.
The repository's `marketplace.json` is for the existing host marketplace and is
not a substitute for submitting to Qoder.

Official references: [Plugin format](https://docs.qoder.cn/qoder-plugins),
[publication and review](https://docs.qoder.com/zh/qoderwork/skill-marketplace-guidelines).
