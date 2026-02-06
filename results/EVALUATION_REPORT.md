# 因子回测系统 - 综合评估报告

**生成时间**: 2026-02-05 22:04:26

---

## 运行配置


**Git Commit**: `70d7bbf41d4ed242e0e6bd9aeb9bf8217ec3e748`

**样本期**:
- 起始日期: 2015-02-28
- 结束日期: 2026-02-28
- 总月数: 133

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

1. **最佳策略**: Momentum - 年化收益 0.19%, Sharpe 0.1153, 最大回撤 -20.68%

2. **成本影响**: 平均成本拖累 -0.51%/年, 平均换手率 22.64%

3. **市场暴露**: Momentum Beta=0.1862, R²=10.09% (需优化)

4. **因子有效性**: Momentum IC均值=0.0031, IR=0.0157, IC正占比=49.59%

5. **稳健性**: 子样本 Sharpe 标准差 0.0987 (稳定)

6. **合成因子**: Composite 排名 4/5, Sharpe -0.6185


---

## Research Question Answer

### RQ1: 扣成本后是否产生稳定的多空收益？

扣除交易成本后，**仅 Momentum 因子实现小幅正收益** (年化 0.19%, Sharpe=0.1153)，但统计检验显示其不具显著性 (t-stat=0.37, p=0.715 > 0.05)。

**年化收益口径**: 全样本与子样本均采用 **CAGR (Compound Annual Growth Rate)** 计算，公式为 `(1 + total_return)^(1/n_years) - 1`，确保样本间可比性。显著性检验针对'月度净收益序列'的均值，与 CAGR 不同但相互印证。其余因子（Reversal, LowVolatility, Trend, Composite）在扣成本后均为负收益：
- **Trend**: 年化 -1.34%, Sharpe=-0.0846
- **Reversal**: 年化 -1.02%, Sharpe=-0.1949
- **Composite**: 年化 -4.64%, Sharpe=-0.6185
- **LowVolatility**: 年化 -8.87%, Sharpe=-0.7447

**统计检验** (见 [significance_summary.md](significance_summary.md)): Newey-West 检验显示，2 个因子（LowVolatility, Composite）通过 5% 显著性水平，但**均为负收益**，不支持稳定正收益假设。

**结论**: 当前因子在样本期内**未能稳定产生超额收益**，Momentum 的小幅正收益缺乏统计显著性支撑。

### RQ2: 因子表现的稳健性如何？

**子样本稳健性** (见 [robustness_table.md](robustness_table.md)):

**说明**: 以下为 Momentum 因子在不同子样本的 **净收益表现 (扣除 20bps 成本)**

| 时间段 | 年化收益 (净) | Sharpe (净) |
|--------|--------------|-------------|
| period_1_2016-01_2020-01 | 1.07% | 0.2858 |
| period_2_2020-01_2026-02 | 1.15% | 0.1463 |

子样本 Sharpe 波动范围为 0.1395，表现在不同时期**差异较大**，稳健性有限。

**成本敏感性**:

- 当交易成本升至 **30 bps** 时，Momentum 年化收益降至 **-0.01%** (转为负值)
- 因子收益对交易成本高度敏感，实际交易中需严格控制成本

**结论**: 因子表现**缺乏时间稳健性**，在不同子样本和成本假设下差异明显，实盘可靠性存疑。

### 重要说明 (Caveat)

当前策略为 **Dollar-Neutral (资金中性)** 但 **非 Beta-Neutral (市场中性)**。Momentum 因子的市场 Beta 为 **0.1862** (超过 0.1 阈值)，R²=10.09%，说明其收益中**包含约 10.1% 的市场暴露成分**，而非纯粹的选股 Alpha。

**OLS 回归结果**: Alpha=-0.0018 (见 [exposure_summary.md](exposure_summary.md))。这表明扣除市场暴露后，Momentum 的纯因子收益 (Alpha) **接近零甚至为负**，进一步削弱了其有效性证据。

