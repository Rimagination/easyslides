<div align="center" id="中文">

<p align="center">
  <img src="assets/logo.png" alt="EasySlides Logo" width="128" height="128">
</p>

<h1 align="center">EasySlides</h1>

<p align="center">
  <a href="CHANGELOG.md"><img alt="Version: 1.1.0" src="https://img.shields.io/badge/Version-v1.1.0-2563EB?style=flat-square"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-16A34A?style=flat-square"></a>
  <img alt="Output: Editable PPTX" src="https://img.shields.io/badge/Output-Editable%20PPTX-D24726?style=flat-square">
</p>

让 Agent 把研究材料做成可编辑 PPT，支持直接制作、AI 生图后整页重建与局部重建。

[中文](#中文) | [English](#english)

</div>

### 模板与案例展厅

**[进入展厅，先看看效果](http://easyslides.scansci.com/)**

| [成品展示](http://easyslides.scansci.com/?library=native#catalog) | [图片参考模板](http://easyslides.scansci.com/?library=image#catalog) |
| --- | --- |
| 用于直接制作可编辑 PPT，含真实案例 | 用整套缩略图指导 AI 生图风格 |

也可以提供自己的 PPT 或参考图片。

### 开始使用

把下面这句话发给 Codex 或支持技能安装的 AI Agent：

> 请帮我安装 EasySlides 的完整仓库和运行依赖，并检查能否生成 PPT：[Rimagination/easyslides](https://github.com/Rimagination/easyslides)

安装完成后，直接提出任务：

> 把这篇论文做成 15 页的组会汇报，突出研究问题、方法和实验结论。先让我选择制作方案。

需要完整仓库和本地依赖，详见 [安装指南](INSTALL.md)。下方生图路线使用 Codex 的 `imagegen`，需在宿主中可用。

### 选择制作方式

制作前会请你确认方案，并说明预计耗时与 Token 消耗。

![EasySlides 三种制作路线：直接生成可编辑 PPT、AI 生图后整页重建、AI 生图后局部重建](assets/easyslides-workflow.svg)

重建范围内的文字可直接编辑；保留的配图与未选区域仍为图片。详见 [重建说明](workflows/slide-image-to-editable-pptx.md)。

文件在本地管理；提交给云端 AI 的材料由对应服务处理，私人资料经你授权后再发布。

<details>
<summary><strong>开发与致谢</strong></summary>

开发文档：[架构说明](ARCHITECTURE.md) · [工作流入口](workflows/index.md)。

EasySlides 的开发借鉴了以下公开项目的实践：

- 可编辑 PPTX 与本地生成：[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)、[Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill)。
- 学术表达：[LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt)。
- 风格与模板管理：[op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)。
- 论文与文献报告：[xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill)、[fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder)。

致谢不代表这些项目对 EasySlides 的正式背书。代码许可见 [LICENSE](LICENSE)；引用、上传或再分发第三方模板与图片时，请确认对应素材的授权。

</details>

[回到顶部](#easyslides)

---

## English

Turn research material into editable PPT with an AI Agent.

### Template and Example Gallery

**[Explore the gallery](http://easyslides.scansci.com/)**

| [Showcase Decks](http://easyslides.scansci.com/?library=native#catalog) | [Image References](http://easyslides.scansci.com/?library=image#catalog) |
| --- | --- |
| Editable PPT creation, with real examples | Whole-deck thumbnails to guide AI-generated slide design |

You can also supply your own PPTX or reference images.

### Get Started

In Codex or an Agent that supports skill installation, say:

> Please install the full [EasySlides repository](https://github.com/Rimagination/easyslides) and its runtime dependencies, and check that it can generate PPTX files.

Then ask:

> Turn this paper into a 15-slide journal-club presentation. Focus on the research question, methods, and results. Ask me to choose a production method first.

See the [installation guide](INSTALL.md) for the full repository and dependencies. Image-based methods require Codex `imagegen` in your host.

### Choose Your Method

EasySlides confirms your method and explains expected time and token usage before starting.

Choose **direct editable PPT**, **AI images with full-slide reconstruction**, or **AI images with annotated-region reconstruction**. Image-based methods offer full-vector rebuilding or preservation of complex pictures.

Rebuilt text stays editable; preserved pictures and unselected regions remain images. See the [reconstruction guide](workflows/slide-image-to-editable-pptx.md).

Files stay in your workspace; cloud AI processes the material you send to it. Confirm permission before sharing sensitive research or publishing private files.

<details>
<summary><strong>Implementation and Credits</strong></summary>

See [ARCHITECTURE.md](ARCHITECTURE.md) and [INSTALL.md](INSTALL.md) for development details.

EasySlides draws on public practice from [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master), [Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill), [LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt), [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill), [xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill), and [fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder). Acknowledgement does not imply endorsement. See [LICENSE](LICENSE) for the code license; third-party templates and images require their own permissions.

</details>

[Back to top](#easyslides)
