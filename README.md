# 因子/组合回测

## 0. 研究目标与研究设计

**核心研究问题**

> 在美国股票市场中，价格/风险相关的横截面因子（如动量、短反转、低波、趋势）是否能在**扣除交易成本后**产生稳定的多空收益？这些收益在不同市场环境/子样本中是否稳健？

**关键设计选择**

* 样本池：S&P 500
* 频率：月度调仓
* 组合形式：market-neutral long-short（净暴露≈0）
* 评价：Sharpe、MaxDD、换手、成本敏感性、IC/IR、子样本稳定性

---

# 1) 数据层（Data Layer）

## 1.1 Universe（样本池）

* 固定一份 tickers 列表（例如 150–300 只）

## 1.2 需要的数据字段

* `Adj Close`（复权收盘价）
* `Volume`（做流动性 proxy）
* 交易日历（日期索引）

## 1.3 数据清洗

* 处理缺失值：某股票缺失超过 X% 的月份则当期剔除
* 对齐：所有股票收益在同一时间点对齐（避免未来数据混进来）
* 复权：必须用复权价算收益（用 Adj Close）

---

# 2) 因子层（Factor Layer）

## 2.1 因子选择

1. **动量（12-1 momentum）**

* ( $MOM_{t} = R_{t-12m, t-1m}$ )

2. **短期反转（1M reversal）**

* ( $REV_{t} = -R_{t-1m, t}$ )

3. **低波（low volatility）**

* ( $LOWVOL_{t} = -\sigma(\text{daily returns over last 3m}$) )

4. **趋势（time-series trend, 200D MA gap）**

* ( $TREND_t = \frac{P_t}{MA_{200}(P)_t} - 1$ )

5. **流动性/成交量冲击（volume/turnover proxy）**

* 用成交额或换手 proxy 做“流动性风险”的控制

## 2.2 因子预处理

对每个月的横截面因子值做：

### (1) Winsorize 去极值（防止少数点把回测扭曲）

* 把因子截断在 1%–99% 或 5%–95%

### (2) 标准化（z-score），才能多因子合成

* ( $z_i = \frac{x_i - \mu}{\sigma}$ )

### (3) 缺失处理

* 因子缺失：当期该股票不参与排序/建仓

---

# 3) 中性化（Neutralization）

## 3.1 第一档：Market-neutral

每月：

* 做多 top 20%
* 做空 bottom 20%
* 多空权重等额（总多=1，总空=-1）

这样净暴露≈0。

## 3.2 第二档：Beta-neutral

用过去 252 天日收益回归市场（比如 SPY）得到每只股票 beta：

* 对每月持仓，调整权重使得
  ( $\sum w_i \beta_i \approx 0$ )

## 3.3 第三档：行业中性

在每个行业内部做 top/bottom，再合并。
（需要 ticker → sector 的映射表）

---

# 4) 组合构建（Portfolio Construction）

## 4.1 排序型

* Top/Bottom 分位数
* 权重等权或按排名线性

## 4.2 风险调整权重

用过去 63 天波动率做风险平价（简化版）：

* ( $w_i \propto \frac{1}{\sigma_i}$ )
  并在多头和空头各自归一化

## 4.3 多因子合成

把多个因子 z-score 后平均：

* ( $score = \frac{1}{K}\sum_k z_{k}$ )

再按 score 排序构建组合。

---

# 5) 交易与回测（Backtest Engine）

## 5.1 时间对齐（最重要：防 look-ahead）

* 月末 t 计算因子
* 用 **t+1 的开盘或下一个交易日收盘** 建仓
  实现上至少做到：**信号 shift(1)**

## 5.2 收益计算

* 计算组合在下个月的收益
* 多空收益：
  ( $r_{LS} = r_{long} - r_{short}$ )

## 5.3 换手率（Turnover）

用定义（每期）：

