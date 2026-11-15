# 因子回测系统 - 综合评估报告

**生成时间**: 2026-11-15 02:53:59

---

## 运行配置


**Git Commit**: `22cecad06b7b6205532d11a0a47e259ed1110db1`

**样本期**:
- 起始日期: 2015-02-28
- 结束日期: 2026-01-31
- 总月数: 132

**回测配置**:
- 调仓频率: 2monthly
- 交易成本: 20.0 bps
- 最小持有期: 12 月
- 进入阈值: 0.25
- 退出阈值: 0.3
- 子样本分割: 2020-01-01

**中性化配置**:
- Dollar-Neutral: True
- Beta-Neutral: False
- 说明: Dollar-neutral (sum(w)=0, long=+1, short=-1), no beta hedging


---

## Executive Summary

1. **最佳策略**: Trend - 年化收益 -1.10%, Sharpe -0.1055, 最大回撤 -26.14%

2. **成本影响**: 平均成本拖累 -0.37%/年, 平均换手率 15.98%

3. **市场暴露**: Trend Beta=-0.1893, R²=13.66% (需优化)

4. **因子有效性**: Trend IC均值=-0.0004, IR=-0.0018, IC正占比=49.60%

5. **稳健性**: 子样本 Sharpe 标准差 0.0916 (稳定)

6. **合成因子**: Composite 排名 4/5, Sharpe -0.5936


---

## Research Question Answer

### RQ1: 扣成本后是否产生稳定的多空收益？

扣除交易成本后，**仅 Momentum 因子实现小幅正收益** (年化 -2.97%, Sharpe=-0.2883)，但统计检验显示其不具显著性 (t-stat=-0.91, p=0.364 > 0.05)。

**年化收益口径**: 全样本与子样本均采用 **CAGR (Compound Annual Growth Rate)** 计算，公式为 `(1 + total_return)^(1/n_years) - 1`，确保样本间可比性。显著性检验针对'月度净收益序列'的均值，与 CAGR 不同但相互印证。其余因子（Reversal, LowVolatility, Trend, Composite）在扣成本后均为负收益：
- **Trend**: 年化 -1.10%, Sharpe=-0.1055
- **Reversal**: 年化 -0.65%, Sharpe=-0.1348
- **Composite**: 年化 -5.35%, Sharpe=-0.5936
- **LowVolatility**: 年化 -9.91%, Sharpe=-0.7572

**统计检验** (见 [significance_summary.md](significance_summary.md)): Newey-West 检验显示，2 个因子（LowVolatility, Composite）通过 5% 显著性水平，但**均为负收益**，不支持稳定正收益假设。

**结论**: 当前因子在样本期内**未能稳定产生超额收益**，Momentum 的小幅正收益缺乏统计显著性支撑。

### RQ2: 因子表现的稳健性如何？

**子样本稳健性** (见 [robustness_table.md](robustness_table.md)):

**说明**: 以下为 Momentum 因子在不同子样本的 **净收益表现 (扣除 20bps 成本)**

| 时间段 | 年化收益 (净) | Sharpe (净) |
|--------|--------------|-------------|
| period_1_2016-01_2020-01 | -4.33% | -0.4594 |
| period_2_2020-01_2026-02 | -3.44% | -0.3299 |

子样本 Sharpe 波动范围为 0.1295，表现在不同时期**差异较大**，稳健性有限。

**成本敏感性**:

- 当交易成本升至 **30 bps** 时，Momentum 年化收益降至 **-3.16%** (转为负值)
- 因子收益对交易成本高度敏感，实际交易中需严格控制成本

**结论**: 因子表现**缺乏时间稳健性**，在不同子样本和成本假设下差异明显，实盘可靠性存疑。

### 重要说明 (Caveat)

当前策略为 **Dollar-Neutral (资金中性)** 但 **非 Beta-Neutral (市场中性)**。Momentum 因子的市场 Beta 为 **-0.1708** (超过 0.1 阈值)，R²=8.01%，说明其收益中**包含约 8.0% 的市场暴露成分**，而非纯粹的选股 Alpha。

**OLS 回归结果**: Alpha=0.0001 (见 [exposure_summary.md](exposure_summary.md))。这表明扣除市场暴露后，Momentum 的纯因子收益 (Alpha) **接近零甚至为负**，进一步削弱了其有效性证据。

**最终结论**: 基于以上分析，本研究仅提供 **弱证据 (weak evidence)**，支持因子在当前配置下产生稳定超额收益。**需进一步实施 Beta-Neutral 中性化** 并在更长样本期、多市场环境下验证，方可得出可靠结论。


---

## 6.1 主结果 (引用 performance table)

详见 [performance_table.md](performance_table.md) 和 [drawdown_stats.csv](drawdown_stats.csv)

### 性能排名 (按 Sharpe 排序)

