# 阶段5完成报告: 回测引擎

**完成时间**: 2026-11-15 13:10

> 本报告由 `scripts/generate_backtest_report.py` 自动生成, 所有数字来自一次真实回测
> (`scripts/test_backtest.py`), 不是手填的。这里用的是最简单的配置 (每月调仓、前后各20%),
> 只用来验证回测引擎本身; 项目正式结果用的是另一套配置, 见 `README.md` 和 `results/`。

---

## 实现概览

### ✅ 已完成模块

1. **时间对齐器** ⭐ CRITICAL (`backtest/time_aligner.py`)
   - 防止look-ahead bias的核心模块
   - 实现shift(1)时间对齐逻辑
   - 确保因子在t期计算，用于预测t+1期收益
   - 包含验证方法检查对齐正确性

2. **交易成本模型** (`backtest/transaction.py`)
   - 默认20 bps(0.20%)成本
   - 公式: cost = turnover × cost_bps / 10000
   - 支持单期、序列和年化成本计算
   - 支持成本分解(进场/离场/调仓)

3. **绩效指标计算器** (`backtest/metrics.py`)
   - 收益指标: 总收益、年化收益、月均收益
   - 风险指标: 年化波动、最大回撤
   - 风险调整收益: Sharpe、Calmar、Sortino
   - 交易统计: 胜率、平均盈亏、盈亏比

4. **回测引擎** ⭐ CRITICAL (`backtest/engine.py`)
   - 主回测循环，整合所有模块
   - 按月迭代计算组合收益
   - 计算换手率和交易成本
   - 更新净值曲线
   - 输出完整回测结果

---

## 测试结果

### 回测配置

| 参数 | 值 |
|------|-----|
| 因子 | 动量因子 (12-1月) |
| 选股分位数 | Top/Bottom 20% |
| 调仓频率 | 每月 |
| 权重方案 | 等权 + Market-Neutral |
| 交易成本 | 20 bps |
| 时间范围 | 2016-02 ~ 2026-01 (120期) |
| 股票数 | 472只 |

### 绩效指标（含交易成本）

| 指标 | 数值 |
|------|------|
| 总收益率 | -20.92% |
| 年化收益 | -2.32% |
| 年化波动率 | 15.03% |
| Sharpe比率 | -0.08 |
| 最大回撤 | -38.50% |
| Calmar比率 | -0.06 |
| 胜率 | 49.17% |
| 盈亏比 | 0.94 |

### 绩效指标（不含交易成本）

| 指标 | 数值 |
|------|------|
| 总收益率 | -11.39% |
| 年化收益 | -1.20% |
| Sharpe比率 | -0.01 |
| 最大回撤 | -32.64% |
| 胜率 | 50.00% |
| 盈亏比 | 1.00 |

### 交易成本分析

| 指标 | 数值 |
|------|------|
| 平均换手率 | 47.25% |
| 中位数换手率 | 45.74% |
| 换手率范围 | 30.85% ~ 100.00% |
| 平均单期成本 | 0.0945% |
| 累计成本(各期成本相加) | 11.34% |
| 年化成本拖累 | 1.13% |

---

## 关键技术实现

### 1. 时间对齐（防look-ahead bias）⭐

**核心逻辑**:
```python
def align_weights_and_return(self, df_weights, df_return):
    # 关键: 将权重shift(1)
    df_weights_shifted = df_weights.shift(1)

    # 权重在t期末计算，用于t+1期交易
    # 所以第一期会变成NaN，需要移除
    df_weights_aligned = df_weights_shifted.iloc[1:]
    df_return_aligned = df_return.iloc[1:]

    return df_weights_aligned, df_return_aligned
```

**验证**:
- ✅ 输入122期因子 → 对齐后120期回测结果
- ✅ 第一期因子为NaN（已正确移除）
- ✅ 第t期的收益用的是第t-1期末算出的权重
- ✅ 滞后只在这里做一次, 因子内部不再额外滞后

### 2. 主回测循环

**核心逻辑**:
```python
for i, date in enumerate(dates):
    # 1. 获取当期权重和收益
    weights = df_weights.loc[date]
    returns = df_return.loc[date]

    # 2. 计算组合收益（不含成本）
    portfolio_return_no_cost = (weights * returns).sum()

    # 3. 计算换手率: TO = 0.5 × Σ|Δw|
    turnover = 0.5 * (weights - prev_weights).abs().sum()

    # 4. 计算交易成本
    cost = turnover * cost_bps / 10000  # 负值

    # 5. 含成本的收益率
    portfolio_return = portfolio_return_no_cost + cost

    # 6. 更新净值
    current_nav = current_nav * (1 + portfolio_return)
```

### 3. 绩效指标计算

**关键公式**:

```python
# 总收益: 从收益率序列连乘, 包含第一期
total_return = (1 + returns).prod() - 1

# 年化收益
annual_return = (1 + total_return) ** (periods_per_year / n_periods) - 1

# Sharpe比率
sharpe = mean_return / std_return * sqrt(periods_per_year)

# 最大回撤: 历史最高净值要把初始净值1.0算进去
running_peak = nav.cummax().clip(lower=1.0)
drawdown = (nav - running_peak) / running_peak
max_dd = drawdown.min()

# Calmar比率
calmar = annual_return / abs(max_dd)
```

---

## 验证结果

### ✅ 时间对齐验证
- 输入: 122期因子值
- 输出: 120期回测结果
- 第一期正确移除(shift后为NaN)
- 不含成本Sharpe为 -0.01, 没有出现"高得不正常"的迹象(偷看未来数据通常会让Sharpe异常高)

### ✅ 中性化验证
- 所有期数权重和的最大偏差 = 4.2e-17
- 多头权重和 = +1, 空头权重和 = -1

### ✅ 换手率验证
- 平均换手率 47.25%
- 第一期换手率 = 100.00%（全部建仓）
- 后续换手率在 30.85% ~ 98.94% 之间

### ✅ 成本计算验证
- 实际年化成本: 1.13%
- 理论年化成本: 47.25% × 12 × 0.002 ≈ 1.13%
- 相对误差 0.0%

### ✅ 净值曲线验证
- 第一期结束后的净值 = 0.9425（第一期收益 -5.75%）
- 最终净值(含成本) = 0.7908
- 最终净值(不含成本) = 0.8861
- 最大单期净值变化 14.88%

---

## 结果分析

### 动量因子表现

在 2016-02 ~ 2026-01 期间，这个最简单配置下的动量多空组合是**负收益**:
- 年化收益: -2.32% (含成本)
- 年化收益: -1.20% (不含成本)

扣成本前就不赚钱, 交易成本只是让亏损更大, 不是亏损的主因。

**读这个结果时要注意**:
- 这里只验证回测引擎算得对不对, 不代表"动量因子有效/无效"的结论
- 股票池是**今天的** S&P 500 成分股, 中途被剔除或退市的公司不在里面(幸存者偏差),
  多空两边都会受影响, 结果只能当参考
- 单个因子、单一市场、十年左右的样本, 统计上不足以下定论

### 交易成本影响

- 成本让年化收益少了 1.12%
- Sharpe 从 -0.01 变为 -0.08
- 每月调仓、平均换手率 47.25%: 换手越高, 成本吃掉的收益越多

---

## 文件结构

```
backtest/
├── __init__.py              # 模块导出
├── time_aligner.py          # 时间对齐器 ⭐
├── transaction.py           # 交易成本模型
├── metrics.py               # 绩效指标计算
└── engine.py                # 回测引擎 ⭐
```

---

**生成时间**: 2026-11-15 13:10
**生成方式**: `python scripts/generate_backtest_report.py`
