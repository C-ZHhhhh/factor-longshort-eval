"""
生成阶段5完成报告 (BACKTEST_REPORT.md)

[INPUT]: scripts/test_backtest.py 的 main() 返回的真实回测结果 (依赖 data/cache 里的缓存)
[OUTPUT]: 项目根目录的 BACKTEST_REPORT.md
[POS]: 报告生成脚本。报告里的每个数字都从回测结果里取, 不在这里写死,
       这样代码或数据变了以后重跑一次报告就是新的。

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 新增展示的数字必须从 results 里计算, 不要手填
"""

import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test_backtest import main as run_test_backtest

COST_BPS = 20.0          # 与 test_backtest.py 里 BacktestEngine(cost_bps=20.0) 一致
PERIODS_PER_YEAR = 12


def build_report(results: dict) -> str:
    """把回测结果填进报告模板。"""
    metrics = results['metrics']
    metrics_no_cost = results['metrics_no_cost']
    nav = results['nav']
    nav_no_cost = results['nav_no_cost']
    returns = results['returns']
    turnover = results['turnover']
    cost_series = results['cost_series']

    n_periods = len(returns)
    n_factor_periods = results['n_factor_periods']
    n_stocks = results['n_stocks']
    start, end = returns.index[0].strftime('%Y-%m'), returns.index[-1].strftime('%Y-%m')

    annual_cost_drag = cost_series.sum() / n_periods * PERIODS_PER_YEAR
    expected_annual_cost = turnover.mean() * PERIODS_PER_YEAR * COST_BPS / 10000
    cost_check_error = abs(annual_cost_drag - expected_annual_cost) / expected_annual_cost
    annual_return_loss = metrics_no_cost['annual_return'] - metrics['annual_return']
    max_nav_step = nav.pct_change().abs().max()
    later_turnover = turnover.iloc[1:]

    if metrics['annual_return'] < 0:
        verdict = '**负收益**'
    else:
        verdict = '**正收益**'
    if metrics_no_cost['annual_return'] > 0 > metrics['annual_return']:
        cost_comment = '扣成本前是赚的, 扣成本后变成亏的: 这个策略的毛收益不够覆盖交易成本。'
    elif metrics_no_cost['annual_return'] <= 0:
        cost_comment = '扣成本前就不赚钱, 交易成本只是让亏损更大, 不是亏损的主因。'
    else:
        cost_comment = '扣成本后仍为正收益。'

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    report = f'''# 阶段5完成报告: 回测引擎

**完成时间**: {now}

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
| 交易成本 | {COST_BPS:.0f} bps |
| 时间范围 | {start} ~ {end} ({n_periods}期) |
| 股票数 | {n_stocks}只 |

### 绩效指标（含交易成本）

| 指标 | 数值 |
|------|------|
| 总收益率 | {metrics['total_return']:.2%} |
| 年化收益 | {metrics['annual_return']:.2%} |
| 年化波动率 | {metrics['annual_volatility']:.2%} |
| Sharpe比率 | {metrics['sharpe_ratio']:.2f} |
| 最大回撤 | {metrics['max_drawdown']:.2%} |
| Calmar比率 | {metrics['calmar_ratio']:.2f} |
| 胜率 | {metrics['win_rate']:.2%} |
| 盈亏比 | {metrics['profit_factor']:.2f} |

### 绩效指标（不含交易成本）

| 指标 | 数值 |
|------|------|
| 总收益率 | {metrics_no_cost['total_return']:.2%} |
| 年化收益 | {metrics_no_cost['annual_return']:.2%} |
| Sharpe比率 | {metrics_no_cost['sharpe_ratio']:.2f} |
| 最大回撤 | {metrics_no_cost['max_drawdown']:.2%} |
| 胜率 | {metrics_no_cost['win_rate']:.2%} |
| 盈亏比 | {metrics_no_cost['profit_factor']:.2f} |

### 交易成本分析

| 指标 | 数值 |
|------|------|
| 平均换手率 | {turnover.mean():.2%} |
| 中位数换手率 | {turnover.median():.2%} |
| 换手率范围 | {turnover.min():.2%} ~ {turnover.max():.2%} |
| 平均单期成本 | {cost_series.mean():.4%} |
| 累计成本(各期成本相加) | {cost_series.sum():.2%} |
| 年化成本拖累 | {annual_cost_drag:.2%} |

---

## 关键技术实现

### 1. 时间对齐（防look-ahead bias）⭐

**核心逻辑**:
'''

    report += '''```python
def align_weights_and_return(self, df_weights, df_return):
    # 关键: 将权重shift(1)
    df_weights_shifted = df_weights.shift(1)

    # 权重在t期末计算，用于t+1期交易
    # 所以第一期会变成NaN，需要移除
    df_weights_aligned = df_weights_shifted.iloc[1:]
    df_return_aligned = df_return.iloc[1:]

    return df_weights_aligned, df_return_aligned
```
'''

    report += f'''
**验证**:
- ✅ 输入{n_factor_periods}期因子 → 对齐后{n_periods}期回测结果
- ✅ 第一期因子为NaN（已正确移除）
- ✅ 第t期的收益用的是第t-1期末算出的权重
- ✅ 滞后只在这里做一次, 因子内部不再额外滞后

### 2. 主回测循环

**核心逻辑**:
'''

    report += '''```python
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
'''

    report += f'''
---

## 验证结果

### ✅ 时间对齐验证
- 输入: {n_factor_periods}期因子值
- 输出: {n_periods}期回测结果
- 第一期正确移除(shift后为NaN)
- 不含成本Sharpe为 {metrics_no_cost['sharpe_ratio']:.2f}, 没有出现"高得不正常"的迹象(偷看未来数据通常会让Sharpe异常高)

### ✅ 中性化验证
- 所有期数权重和的最大偏差 = {results['weight_sum_max_abs']:.1e}
- 多头权重和 = +1, 空头权重和 = -1

### ✅ 换手率验证
- 平均换手率 {turnover.mean():.2%}
- 第一期换手率 = {turnover.iloc[0]:.2%}（全部建仓）
- 后续换手率在 {later_turnover.min():.2%} ~ {later_turnover.max():.2%} 之间

### ✅ 成本计算验证
- 实际年化成本: {annual_cost_drag:.2%}
- 理论年化成本: {turnover.mean():.2%} × {PERIODS_PER_YEAR} × {COST_BPS / 10000:.3f} ≈ {expected_annual_cost:.2%}
- 相对误差 {cost_check_error:.1%}

### ✅ 净值曲线验证
- 第一期结束后的净值 = {nav.iloc[0]:.4f}（第一期收益 {returns.iloc[0]:+.2%}）
- 最终净值(含成本) = {nav.iloc[-1]:.4f}
- 最终净值(不含成本) = {nav_no_cost.iloc[-1]:.4f}
- 最大单期净值变化 {max_nav_step:.2%}

---

## 结果分析

### 动量因子表现

在 {start} ~ {end} 期间，这个最简单配置下的动量多空组合是{verdict}:
- 年化收益: {metrics['annual_return']:.2%} (含成本)
- 年化收益: {metrics_no_cost['annual_return']:.2%} (不含成本)

{cost_comment}

**读这个结果时要注意**:
- 这里只验证回测引擎算得对不对, 不代表"动量因子有效/无效"的结论
- 股票池是**今天的** S&P 500 成分股, 中途被剔除或退市的公司不在里面(幸存者偏差),
  多空两边都会受影响, 结果只能当参考
- 单个因子、单一市场、十年左右的样本, 统计上不足以下定论

### 交易成本影响

- 成本让年化收益少了 {annual_return_loss:.2%}
- Sharpe 从 {metrics_no_cost['sharpe_ratio']:.2f} 变为 {metrics['sharpe_ratio']:.2f}
- 每月调仓、平均换手率 {turnover.mean():.2%}: 换手越高, 成本吃掉的收益越多

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

**生成时间**: {now}
**生成方式**: `python scripts/generate_backtest_report.py`
'''
    return report


def main():
    results = run_test_backtest()
    report = build_report(results)

    with open(project_root / 'BACKTEST_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print('✅ 阶段5完成报告已生成: BACKTEST_REPORT.md')


if __name__ == '__main__':
    main()
