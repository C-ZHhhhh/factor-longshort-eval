# 可视化模块实现总结

**完成时间**: 2026-02-04 10:55

---

## 📊 实现内容

### 新增模块

1. **visualization/factor_visualizer.py** (511行)
   - `FactorVisualizer`类：因子回测可视化核心模块
   - 提供4种核心图表生成功能

2. **scripts/generate_visualizations.py** (121行)
   - 可视化图表生成脚本
   - 整合数据加载、报告生成、图表绘制全流程

---

## 🎨 生成的4种核心图表

### 1. 净值曲线对比图 (nav_comparison.png)

**文件**: results/figures/nav_comparison.png
**尺寸**: 435 KB

**内容**:
- 子图1: 多因子净值曲线对比
  - 显示所有因子的净值走势
  - 统一配色方案
  - 图例显示因子名称

- 子图2: 月度收益率柱状图
  - 展示代表因子(Momentum)的月度收益分布
  - 正收益绿色，负收益红色

**用途**: 直观对比各因子的长期表现和稳定性

---

### 2. IC时间序列图 (ic_timeseries.png)

**文件**: results/figures/ic_timeseries.png
**尺寸**: 1.2 MB

**内容**:
- 为每个因子生成独立子图
- 每个子图包含:
  - IC原始时间序列（细线）
  - IC 12月移动平均（粗线）
  - 零线参考
  - IC均值线（红色虚线）
  - 正负区域填充（绿色/红色）

- 标题显示关键指标:
  - IR (信息比率)
  - IC均值
  - IC正占比

**用途**: 分析因子预测能力的稳定性和时变特征

---

### 3. 回撤曲线图 (drawdown_analysis.png)

**文件**: results/figures/drawdown_analysis.png
**尺寸**: 588 KB

**内容**:
- 子图1: 回撤曲线对比
  - 显示所有因子的回撤演变
  - 标注最大回撤数值
  - 填充回撤区域

- 子图2: 水下时间分析
  - 展示最佳因子(Momentum)的回撤期次
  - 不同颜色标识回撤深度:
    - 黄色: 轻度回撤 (-10%以内)
    - 橙色: 中度回撤 (-10%~-20%)
    - 红色: 深度回撤 (-20%以上)

**用途**: 评估策略的风险特征和恢复能力

---

### 4. 因子相关性热图 (factor_correlation_heatmap.png)

**文件**: results/figures/factor_correlation_heatmap.png
**尺寸**: 181 KB

**内容**:
- Spearman秩相关系数矩阵
- 色彩编码:
  - 红色: 负相关
  - 白色: 零相关
  - 蓝色: 正相关
- 数值标注（保留3位小数）
- 对角线为1（自相关）

**用途**: 识别因子冗余性，指导多因子组合构建

---

## 🔧 技术实现

### FactorVisualizer类核心方法

```python
class FactorVisualizer:
    def __init__(self, output_dir: str = 'results/figures')

    def plot_nav_comparison(
        backtest_results: Dict,
        figsize=(14, 8),
        save=True
    ) -> plt.Figure

    def plot_ic_timeseries(
        ic_results: Dict,
        figsize=(14, 10),
        save=True
    ) -> plt.Figure

    def plot_drawdown(
        backtest_results: Dict,
        figsize=(14, 8),
        save=True
    ) -> plt.Figure

    def plot_factor_correlation(
        factor_values: Dict,
        method='spearman',
        figsize=(10, 8),
        save=True
    ) -> plt.Figure

    def generate_all_plots(
        backtest_results: Dict,
        ic_results: Dict,
        factor_values: Dict
    ) -> Dict[str, plt.Figure]
```

### 数据流

```
load_clean_data()
    ↓
EnhancedReportGenerator.generate_enhanced_report()
    ↓
MultiFactorComparator.run_single_factor() → backtest_results
    ↓
IC分析 → ic_results
    ↓
因子计算 → factor_values
    ↓
FactorVisualizer.generate_all_plots()
    ↓
保存4张图表到 results/figures/
```

---

## 🎯 关键特性

### 1. 统一配色方案

```python
self.colors = {
    'Momentum': '#1f77b4',      # 蓝色
    'Reversal': '#ff7f0e',      # 橙色
    'LowVolatility': '#2ca02c', # 绿色
    'Trend': '#d62728',         # 红色
    'Liquidity': '#9467bd',     # 紫色
    'Composite': '#8c564b',     # 棕色
    'Benchmark': '#7f7f7f'      # 灰色
}
```

### 2. 中文字体支持

```python
plt.rcParams['font.sans-serif'] = [
    'Arial Unicode MS',  # macOS
    'SimHei',            # Windows
    'DejaVu Sans'        # Linux
]
plt.rcParams['axes.unicode_minus'] = False
```

### 3. 高分辨率输出