* ( $TO_t = \frac{1}{2}\sum_i |w_{i,t} - w_{i,t-1}|$ )

## 5.4 交易成本模型（你要做“敏感性分析”）

* 成本 = `TO_t * cost_bps`
* 做 3 档：10/20/30 bps
  输出不同成本下的 Sharpe 和年化收益。

---

# 6) 评估指标（Evaluation）

## 6.1 交易绩效

* 年化收益、年化波动
* Sharpe（无风险利率设 0 ）
* Max Drawdown
* 月胜率、偏度/峰度

## 6.2 因子有效性：IC/IR

每期算：

* IC = Spearman corr(因子值, 下一期收益)
* IR = mean(IC) / std(IC)

输出：

* IC 时间序列
* 平均 IC、IC t-stat

## 6.3 暴露检查（Exposure）

至少做：

* 市场 beta（是否接近 0）
  
  展示对比：
  
* neutral 前 beta

* neutral 后 beta

---

# 7) 稳健性（Robustness）

1. **子样本**：2015–2019 vs 2020–2025
2. **分位数参数**：Top/Bottom 10% vs 20% vs 30%
3. **成本敏感性**：10/20/30 bps
4. **再平衡频率**：月度 vs 双月/季度

---

# 8) 交付与展示（Deliverables）

`results/` 里有：

**图**

* 多空净值曲线（含成本 vs 不含成本对比）
* 回撤曲线（Drawdown）
* IC 序列图（或 IC 分布直方图）

**表**

* Performance summary：年化收益/波动/Sharpe/MaxDD/换手
* Robustness table：不同成本/子样本/分位数下的对比

# 9) Key Results（关键结果）

## 9.1 Momentum因子表现总览

基于S&P 500样本（2016-2026, 121个月），月度调仓，20bps交易成本：

| 指标 | 数值 | 说明 |
|------|------|------|
| **年化收益(净)** | **0.19%** | 扣除20bps成本后 |
| **Sharpe Ratio** | **0.1153** | 风险调整后收益 |
| **最大回撤** | **-20.68%** | 约在2019-2020期间 |
| **年化波动** | **9.50%** | 月度波动年化 |
| **平均换手率** | **17.91%** | 月度调仓换手 |
| **成本拖累** | **-0.41%/年** | 交易成本影响 |

**统计显著性**: Newey-West t-stat = 0.36, p = 0.719（**不显著**）

**结论**: Momentum因子实现小幅正收益，但缺乏统计显著性，不构成稳定超额收益的强证据。

---

## 9.2 核心可视化结果

### 毛收益 vs 净收益对比

![Momentum Equity Curve](results/figures/fig_01_equity_gross_vs_net_momentum.png)

**关键发现**: 交易成本消耗约67.8%的毛收益，严重拖累最终表现。

---

### 成本敏感性分析

![Cost Sensitivity](results/figures/fig_03_cost_sensitivity_momentum.png)

**关键发现**:
- 基准点（20bps）：年化收益0.19%
- 临界点（30bps）：年化收益转负（-0.01%）
- **结论**: 策略对交易成本高度敏感，实盘需严控成本

---

### 市场暴露：Alpha & Beta

![Exposure Analysis](results/figures/fig_05_exposure_alpha_beta.png)

**关键发现**:
- **Momentum Beta = 0.1862**（超过0.1阈值），收益中约10%为市场暴露
- **Momentum Alpha = -0.0018**（接近零），扣除市场影响后纯因子收益不显著
- **改进方向**: 需实施Beta-Neutral中性化

---

## 9.3 完整报告

详细分析请参阅：
- [Results Snapshot](docs/03_results_snapshot.md) - 快照报告（1表+3图）
- [Evaluation Report](results/EVALUATION_REPORT.md) - 综合评估报告
- [CAGR Diagnostics](results/cagr_diagnostics.md) - 年化收益计算验证
- [All Figures](results/figures/) - 完整图表集

---
