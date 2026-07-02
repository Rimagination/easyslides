# EasySlides 卡片库组装说明书

本说明书给 agent 使用。目标不是让 agent 自由画卡，而是先选择合适的卡片样式，再把内容压进已经声明好的尺寸和容量里。任何卡片内容在渲染前都必须通过 `scripts/card_library.py validate`。

## 1. 先判断内容形状

优先判断内容的语义形状，而不是先看它“像不像卡片”。

| 内容形状 | 优先卡片 |
| --- | --- |
| 一个大数字、一个结果指标 | `stat_card` |
| 三个并列指标 | `kpi_row_3` |
| 三个并列发现、贡献、风险 | `three_card_summary` |
| 四个模块、问题、分类块 | `four_quadrant_grid` |
| 两侧对比、前后对比、国内外对比 | `comparison_pair` |
| 优势/限制、收益/风险 | `pros_cons_pair` |
| 方法流程、技术路线 | `process_steps_4` |
| 时间阶段、项目里程碑 | `timeline_milestones` |
| 一个主图加解释 | `figure_note_card` |
| 一个结论加多条证据 | `evidence_stack` |
| 方法由几个模块组成 | `method_module_card` |
| 文献速读、论文摘要 | `citation_reading_card` |
| 一句重点结论 | `callout_quote_card` |

如果内容不符合这些形状，先用普通 body variant，例如 `flexible_canvas` 或 `figure_with_notes`，不要强行卡片化。

## 2. 再检查数量

每个卡片在 `templates/cards/card_library.json` 的 `selection.item_count_min` 和 `selection.item_count_max` 中声明了可接受数量。

- 3 个并列点用 `three_card_summary`，不要塞进 2 卡或 4 卡。
- 4 个模块用 `four_quadrant_grid`。
- 3-5 个步骤可用 `process_steps_4` 或 `timeline_milestones`；超过 5 个应拆页或改为表格/流程图。
- 只有一个主图时才用 `figure_note_card`；多个主图优先拆页。

## 3. 填槽位前先压缩内容

卡片的每个 slot 都有固定容量：

- `max_chars_per_line_zh`
- `max_lines`
- `font_size_px`
- `min_font_size_px`
- `overflow_action`

agent 必须先把内容改写到 slot 容量以内，再渲染。不要依赖 PowerPoint 自动缩小字号，也不要让文本框溢出。

## 4. 内容超容量时的处理顺序

1. 删除套话和弱信息。
2. 把长句改成短句。
3. 保留结论，移动证据细节到备注或下一页。
4. 如果仍超出，换更适合的卡片或 body variant。
5. 如果卡片本身不再适合表达这个内容，拆页。

禁止的处理：

- 不要把字号缩到 `min_font_size_px` 以下。
- 不要把卡片宽高临时拉大。
- 不要增加未声明的 slot。
- 不要把不并列的内容塞进并列卡。

## 5. 推荐命令

查看卡片总数：

```powershell
python scripts/card_library.py count
```

按内容形状查找卡片：

```powershell
python scripts/card_library.py query --content-shape parallel_points --item-count 3
```

校验一个 payload：

```powershell
python scripts/card_library.py validate --card-id three_card_summary --payload-json "{\"items\":[{\"title\":\"机制清晰\",\"body\":\"变量之间存在稳定路径，适合用图示表达主链路。\"},{\"title\":\"证据充分\",\"body\":\"多源数据给出一致方向，局部差异作为补充说明。\"},{\"title\":\"应用可迁移\",\"body\":\"指标定义简单，后续可复用到相邻区域。\"}]}"
```

复杂 payload 推荐先写入 JSON 文件，再校验：

```powershell
python scripts/card_library.py validate --card-id three_card_summary --payload-file payload.json
```

导出卡片样册 PPT：

```powershell
python scripts/card_library.py preview --output outputs/card_library_preview.pptx
```

## 6. 组装原则

卡片库目前包含 13 种首版样式。它们是“安全零件”，不是完整页面模板。agent 选中卡片后，应把它放进当前页面的内容区，并遵守该模板已有的导航、标题、页脚、颜色和字号规则。

卡片表达的是内容结构。装配时先问：这页到底是指标、并列观点、对比、流程、证据、方法模块、文献摘要，还是一句重点结论？问清楚后再选卡。

## 7. 默认视觉皮肤

默认皮肤是 `consulting_light`，参考 PPT Master example 的咨询风卡片：

- 白色卡片主体
- 柔和阴影和极细描边
- 顶部强调色条
- 编号徽章或类别短码
- 图标圆底
- 内容分割线
- 底部容量标签

导出样册时应使用这套视觉皮肤，而不是只画边框的工程样机。视觉层可以换皮肤，但不能改变 `card_library.json` 中声明的几何尺寸和 slot 容量。

## 8. PPT Master 风格视觉配方

当需要更复杂、更像 PPT Master example 的卡片时，先读
`templates/cards/visual-recipes-manual.md`，再查
`templates/cards/visual_recipes.json`。

推荐查询：

```powershell
python scripts/card_recipe.py query --content-shape sequence --item-count 3
python scripts/card_recipe.py prompt --recipe-id pm_flow_strip
```

`card_library.json` 负责内容容量和安全边界；`visual_recipes.json` 负责视觉结构，例如标题带、左强调条、流程条、进度条、双指标卡和图片证据卡。两者冲突时，容量安全优先。