- DPI: 300
- 格式: PNG
- bbox_inches='tight' (自动裁剪边距)

### 4. 自动化工作流

```bash
# 一键生成所有图表
python scripts/generate_visualizations.py
```

---

## ✅ 验证结果

### 生成成功确认

```
✅ 净值曲线对比图已保存: results/figures/nav_comparison.png
✅ IC时间序列图已保存: results/figures/ic_timeseries.png
✅ 回撤曲线图已保存: results/figures/drawdown_analysis.png
✅ 因子相关性热图已保存: results/figures/factor_correlation_heatmap.png
```

### 文件大小

```
-rw-r--r--  588K  drawdown_analysis.png
-rw-r--r--  181K  factor_correlation_heatmap.png
-rw-r--r--  1.2M  ic_timeseries.png
-rw-r--r--  435K  nav_comparison.png

总计: ~2.4 MB (4张高分辨率图表)
```

---

## 🔍 关键发现（从图表中）

> 本节数字于 2026-11-15 按修复后的代码重跑更新 (`python scripts/generate_visualizations.py`)。
> 旧版写的"Trend 因子 IC 正占比 99.21%"是 IC 计算用到了当月收益造成的, 不是真实的预测能力。

### 净值曲线对比
- 5 个单因子的多空组合全部是负收益, 没有哪条净值曲线是向上的
- **LowVolatility因子**跌得最深
- 合成因子(Composite)没有超过单因子

### IC时间序列
- 各因子的 IC 正占比: Trend 49.6%、Reversal 48.1%、Momentum 47.5%、LowVolatility 44.6%、Liquidity 37.7%
- IC 均值都在 0 附近 (-0.03 ~ +0.01), 前四个因子的 t 统计量绝对值都小于 2, 统计上看不出预测能力
- 现在的 IC 是"本月因子值"和"下个月收益"的相关性

### 回撤分析
- 最大回撤: Reversal -14.94%、Trend -26.14%、Momentum -34.94%、Liquidity -39.21%、LowVolatility -69.99%
- 回撤的起点包含初始净值 (第一个月就亏也算回撤)

### 因子相关性
- 动量方向修正后相关性数值已变化, 以重新生成的 `results/figures/factor_correlation_heatmap.png` 为准
- 注意: 这张热图算的是"各因子每月横截面均值"之间的相关性, 不是同一个月里各因子对股票排序的相关性

---

## 📈 后续优化方向

### 1. 交互式图表
- 使用Plotly生成HTML交互图
- 支持缩放、悬停显示详细数据
- 可导出为独立HTML文件

### 2. 更多图表类型
- 滚动Sharpe比率
- 月度收益热图
- 因子暴露分析图
- 持仓集中度分析

### 3. 自定义化
- 支持用户自定义配色
- 可配置图表尺寸
- 可选择显示/隐藏特定因子

### 4. 集成到报告
- 将图表嵌入到ENHANCED_EVALUATION_REPORT.md
- 生成包含所有图表的完整HTML报告
- 支持PDF导出

---

## 📚 使用说明

### 快速生成图表

```bash
# 激活环境
source venv/bin/activate

# 生成所有图表
python scripts/generate_visualizations.py
```

### 自定义图表生成

```python
from visualization.factor_visualizer import FactorVisualizer

# 初始化
visualizer = FactorVisualizer(output_dir='custom/path')

# 单独生成某个图表
fig = visualizer.plot_nav_comparison(backtest_results)

# 或生成所有图表
figures = visualizer.generate_all_plots(
    backtest_results=backtest_results,
    ic_results=ic_results,
    factor_values=factor_values
)

# 关闭图表
visualizer.close_all()
```

---

## 🐛 已修复的问题

### 问题1: KeyError: 'nav_series'

**原因**: 回测引擎返回的键名是`'nav'`，不是`'nav_series'`

**修复**:
```python
# 修复前
nav = result['nav_series']  # ❌

# 修复后
nav = result['nav']  # ✅
```

**影响位置**:
- visualization/factor_visualizer.py:101
- visualization/factor_visualizer.py:283
- visualization/factor_visualizer.py:313

---

## ✨ 总结

可视化模块已完整实现，提供了4种核心图表，覆盖了因子回测分析的关键维度：

1. ✅ **收益表现** - 净值曲线对比
2. ✅ **预测能力** - IC时间序列
3. ✅ **风险特征** - 回撤分析
4. ✅ **因子关系** - 相关性热图

所有图表均为高分辨率PNG格式，支持中文显示，配色统一，可直接用于报告展示。

---

**实现者**: Claude Code
**实现时间**: 2026-02-04
**代码行数**: 632行 (factor_visualizer.py 511行 + generate_visualizations.py 121行)
**测试状态**: ✅ 通过（成功生成4张图表）