**最终结论**: 基于以上分析，本研究仅提供 **弱证据 (weak evidence)**，支持因子在当前配置下产生稳定超额收益。**需进一步实施 Beta-Neutral 中性化** 并在更长样本期、多市场环境下验证，方可得出可靠结论。


---

## 6.1 主结果 (引用 performance table)

详见 [performance_table.md](performance_table.md) 和 [drawdown_stats.csv](drawdown_stats.csv)

### 性能排名 (按 Sharpe 排序)

| 排名 | 因子 | 年化收益(净) | Sharpe | 最大回撤 | 成本拖累 |
|------|------|-------------|--------|----------|---------|
| 1 | Momentum | 0.19% | 0.1153 | -20.68% | -0.41% |
| 2 | Trend | -1.34% | -0.0846 | -27.71% | -0.46% |
| 3 | Reversal | -1.02% | -0.1949 | -19.06% | -0.83% |
| 4 | Composite | -4.64% | -0.6185 | -39.84% | -0.56% |
| 5 | LowVolatility | -8.87% | -0.7447 | -68.28% | -0.31% |

### 关键观察

- **性能差异**: 最佳策略 (Momentum, Sharpe=0.1153) vs 最差策略 (LowVolatility, Sharpe=-0.7447), 差距 0.8599
- **成本影响最大**: Reversal 成本拖累 -0.83%/年
- **最大回撤**: LowVolatility -68.28%

---

## 6.2 多因子对比 (含 Composite)


### Composite 因子表现

- **排名**: 4/5
- **年化收益(净)**: -4.64%
- **Sharpe**: -0.6185
- **最大回撤**: -39.84%
- **换手率**: 25.04%

### 单因子 vs Composite

| 因子 | Sharpe | Composite Sharpe | 改进 |
|------|--------|-----------------|------|
| Momentum | 0.1153 | -0.6185 | -0.7338 |
| Trend | -0.0846 | -0.6185 | -0.5339 |
| Reversal | -0.1949 | -0.6185 | -0.4236 |
| LowVolatility | -0.7447 | -0.6185 | +0.1262 |

**结论**: Composite 因子未能超越最佳单因子，建议优化合成方法或仅使用表现最好的因子。


---

## 6.3 稳健性 (子样本 + 成本敏感性)

详见 [robustness_table.md](robustness_table.md)

### 稳健性评估

#### 子样本稳健性

| 时间段 | 年化收益 | Sharpe | 最大回撤 |
|--------|---------|--------|----------|
| period_1_2016-01_2020-01 | 1.07% | 0.2858 | -17.76% |
| period_2_2020-01_2026-02 | 1.15% | 0.1463 | -19.70% |

**Sharpe 差异**: 0.1395 (稳定)

#### 成本敏感性

| 成本 | 年化收益 | Sharpe | 变化 |
|------|---------|--------|------|
| 10 bps | 0.40% | 0.1378 | 基准 |
| 20 bps | 0.19% | 0.1153 | -0.0225 |
| 30 bps | -0.01% | 0.0927 | -0.0451 |
| 40 bps | -0.22% | 0.0701 | -0.0677 |
| 50 bps | -0.42% | 0.0475 | -0.0904 |

**成本敏感性**: 每增加10bps，年化收益下降约 0.20%


---

## 6.4 暴露与结论 (beta/corr)

详见 [exposure_summary.md](exposure_summary.md)

### 市场暴露分析

| 策略 | Beta | R² | 相关系数 | 评价 |
|------|------|-----|---------|------|
| Momentum | 0.1862 | 10.09% | 0.3177 | ⚠️  超标 |
| Reversal | 0.0262 | 0.70% | 0.0839 | ✅ 良好 |
| LowVolatility | -0.4552 | 36.75% | -0.6062 | ⚠️  超标 |
| Trend | -0.2126 | 17.45% | -0.4178 | ⚠️  超标 |
| Composite | -0.2396 | 30.74% | -0.5544 | ⚠️  超标 |

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

**报告生成时间**: 2026-02-05 22:04:26

*本报告由统一评估器自动生成，所有数字均来自代码运行输出。*
