# 从 PDF 自动提取科研原图

新建论文汇报，先使用版面识别工具提取图形区域与元数据。不要把聊天模型
目测页面、编造矩形坐标作为默认取图方法。视觉检查用于验收完整性和科学
含义；不能因有图片文件就认定提取成功。

```powershell
python <runtime>/scripts/easyslides.py figure-extract paper.pdf --out <project>/extracted/paper
# 复用已有结构化解析结果，无需再次上传或消耗解析额度：
python <runtime>/scripts/easyslides.py figure-extract paper.pdf --layout <existing>/layout.json --out <project>/figures
```

`auto` 优先使用已配置 token 的 MinerU Precision；没有 token 时使用已配置的
本地 PDFFigures2。可用 `--backend mineru|pdffigures2` 显式选择。输入是公开文献
且在获授权的资料范围内时，按现有流程处理；未发表、保密或个人文件上传前
确认资料处理范围。不要泄露 token；不要擅自配置模型或修改全局依赖。

- **MinerU Precision**：保留 Markdown、layout JSON、图像和原始结果。提取器
  读取 `pdf_info/page_size/page_idx` 与机器识别的图／表区域坐标，再从原始
  PDF 导出 300 dpi PNG 和对应区域 PDF。记录来源哈希、页码、原始坐标、
  导出坐标、解析器输出和 DPI。已有版面坐标直接复用，避免重复付费解析。
- **PDFFigures2**：使用已有本地配置提取科研图表，保留原始 JSON、图像和
  caption。它是独立的本地图表提取路径，不要求为此新增云端 API。
- 缺少工具、认证或布局信息时，报告具体缺项，并使用已有出版社独立图件、
  已验证资产或用户提供的原图。纯 Markdown、OCR 文本和普通嵌入图片枚举
  不能冒充完整科研图提取；不要静默降级后继续声称已取得原图。

保留图号、子图标记、坐标轴、单位、图例、误差定义与 caption 的关联。PDF
中的科学图经常由矢量线、文本和位图共同组成，直接枚举 `get_images()` 不能
保证取得整图。优先使用完整图；需要子图时，使用工具给出的子图区域，并
记录其母图号。共享图例不在子图区域内时，须一起保留或等义原生重建。

解析器可能把一个多面板图拆成多个区域，caption 也可能绑定错误。区域序号
`region-p02-005` 或资产索引自动生成的 `Figure 5` **不代表论文真实 Fig. 5**。
核对论文图题、原始子图标签和变量后再命名。机器坐标也须检查轴和图例是否
完整；识别不清时重跑合适的解析器或保留完整图，不靠随意缩小边界消除白区。

`figures_manifest.json` 的 `needs_review` 是正常中间状态。图件通过核对后，
按“变量关系／比较 (Author et al., year)”写中文图题，再进入科学正文组合。
禁止将 AI 生成图伪装为论文原图或重绘的实测数据。
