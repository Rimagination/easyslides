<p align="center">
  <img src="assets/logo.png" alt="EasySlides Logo" width="128" height="128">
</p>

# EasySlides

[中文](#中文) | [English](#english)

<p align="center">
  <img alt="AI Agent Plugin" src="https://img.shields.io/badge/AI%20Agent-Plugin-2563EB?style=flat-square">
  <img alt="Output: PPTX" src="https://img.shields.io/badge/Output-PPTX-D24726?style=flat-square">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-16A34A?style=flat-square"></a>
</p>

## 中文

**用自然语言，把研究材料做成能讲、能改的 PPT。**

EasySlides 是面向组会、文献精读、开题和答辩的 AI Agent 插件。提供论文、报告或参考 PPT，说明听众和重点，即可开始制作。

当前版本：**1.1.0** · [更新与升级说明](CHANGELOG.md)

### 模板与案例展厅

**[进入展厅，先看看效果](http://easyslides.scansci.com/)**

| [原生模板](http://easyslides.scansci.com/?library=native#catalog) | [图片参考模板](http://easyslides.scansci.com/?library=image#catalog) |
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

未指定方案时，会先请你选择，确认后再制作。

![EasySlides 三种制作路线：直接生成可编辑 PPT、AI 生图后整页重建、AI 生图后局部重建](assets/easyslides-workflow.svg)

| 方案 | 适合你的情况 | Token 消耗 | 耗时 |
| --- | --- | --- | --- |
| **直接生成可编辑 PPT** | 需要频繁修改文字、图表和布局 | 中 | 中 |
| **AI 生图后整页重建** | 先确认整页视觉效果，再重建为可编辑内容 | 高 | 长 |
| **AI 生图后局部重建** | 保留原图，仅编辑批注指定的部分 | 低至中 | 短至中 |

### 选择重建方式

生图路线以你确认的 `imagegen` 原图为准，支持浏览器批注选区。重建前还需选择：

| 选项 | 你会得到什么 | Token 消耗 | 耗时 |
| --- | --- | --- | --- |
| **全图矢量重建** | 图形可拆分编辑，细节可能与原图有差异 | 高至很高 | 长至很长 |
| **保留复杂配图** | 文字和简单结构可编辑，复杂配图保留原图 | 中 | 中 |

**重建范围内的文字均为原生文本框**，同一行不随意拆框，并检查对齐。局部重建的未选区域、保留配图的内部元素仍不可单独编辑。已有确认图可跳过生图；矢量化困难时会先与你确认处理方式。

两表等级均为相对估计，随页数、复杂度和修改次数变化。局部路线按已有图片、少量选区估计；第二表仅计重建，生图消耗与时间另行说明。

### 交付与消耗

交付 PPTX、页面预览和编辑范围说明，并报告已知视觉差异。有可用统计时附上耗时、生图调用次数与额度变化；精确 Token 或生图额度不可获取时明确标注，不用账户百分比推算本次消耗。

### 资料与隐私

文件在本地管理；使用云端 AI 时，提交的文字和图片由对应服务处理。请确认敏感材料的使用权限，私人资料经你授权后再发布。

<details>
<summary><strong>想了解技术实现？</strong></summary>

- **直接制作**：材料 → SVG／图形描述 → DrawingML 原生对象 → PPTX；已有 PPTX 模板可直接填充。
- **生图重建**：Codex `imagegen` → 页面位图 → 文字／布局识别 → 重建 → PPTX。矢量方案使用 `scansci-svg` 重绘；保留配图方案组合原生文字、简单图形和原图。
- **局部处理**：仅在批注选区执行重建，清除对应旧像素，再与未选区域合成。

更多实现细节见 [架构说明](ARCHITECTURE.md) 和 [工作流入口](workflows/index.md)。

</details>

<details>
<summary><strong>开发与致谢</strong></summary>

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

**Turn research material into slides you can present and edit, using natural language.**

EasySlides is an AI Agent plugin for research talks, journal clubs, proposals, and thesis defenses. Provide your material, audience, and key points to get started.

Current version: **1.1.0** · [Release notes](CHANGELOG.md)

### Template and Example Gallery

**[Explore the gallery](http://easyslides.scansci.com/)**

| [Native Templates](http://easyslides.scansci.com/?library=native#catalog) | [Image References](http://easyslides.scansci.com/?library=image#catalog) |
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

EasySlides asks you to choose before starting unless you have already specified a method.

| Method | Best for | Token Usage | Time |
| --- | --- | --- | --- |
| **Direct editable PPT** | Editing text, diagrams, and layouts directly in PowerPoint | Medium | Medium |
| **AI images, then full-slide reconstruction** | Approving the generated visual design before rebuilding the whole slide | High | Long |
| **AI images, then selected-region reconstruction** | Making only annotated parts of an approved image editable | Low to medium | Short to medium |

For image-based methods, approve the actual `imagegen` output, then choose:

- **Full vector reconstruction**: editable shapes, with possible differences in detail. Token usage: high to very high; time: long to very long.
- **Preserve complex images**: editable text and simple shapes; pictures stay intact. Token usage and time: medium.

Rebuilt text uses native text boxes with logical lines kept together and alignment checked. Unselected regions and picture internals remain uneditable. Approved images skip generation; difficult vector work requires your confirmation.

All levels are relative to scope and complexity. Selected-region estimates assume existing images and a few annotations; reconstruction estimates exclude image generation.

### Results

Delivery includes PPTX, previews, editable scope, and known differences. Available usage statistics are reported; missing exact token or image-quota figures are marked unavailable, never inferred from account percentages.

### Privacy

Files stay in your workspace; cloud AI processes the material you send to it. Confirm permission before sharing sensitive research or publishing private files.

<details>
<summary><strong>Implementation and Credits</strong></summary>

Direct creation converts SVG/shape descriptions into DrawingML objects or fills an existing PPTX. Image reconstruction uses `imagegen` pages, text/layout recognition, and either `scansci-svg` redrawing or original picture regions. Partial rebuilding replaces only selected regions and their old pixels.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [INSTALL.md](INSTALL.md) for development details.

EasySlides draws on public practice from [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master), [Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill), [LearnPrompt/humanize-ppt](https://github.com/LearnPrompt/humanize-ppt), [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill), [xiao634zhang/paper-ppt-skill](https://github.com/xiao634zhang/paper-ppt-skill), and [fangyuanopus/literature-report-ppt-builder](https://github.com/fangyuanopus/literature-report-ppt-builder). Acknowledgement does not imply endorsement. See [LICENSE](LICENSE) for the code license; third-party templates and images require their own permissions.

</details>

[Back to top](#easyslides)
