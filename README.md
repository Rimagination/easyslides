# EasySlides

[中文](#中文) | [English](#english)

![EasySlides: Research to editable slides](assets/easyslides-github-hero.png)

EasySlides is a **project-backed Codex skill**. `SKILL.md` is the agent
entrypoint, but real PPTX generation, template reuse, slide-image
reconstruction, and QA gates require the full repository.

- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Installation: [INSTALL.md](INSTALL.md)
- Skill entrypoint: [SKILL.md](SKILL.md)

---

## 中文

EasySlides 是一个面向学术汇报与研究型演示文稿的本地 PPTX 生成工具链。它的核心目标是把论文、报告、网页、Markdown 等来源材料转换为结构清晰、风格一致、并且可以在 PowerPoint 中继续编辑的演示文稿。

> 研究材料 -> 可追溯叙事 -> 模板与组件编排 -> 可编辑原生 PPTX

核心流程：

```text
来源材料 -> 项目工作区 -> Deck Plan -> SVG/布局模板 -> 可编辑 PPTX
```

### 核心能力

- **学术材料到叙事**：从论文、报告、数据、网页和 Markdown 建立可追溯的内容计划，优先保留用户提供的主张、图表、表格与引用。
- **PPTX 蒸馏与模板化**：把参考 PPTX 分解为稳定页面壳、内容变体、组件、几何、设计令牌与来源证据，而不是把整套页面当作不可控的图片。
- **模板受边界约束**：命名模板只能使用其声明的本地页面变体和组件；全局组件或其它模板资产不能被悄悄套用。
- **组件资产体系**：提供模板组件、卡片、页面配方、图表和图标库；组件具有输入槽位、容量、渲染器和 QA 契约。
- **原生可编辑交付**：生产链固定为 `SVG/shape IR -> DrawingML/OOXML -> PPTX`，文字、形状、颜色和图表保持可编辑。
- **Fail-closed QA**：文本容量、垂直居中、几何、视觉差异、PPTX 可编辑性与跨材料测试均为交付门禁。

### 项目结构

- `SKILL.md`：学术 PPT 工作流的主说明。
- `scripts/`：转换、项目管理、SVG 校验、模板导入、PPTX 导出等工具。
- `templates/`：学术布局模板、风格包、图表模块与图标库。
- `assets/`：README、品牌和产品级视觉资产。
- `references/`：写作规范、设计规则、执行器/策略器参考。
- `workflows/`：预览、音频、模板创建、图表验证、主题调研等扩展流程。
- `tests/`：模板契约、CLI 入口与核心工具的回归测试。

### 快速开始

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/easyslides.py --help
```

创建一个本地演示项目：

```powershell
python scripts/project_manager.py init my_presentation --format ppt169
python scripts/project_manager.py import-sources projects/my_presentation <source_files...> --copy
python scripts/project_manager.py validate projects/my_presentation
```

在完成 SVG 页面编排后导出 PPTX：

```powershell
python scripts/finalize_svg.py projects/my_presentation
python scripts/svg_to_pptx.py projects/my_presentation
```

### 常用工作流

```powershell
# 将资料转换为 Markdown，并建立项目
python scripts/easyslides.py source-to-md <source-file-or-url> -o <markdown-output>
python scripts/project_manager.py init my_presentation --format ppt169

# 从参考 PPTX 蒸馏可复用模板资产
python scripts/easyslides.py distill <template.pptx> --template-id <template_id>

# 验证模板能力边界，并编译生产模板
python scripts/easyslides.py template-capabilities validate --json
python scripts/easyslides.py template-compile templates/layouts/nsfc_defense --write --json

# 生成组件选择、候选方案和 PPTX 预览
python scripts/easyslides.py component-workflow deck_plan.json --out build/component_workflow
```

### 模板

当前可发布的学术布局模板位于 `templates/layouts/`，索引文件为 `templates/layouts/layouts_index.json`。除了通用学术、SCQA、答辩和文献汇报页面壳外，`nsfc_defense` 提供了可执行内容变体与模板局部组件。

每个模板目录都拥有 `capability_profile.json`。它定义模板是否可用于生成、允许哪些页面或组件粒度，以及是否存在局部组件包。命名模板默认拒绝未声明的全局资产；蒸馏中间目录与栅格保真目录被标记为不可直接生成。

常用维护命令：

```powershell
python scripts/easyslides.py template-capabilities validate --json
python scripts/easyslides.py template-package rebuild --json
python scripts/easyslides.py template-gate templates/layouts/nsfc_defense --json
```

### 致谢

EasySlides 在多个开源项目与公开实践的启发上继续扩展。为避免把不同层次的贡献混在一起，这里按项目所启发的能力层次致谢：

- **工程底座**：[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) 为可编辑 PPTX 生成提供了重要的工程框架、工作流组织方式与基础能力，EasySlides 在此基础上继续发展本地 SVG 到 DrawingML/PPTX 的生成链路。
- **学术表达**：[Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill) 为结构化论证、学术表达、引用规范和沟通优先的设计原则提供了重要参考。
- **叙事编排**：[LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt) 的 Audience-State-Transfer 思想提醒我们，PPT 不只是信息容器，更是观众状态转移的路径；这启发了 EasySlides 对通用学术模板、SCQA 叙事结构和页面级听众推进的规则设计。
- **风格与模板治理**：[op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) 启发了本项目对风格约束包、可复用设计规范和模板治理方式的组织。
- **论文与文献报告流程**：[xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill) 与 [fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder) 为论文汇报、文献报告和 academic PPT skills 的构建提供了有价值的思路。

本项目在上述开源工作的启发与基础上继续扩展，新增代码、模板、规则与项目组织由 EasySlides 维护；除非原项目另有说明，以上致谢不代表相关项目对 EasySlides 的正式背书。

### 发布与隐私

`projects/` 下的生成物、论文原文、导出 PPT、预览图、解包 Office XML 和本地 QA 输出默认不会进入 Git。建议只提交可复用代码、模板、测试和文档。

API Key 请放在环境变量或本地 `.env` 中，不要提交真实密钥。`.env.example` 仅用于说明支持的配置项。

[Back to top](#easyslides)

---

## English

EasySlides is a local PPTX generation toolchain for academic talks and research presentations. Its goal is to turn papers, reports, web pages, Markdown, and other source materials into structured, visually consistent, and PowerPoint-editable decks.

> Research material -> traceable narrative -> template and component composition -> editable native PPTX

It is a project-backed skill: installing only `SKILL.md` gives an agent the
routing guide, while installing the full repository provides the runtime,
templates, workflows, and QA gates required for actual PPTX generation. See
[ARCHITECTURE.md](ARCHITECTURE.md) and [INSTALL.md](INSTALL.md).

Core pipeline:

```text
source material -> project workspace -> deck plan -> SVG/layout templates -> editable PPTX
```

### What It Does

- **Research material to narrative**: turns papers, reports, data, web pages, and Markdown into traceable deck plans while preserving supplied claims, figures, tables, and citations.
- **PPTX distillation and templating**: extracts stable shells, body variants, components, geometry, design tokens, and provenance from reference decks instead of treating them as opaque page images.
- **Bounded templates**: a named template can select only its declared local variants and components. Global or cross-template assets cannot silently leak into a deck.
- **Component assets**: template components, cards, page recipes, charts, and icons carry slot, capacity, renderer, and QA contracts.
- **Editable native delivery**: the production path is `SVG/shape IR -> DrawingML/OOXML -> PPTX`, keeping text, shapes, colors, and charts editable.
- **Fail-closed QA**: content capacity, vertical alignment, geometry, visual difference, editability, and cross-material checks are delivery gates.

### Repository Layout

- `SKILL.md`: main operating guide for the academic PPT workflow.
- `scripts/`: utilities for conversion, project management, SVG validation, template import, and PPTX export.
- `templates/`: academic layout templates, style packs, chart modules, and icon libraries.
- `assets/`: README, brand, and product-level visual assets.
- `references/`: authoring standards, design rules, strategist/executor guidance.
- `workflows/`: optional flows for preview, audio, template creation, chart verification, and topic research.
- `tests/`: regression tests for template contracts, CLI entry points, and core tools.

### Quick Start

```powershell
python scripts/project_manager.py setup-pdf-tools --install
python -m pytest -q
python scripts/easyslides.py --help
```

Create a local deck project:

```powershell
python scripts/project_manager.py init my_presentation --format ppt169
python scripts/project_manager.py import-sources projects/my_presentation <source_files...> --copy
python scripts/project_manager.py validate projects/my_presentation
```

For paper-PPT workflows that require structured figures/tables, add
`--require-structured-pdf` to `import-sources`. The strict scholarly extraction
chain is `MinerU -> PDFFigures2 -> fail fast`; it does not silently fall back to
plain PyMuPDF text extraction. `--require-mineru` is kept as a compatibility
alias for the same strict mode. On first use, run
`python scripts/project_manager.py setup-pdf-tools --install`; it installs
Python requirements, checks MinerU token configuration, builds PDFFigures2, and
writes `PDFFIGURES2_JAR` to local `.env`. Configure PDFFigures2 manually with
`PDFFIGURES2_CMD` (a command template using `{pdf}` and `{out}`) or
`PDFFIGURES2_JAR`.

Export a PPTX after authoring SVG pages:

```powershell
python scripts/finalize_svg.py projects/my_presentation
python scripts/svg_to_pptx.py projects/my_presentation
```

### Common Workflows

```powershell
# Convert source material and create a project
python scripts/easyslides.py source-to-md <source-file-or-url> -o <markdown-output>
python scripts/project_manager.py init my_presentation --format ppt169

# Distill reusable template assets from a reference PPTX
python scripts/easyslides.py distill <template.pptx> --template-id <template_id>

# Validate template boundaries and compile a production template
python scripts/easyslides.py template-capabilities validate --json
python scripts/easyslides.py template-compile templates/layouts/nsfc_defense --write --json

# Produce component choices, review material, and a PPTX preview
python scripts/easyslides.py component-workflow deck_plan.json --out build/component_workflow
```

### Templates

Active academic layout templates live under `templates/layouts/` and are indexed in `templates/layouts/layouts_index.json`. Alongside general academic, SCQA, defense, and literature-report shells, `nsfc_defense` provides executable body variants and template-local components.

Every template directory owns a `capability_profile.json`. It declares whether the directory can generate decks, which page/component granularities are permitted, and whether a local component pack exists. Named templates reject undeclared global assets by default; distilled and raster-faithful directories are source-scoped rather than direct generation templates.

Useful maintenance commands:

```powershell
python scripts/easyslides.py template-capabilities validate --json
python scripts/easyslides.py template-package rebuild --json
python scripts/easyslides.py template-gate templates/layouts/nsfc_defense --json
```

### Acknowledgements

EasySlides builds on several open-source projects and public practices. To keep the credits readable, we group them by the layer of capability they inspired:

- **Engineering foundation**: [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) provided important engineering architecture, workflow organization, and foundational capabilities for editable PPTX generation. EasySlides extends that foundation with its local SVG-to-DrawingML/PPTX pipeline.
- **Academic communication**: [Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill) provided important references for structured argument, academic communication, citation standards, and communication-first design.
- **Narrative orchestration**: [LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt) contributed an important Audience-State-Transfer perspective: a deck is not merely an information container, but a path for audience-state transfer. This influenced EasySlides' general academic templates, SCQA narrative structure, and page-level audience progression rules.
- **Style and template governance**: [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) inspired the way this project organizes style constraint packs, reusable design specifications, and template governance.
- **Paper and literature report workflows**: [xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill) and [fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder) offered valuable ideas for paper presentations, literature reports, and academic PPT skills.

EasySlides extends these open-source inspirations with its own code, templates, rules, and project structure. Unless otherwise stated by the upstream projects, these acknowledgements do not imply formal endorsement of EasySlides by the referenced projects.

### Publishing And Privacy

Generated decks, source papers, exported PPTX files, rendered previews, unpacked Office XML, and local QA outputs under `projects/` are ignored by default. Commit reusable code, templates, tests, and documentation; keep private source material and generated artifacts local unless they are explicitly cleared for publication.

API keys should live in environment variables or a local `.env`; never commit real credentials. Use `.env.example` only as a template for supported configuration values.

[Back to top](#easyslides)
