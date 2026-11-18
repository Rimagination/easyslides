# EasySlides — Qoder marketplace submission

## Listing copy

**Name:** EasySlides

**Summary:** 把论文和研究材料组织成可编辑学术 PPT，支持模板复用、图片重建与 PPTX 模板蒸馏。

**Description:**

EasySlides 面向论文汇报、研究综述与答辩。先根据材料、听众和时长明确汇报要求，
再确认原生可编辑或图片生成后重建的制作路线，以及主题色和主题图来源。

- 原生制作：八套学术模板，默认使用 `academic_general`；十四学科门类主题图可适配封面、目录、页眉与结尾。
- 证据与版式：结合论文原图和有来源的科学图表编排内容，保留引用，按统一文字层级、对齐和页码规则检查并渲染预览。
- 图片重建：把用户确认的整页图片或指定区域转成可编辑内容；先明确重建方式与可编辑范围。
- 模板蒸馏：从已有 PPTX 提取布局、组件和符号，整理成可审阅的复用资产。

Python 3.10+ 和运行依赖用于实际制作；预览需要 PowerPoint 或 LibreOffice。
新图片生成依赖宿主可用工具或用户配置的服务。首次使用时由 Agent 检查环境，
输出保存在用户工作区。

**Example prompts:**

- 用 EasySlides 把这篇论文做成 20 分钟组会汇报，先确认制作路线、主题色和主题图。
- 用 EasySlides 修改这个 PPT 的版式与配色，保留原始图表和结论。
- 用 EasySlides 蒸馏这个 PPTX，提取可复用模板和组件。

**Source:** https://github.com/Rimagination/easyslides

**License:** MIT

**Logo:** `assets/logo.png`

**Package:** `build/easyslides-qoder-<version>.zip`

## Submission

Check the account and publication list in the user's Qoder region. The
international portal is `qoder.com`; use
[the China portal](https://qoder.cn/account/apphub-publications) only for
a China-site account. A publication list on one portal does not establish
submission or review status on the other.

Sign in at [My publications](https://qoder.com/account/apphub-publications), choose
Plugin, upload the package and logo, and adapt the copy above to the live form's
fields and limits. Select the closest available productivity or document category.
The account owner supplies publisher identity when requested by the platform.

Run Qoder's bundled `create-plugin` offline validator against both the plugin
directory and the final ZIP before submission. Record runtime validation
separately from marketplace review; a passing package check is not approval.

Reference: [Qoder publication guide](https://docs.qoder.com/zh/qoderwork/skill-marketplace-guidelines).