| 排名 | 因子 | 年化收益(净) | Sharpe | 最大回撤 | 成本拖累 |
|------|------|-------------|--------|----------|---------|
| 1 | Trend | -1.10% | -0.1055 | -26.14% | -0.40% |
| 2 | Reversal | -0.65% | -0.1348 | -14.94% | -0.42% |
| 3 | Momentum | -2.97% | -0.2883 | -34.94% | -0.38% |
| 4 | Composite | -5.35% | -0.5936 | -42.63% | -0.37% |
| 5 | LowVolatility | -9.91% | -0.7572 | -69.99% | -0.29% |

### 关键观察

- **性能差异**: 最佳策略 (Trend, Sharpe=-0.1055) vs 最差策略 (LowVolatility, Sharpe=-0.7572), 差距 0.6517
- **成本影响最大**: Reversal 成本拖累 -0.42%/年
- **最大回撤**: LowVolatility -69.99%

---

## 6.2 多因子对比 (含 Composite)


### Composite 因子表现

- **排名**: 4/5
- **年化收益(净)**: -5.35%
- **Sharpe**: -0.5936
- **最大回撤**: -42.63%
- **换手率**: 16.31%

### 单因子 vs Composite

| 因子 | Sharpe | Composite Sharpe | 改进 |
|------|--------|-----------------|------|
| Trend | -0.1055 | -0.5936 | -0.4880 |
| Reversal | -0.1348 | -0.5936 | -0.4588 |
| Momentum | -0.2883 | -0.5936 | -0.3053 |
| LowVolatility | -0.7572 | -0.5936 | +0.1637 |

**结论**: Composite 因子未能超越最佳单因子，建议优化合成方法或仅使用表现最好的因子。


---

## 6.3 稳健性 (子样本 + 成本敏感性)

详见 [robustness_table.md](robustness_table.md)

### 稳健性评估

#### 子样本稳健性

| 时间段 | 年化收益 | Sharpe | 最大回撤 |
|--------|---------|--------|----------|
| period_1_2016-01_2020-01 | -4.33% | -0.4594 | -19.69% |
| period_2_2020-01_2026-02 | -3.44% | -0.3299 | -32.98% |

**Sharpe 差异**: 0.1295 (稳定)

#### 成本敏感性

| 成本 | 年化收益 | Sharpe | 变化 |
|------|---------|--------|------|
| 10 bps | -2.78% | -0.2672 | 基准 |
| 20 bps | -2.97% | -0.2883 | -0.0211 |
| 30 bps | -3.16% | -0.3093 | -0.0421 |
| 40 bps | -3.34% | -0.3303 | -0.0631 |
| 50 bps | -3.53% | -0.3512 | -0.0840 |

**成本敏感性**: 每增加10bps，年化收益下降约 0.19%


---

## 6.4 暴露与结论 (beta/corr)

详见 [exposure_summary.md](exposure_summary.md)

### 市场暴露分析

| 策略 | Beta | R² | 相关系数 | 评价 |
|------|------|-----|---------|------|
| Momentum | -0.1708 | 8.01% | -0.2831 | ⚠️  超标 |
| Reversal | 0.0204 | 0.53% | 0.0730 | ✅ 良好 |
| LowVolatility | -0.5001 | 34.82% | -0.5901 | ⚠️  超标 |
| Trend | -0.1893 | 13.66% | -0.3696 | ⚠️  超标 |
| Composite | -0.2621 | 20.70% | -0.4550 | ⚠️  超标 |

**结论**: ⚠️  策略存在较大市场暴露，需优化中性化逻辑。


---

## 改进建议

基于以上分析，提出以下改进建议：

2. **优化市场中性化**
   - 以下策略Beta超标: Momentum, LowVolatility, Trend, Composite
   - 检查权重归一化逻辑
   - 考虑添加市场对冲头寸

3. **优化因子合成**
   - 当前等权合成未能提升表现
   - 建议使用 Sharpe 加权或 IC 加权
   - 仅合成表现较好的因子


---

## 附录：生成文件清单

- `performance_table.csv` / `.md` - 性能表格
- `drawdown_stats.csv` - Drawdown 统计
- `exposure_summary.md` - 市场暴露分析 (含 Alpha)
- `exposure_stats.csv` - 暴露统计数据
- `robustness_table.csv` / `.md` - 稳健性测试表格
- `significance_summary.md` - 显著性检验报告 (t-stat, Newey-West)
- `ic_summary.csv` - IC 汇总 (forward IC, lag=1)
- `ic_sanity_checks.md` - IC 时间对齐验证
- `weight_neutrality_stats.csv` - 权重中性化验证
- `metadata.json` - 运行配置元数据
- `nav_comparison.png` - 净值曲线对比图
- `ic_timeseries.png` - IC 时间序列图
- `drawdown_analysis.png` - 回撤曲线图
- `factor_correlation_heatmap.png` - 因子相关性热图
- `equity_gross_vs_net.png` - 毛收益 vs 净收益对比图

---

**报告生成时间**: 2026-11-15 02:53:59

*本报告由统一评估器自动生成，所有数字均来自代码运行输出。*
