# visualization/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

可视化层,负责把回测和评估的结果画出来:静态图片(PNG)和一份单文件的网页报告。

## 边界

**输入**: 回测结果、评估指标(都由上游算好,这里不重新计算任何结果)
**输出**: `results/` 下的 PNG 图片、`results/report.html`、`results/report_data.json`

## 约束

1. **不写死结果**: 图和网页上的每个数字、每句结论都来自传入的数据;网页模板里不允许出现任何结果数字或结论句
2. **结论说法一致**: 网页报告的定性判断(是否正收益、是否显著、Beta 是否超标)复用 `evaluation/report_narrative.py`,不另设阈值
3. **颜色跟着策略走**: 每个策略的颜色槽位固定(`html_report.SERIES_SLOTS`),不随排名、筛选或显示与否变化
4. **网页单文件、可离线**: `report.html` 不引用任何外部脚本、样式、字体或图片
5. **每张图都有数据表**: 网页里每张图下面都能展开对应的数据表,数值不只藏在悬停提示里

## 成员清单

**__init__.py**: 包初始化文件

**factor_visualizer.py**: 静态图(matplotlib)。净值曲线对比、IC 时间序列、回撤曲线、因子相关性热图、毛收益 vs 净收益。

**html_report.py**: 网页报告的数据和结论。`build_report_data()` 把回测/评估结果组装成一个可存为 JSON 的 dict(含文字结论);`render_html()` 把它填进模板;`write_report()` 写出 `report_data.json` 和 `report.html`。由 `scripts/run_evaluation.py` 调用。

**report_template.html**: 网页报告的模板。只负责排版和用内联 JS 画图(折线图、条形图、悬停提示、数据表),数据全部来自 `html_report.py` 填入的 JSON。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
