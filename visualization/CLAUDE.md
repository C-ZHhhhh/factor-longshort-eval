# visualization/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

可视化层,负责生成静态图表、交互式图表、HTML报告。

## 边界

**输入**: 回测结果、评估指标
**输出**: PNG/HTML图表、完整HTML报告

## 约束

1. **双输出**: 静态图(matplotlib/seaborn) + 交互图(Plotly)
2. **统一样式**: 保持图表风格一致
3. **报告完整性**: HTML报告包含所有关键图表和表格

## 成员清单

**__init__.py**: 包初始化文件

**factor_visualizer.py**: 因子回测可视化核心模块。提供4种核心图表：净值曲线对比图、IC时间序列图、回撤曲线图、因子相关性热图。

**static_plots.py**: 静态图表模块(matplotlib/seaborn)。净值曲线、回撤、IC序列等。

**interactive_plots.py**: Plotly交互图模块。交互式净值图、因子相关性热图等。

**report_generator.py**: 报告生成模块。整合所有图表和表格,生成HTML报告。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
