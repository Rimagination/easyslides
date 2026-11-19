# DeepSeek Harness host adapter

The npm bundle registers `easyslides`, `easyslides-distill`,
`easyslides-clarify` and `video` through DSH's native skill provider. Use the host's `skill`
loader; the loaded skill names its absolute runtime directory. Relative paths
in that skill resolve from its `resourceBase`, so `../../SKILL.md` is the shared
operating guide. This adapter uses the same templates and Python commands as
Codex and ZCode.

## First use and tools

- Keep package files read-only. Create presentations and environments in the
  user's working directory, outside the npm package and `node_modules`.
- Check Python 3.10+ and run `python "<runtime>/scripts/easyslides.py" doctor --json`
  using the host's available shell tool. Use `python3` on systems where that is
  the executable name. If dependencies are missing, create a workspace-local
  `.easyslides-venv`, install `"<runtime>/requirements.txt"` there, then run the
  scripts with that environment's Python. Explain this first-use setup; follow
  the host's existing permission controls. Do not change global Python packages.
- Inspect the doctor's runtime root and same-named user skill. A user-level
  `~/.agents/skills/easyslides` can shadow the npm provider; upgrading npm alone
  then does not update the loaded instructions. Use the absolute runtime from
  the skill actually loaded, and report a mismatch before authoring. Do not
  modify package code to work around a contract error.
- For new native academic content, read `academic-native-authoring.md` and
  `scientific-composition.md` before planning. Use the versioned page contract,
  source-backed figures/diagrams and complementary comparisons. Do not increase
  density by filling text quotas or repeating the title around a chart.
- Verify model image input from declared capability or an actual successful
  image read. Pass `doctor --image-input unavailable` if image reading fails;
  exporting PNGs does not change that capability. Run `academic-gate` on the
  final PPTX. A non-visual model must leave `needs_visual_review` until a human
  or capable image model has inspected every rendered page. Never describe a
  pixel/ink measurement as visual review or quietly switch the user's model.
- DSH plugin installation has no pip/postinstall hook and requires no API key
  merely to register skills or use existing theme images. Rendering requires
  Microsoft PowerPoint or LibreOffice as described in `INSTALL.md`.
- Ask unresolved choices through the host's user-question tool when available;
  otherwise ask in the conversation and wait. Do not refer to Codex-only tool
  names as if DSH supplied them. Do not skip the production-scheme choice,
  theme color or theme-image source. For native production with no explicit
  template, use `academic_general`; use its discipline theme images only when
  `template_assets` was chosen, and respect `generate_new` or `user_provided`. Inspect
  the material for discipline, presenter, institution and date; ask only for
  unresolved information and respect omissions.
- Use host search/fetch tools for evidence. Only use an image generator the host
  actually supplies or a user-configured backend supported by
  `scripts/image_gen.py`. When unavailable, explain the missing capability and
  let the user supply images or select native production with existing assets.
  Do not silently change an approved production scheme.
- Extract PDF research figures with `figure-extract` before page planning;
  reuse parser layout JSON when present. Keep complete axes, shared legends
  and verified paper figure numbers. Parser region IDs are not figure numbers.
  Image reading is for review, not the default source of hand-picked crop boxes.

## Installation and compatibility

Enter **`easyslides`** in DSH's Add plugin package field,
or run `dsh plugin --profile desktop add easyslides` (`web` for a web profile).
Enable the bundle when the host offers it. It contributes skills, with no extra
MCP server, duplicate tool service, or changes to model/provider settings.

The package declares DSH `>=0.2.2-rc.1 <0.3.0` and Node.js `>=24.9.0`.
The skill-provider integration is tested against DSH skill service
`0.2.2-rc.1` and Cordis `4.1.0`. This does not establish compatibility with
unreleased API changes or replace a real end-to-end presentation review.

Maintainers: `npm run build` stages the existing privacy-safe plugin bundle in
`runtime/`; `npm pack` runs the same build via `prepack`. `files` only allows
`dsh/` and `runtime/` plus npm's standard README, license and package manifest.
There is no `install`, `postinstall` or `prepare` hook. Inspect the tarball before
publishing; building and packing do not publish anything.

Official references: [bundle format and installation](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.zh.md),
[skill-provider contract](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md).
