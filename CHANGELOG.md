# Changelog

## Unreleased

- 修复 `literature_minimal` 目录页、章节页的可选 Logo：未提供时移除整个框组，提供时绑定框内图片；补充原生 PPTX 导出与编辑保存测试（[#1](https://github.com/Rimagination/easyslides/issues/1)）。
- 修复组内文字槽位与作者、日期等行内槽位的填充，保留外框、字体和固定标签。
- Both renderers now bind grouped image slots without replacing their frames. Raw templates still require placeholder filling before export; `*_svg.pptx` is the image-reference copy, while the primary `.pptx` contains editable shapes.

## 1.1.0 - 2026-09-10

### 面向用户

- 制作前选择：直接生成可编辑 PPT、AI 生图后整页重建、AI 生图后局部重建。选项同时说明相对 Token 消耗和耗时。
- 重建前选择：全图矢量重建或保留复杂配图。重建范围内的文字使用原生文本框，同一逻辑行保持完整。
- 展厅区分 7 种原生模板与 13 种图片参考样式；按需加载选中的整套缩略图。
- 以用户确认的 imagegen 原图为预览及批注依据，局部重建保留未选区域。

### 修正

- 补全打包所需的模板策略、索引和图片参考库；排除本地材料、缓存和案例输出。
- 加强制作方案确认、文字覆盖、原生可编辑性和局部范围验收；旧 OCR 碎片需按原图核对为完整文字行。
- 修复配色传递、图片资产绑定、文献模板能力声明及环境诊断中的误报。

### 升级与限制

- 旧图片重建项目中，含 Layer C 文字的页面需补充 `source_text_lines` 后再运行生产 QA，详见 [重建工作流](workflows/slide-image-to-editable-pptx.md)。
- 新的页面生图依赖宿主提供可调用的 Codex `imagegen`；仅安装技能不能证明工具可用。已有确认图片可以直接进入重建。
- 已在 Windows PowerPoint 验证代表性页面的渲染与编辑保存。跨平台渲染、字体替换及 Codex 内置批注新提交仍需对应环境验证；不承诺逐像素一致。
- Token、生图额度等精确统计不可获取时会明确说明，不用账户总百分比推算单次消耗。

### English Summary

Three user-selected production methods, two explicit reconstruction modes, seven native templates, thirteen image-reference styles, source-line text validation, and portable plugin packaging. Existing reconstruction projects must add source-reviewed `source_text_lines` before production QA. AI generation remains host-dependent; visual fidelity and font portability have documented limits.
