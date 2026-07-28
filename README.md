# EasySlides

[中文](#中文) | [English](#english)

![EasySlides: Research to editable slides](assets/easyslides-github-hero.png)

## 中文

**EasySlides 是一个 AI Agent 插件，面向学术报告与研究型演讲稿的本地 PPTX 生成工具。**它的核心目标是将论文、网页、Markdown 等来源材料转换为结构清晰、风格一致，并且可以在 PowerPoint 中继续编辑的演讲稿。

你不需要学习代码、版式语法或复杂的制作流程。只要用自然语言说明你的汇报场景、提供已有材料，并在信息不够明确时回答 EasySlides 的追问，它会先理解研究问题、听众、叙事目标和版式约束，再完成内容组织、页面编排与可编辑 PPTX 的交付。

> 从研究材料出发，用自然语言协作，生成真正能继续修改和使用的学术 PPT。

### 核心优势

- **先理解材料，再开始排版**：论文、报告、网页和 Markdown 不会被粗暴地塞进固定页面。EasySlides 会梳理论点、证据、图表、引用和叙事顺序，把“资料”转成适合讲述的演讲稿结构。
- **不清楚就先问，不靠猜**：当汇报对象、页数、研究重点、模板选择或素材用途不明确时，Agent 会通过可选择的问题确认关键信息，再继续制作。
- **模板是设计能力，不是僵硬页数**：模板由设计语言、稳定页面壳、内容变体和可复用组件组成。它既保留统一风格，也能根据材料选择合适的图文、对比、流程、数据和结论表达方式。
- **从现有 PPT 中提炼可复用风格**：可以把参考 PPT 蒸馏成可执行的模板，保留其内容组织、布局规律、组件表达与视觉秩序，而不是只截取几张不能复用的图片。
- **交付的是原生可编辑 PPTX**：文字、形状、颜色、图表和页面结构都能在 PowerPoint 中继续修改。项目在本地工作区处理材料与生成结果，便于保留研究资料的控制权。
- **把细节当作硬约束**：文字容量、容器中的垂直居中、对齐、几何关系、模板边界和视觉差异都经过质量检查，避免“大框里挤几行字”或“看起来像模板却不好讲”的页面。

### 与常见方案的区别

| 关注点 | EasySlides | 常见云端 AI PPT 工具 | 传统模板与排版工具 | 代码型幻灯片工具 |
| --- | --- | --- | --- | --- |
| 使用方式 | 通过自然语言与 Agent 协作 | 通常由提示词生成后手动调整 | 主要靠人工拖拽与排版 | 需要编写代码或标记语言 |
| 对研究材料的处理 | 从论点、证据、图表和引用出发组织叙事 | 更擅长快速概括与视觉初稿 | 依赖用户先整理好内容 | 依赖开发者自行准备内容与结构 |
| 模板复用 | 蒸馏设计语言、页面壳、内容变体与组件 | 多为主题皮肤或固定版式 | 多为静态母版和单页素材 | 可复用组件强，但设计和内容规则需自行实现 |
| 可编辑交付 | 原生 PPTX，便于在 PowerPoint 接力修改 | 取决于平台的导出能力 | 原生 PPTX | 取决于所选渲染链路 |
| 质量控制 | 内容容量、对齐、模板边界和视觉检查进入交付门槛 | 通常以生成结果为主，需人工复核 | 主要靠人工检查 | 主要靠开发者自行测试 |

EasySlides 的重点不是取代所有演示工具，而是把“读懂研究材料、讲清研究故事、保持模板秩序、交付可编辑文件”连成一个完整的本地工作流。

### 快速开始

在 Codex 或支持安装技能的 AI Agent 对话中，直接发送下面这句话：

> 请帮我安装这个插件：
> [Rimagination/easyslides](https://github.com/Rimagination/easyslides)

安装完成后，直接像与研究助理沟通一样提出任务。例如：

- “把这篇论文做成 15 页的组会汇报，突出研究问题、方法和实验结论。”
- “参考这份答辩 PPT 的风格，蒸馏出一个可复用模板，再用我的开题材料做一套新 PPT。”
- “材料里缺少研究对象和汇报时长时，先问我，不要自行补全。”

### 应用案例：从论文到组会汇报

以经典论文 *Attention Is All You Need* 为例，用户只需说明“我要做一次面向实验室同学的论文精读汇报，重点讲 Transformer 为什么有效”。EasySlides 会先确认听众背景、页数与讲述重点，然后组织出问题背景、核心方法、关键结构、实验结果、局限与讨论等页面；需要时保留论文图表和引用来源，并为每一页选择最匹配的内容变体。

最终得到的不是一份只能观看的长图，而是一套可以在 PowerPoint 中修改标题、替换图表、补充实验并继续演讲的 PPTX。案例站中已经展示了 Transformer 文献汇报、两种答辩版式及其真实页图。

### 模板与案例展厅

访问 [EasySlides 模板与案例展厅](http://easyslides.scansci.com/) 查看现有案例、模板名称、真实页图和可下载的 PPTX。

模板不是“封面加几张固定内容页”。在 EasySlides 中，一个模板包含：

- **设计语言**：字体、色彩、留白、标题层级和视觉节奏。
- **稳定页面壳**：如封面、目录、章节页、内容页和结束页；没有目录的参考 PPT 也不会被强行补上目录。
- **内容变体**：根据材料选择图文并列、流程、对比、研究路径、数据洞察、方法拆解或结论聚焦等表达，而不是让所有内容页长得一样。
- **组件资产**：标题栏、导航、卡片、图表、图标、标注和局部装饰都有明确的用途、容量和对齐规则。

### 隐私与交付

EasySlides 以本地项目工作区组织材料与生成结果。论文原文、参考 PPT、预览图、导出的演示文件和本地质量检查结果默认不提交到 Git。请只在明确授权后再发布包含私人研究材料的内容。

<details>
<summary><strong>项目结构与开发信息</strong></summary>

<br>

日常使用不需要直接操作这些目录；它们用于让 Agent、模板和质量检查协同工作。

| 目录或文件 | 用途 |
| --- | --- |
| `SKILL.md` | Agent 的主操作说明与任务路由。 |
| `scripts/` | 材料转换、项目管理、模板蒸馏、渲染、PPTX 导出与检查工具。 |
| `templates/` | 页面模板、内容变体、组件、图表与图标资产。 |
| `assets/` | README 与产品视觉资源。 |
| `references/` | 写作、叙事、设计与质量规则。 |
| `workflows/` | 预览、模板创建、图表验证等扩展工作流。 |
| `tests/` | 模板契约、命令入口与核心能力的回归测试。 |

EasySlides 参考并扩展了 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)、[Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill)、[LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt)、[op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)、[xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill) 和 [fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder) 的公开实践。上述致谢不代表这些项目对 EasySlides 的正式背书。

</details>

[回到顶部](#easyslides)

---

## English

**EasySlides is an AI Agent plugin for creating local, editable PPTX decks for academic talks and research presentations.** It turns papers, web pages, Markdown, and other source material into presentations with a clear story, coherent visual language, and native PowerPoint editability.

Users work in natural language. Describe the presentation, provide materials, and answer clarification questions when the brief is incomplete. EasySlides then identifies the research question, audience, narrative objective, and design constraints before building the deck.

### Why EasySlides

- **Material-aware storytelling**: it organizes claims, evidence, figures, citations, and narrative sequence before layout begins.
- **Clarification by default**: ambiguous audience, timing, scope, template, or source usage is resolved through questions instead of silent guessing.
- **Templates with range**: a template contains design language, stable page shells, body variants, and reusable components, rather than a small fixed set of pages.
- **Reusable PPTX distillation**: reference decks can become reusable template assets that retain their visual hierarchy, content organization, and component language.
- **Native editable delivery**: text, shapes, colors, charts, and page structure remain editable in PowerPoint.
- **Quality gates**: capacity, vertical centering, alignment, geometry, template boundaries, and visual checks are treated as delivery requirements.

### How It Compares

| Focus | EasySlides | General cloud AI deck tools | Traditional templates | Code-first slide tools |
| --- | --- | --- | --- | --- |
| Interaction | Natural-language collaboration with an Agent | Generate, then manually adjust | Manual authoring | Code or markup |
| Research material | Narratives built from claims, evidence, figures, and citations | Fast summaries and visual drafts | User prepares all structure | Developer prepares content and structure |
| Template reuse | Distilled shells, variants, and components | Themes or fixed layouts | Static masters and page assets | Reusable components, implemented by the developer |
| Delivery | Native editable PPTX | Export capability varies by platform | Native PPTX | Depends on the rendering path |
| Review | Capacity, alignment, template, and visual gates | Usually a manual review step | Manual review | Developer-defined tests |

### Get Started

In Codex or an AI Agent that supports skill installation, simply say:

> Please install this plugin: [Rimagination/easyslides](https://github.com/Rimagination/easyslides)

Then speak naturally, for example: “Turn this paper into a 15-slide journal-club deck and focus on the research question, method, and results.”

### Gallery

See real slide pages, templates, and downloadable examples in the [EasySlides gallery](http://easyslides.scansci.com/).

<details>
<summary><strong>Repository structure and credits</strong></summary>

<br>

`SKILL.md` routes Agent tasks; `scripts/` contains conversion, distillation, rendering, export, and QA utilities; `templates/` contains layouts, variants, components, charts, and icons; `references/` records authoring and design rules; and `tests/` protects the core contracts.

EasySlides builds on public practice and inspiration from [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master), [Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill), [LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt), [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill), [xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill), and [fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder). These acknowledgements do not imply formal endorsement.

</details>

[Back to top](#easyslides)
