"""
Beta 对冲前后对比

[INPUT]:
- backtest_results (dict): {策略名: BacktestEngine.run() 的结果}
- df_return_daily / market_return_daily: 股票和市场基准的日收益率 (估计股票 Beta 用)
- market_return (Series): 市场基准月收益率

[OUTPUT]:
- compare_hedged(): 对比表 (每个策略一行: 对冲前/后的实现 Beta、年化收益、Sharpe、回撤、显著性)
  和对冲后的回测结果
- create_markdown(): 对比表的 Markdown 报告

[POS]:
回答一个问题: 策略的亏损里, 有多少只是因为"跟着大盘反着走"(市场暴露), 有多少是因子本身的问题。
做法是给每个策略加上市场对冲 (backtest/beta_hedge.py), 再和对冲前比。

[PROTOCOL]:
1. 对冲前和对冲后必须用同一段时间比 (对冲后的样本开头会少几个月)
2. "实现 Beta"是事后用月收益对市场回归得到的, 用来检验对冲有没有效;
   对冲仓位本身用的是事前估计的 Beta, 两者不是一回事
3. 逻辑变更时同步更新此头部, 并检查 evaluation/CLAUDE.md
"""

from typing import Dict, Tuple

import pandas as pd

from backtest import beta_hedge
from backtest.metrics import PerformanceMetrics
from evaluation.exposure_check import ExposureChecker
from evaluation.significance import newey_west_mean_test

PERIODS_PER_YEAR = 12


def _side_stats(result: Dict, market_return: pd.Series, suffix: str) -> Dict:
    """一侧 (对冲前或对冲后) 的指标, 键名带上 _before / _after 后缀。"""
    metrics = PerformanceMetrics(periods_per_year=PERIODS_PER_YEAR)
    net = metrics.calculate_all_metrics(result['returns'], result['nav'])
    gross = metrics.calculate_all_metrics(result['returns_no_cost'], result['nav_no_cost'])
    exposure = ExposureChecker().estimate_beta_from_returns(
        df_portfolio_return=result['returns'], df_market_return=market_return
    )
    nw_t_stat, nw_p_value = newey_west_mean_test(result['returns'])
    stats = {
        'beta': exposure['beta'],
        'annual_return': net['annual_return'],
        'annual_return_gross': gross['annual_return'],
        'annual_vol': net['annual_volatility'],
        'sharpe': net['sharpe_ratio'],
        'max_drawdown': net['max_drawdown'],
        'mean_return': float(result['returns'].mean()),
        'nw_t_stat': nw_t_stat,
        'nw_p_value': nw_p_value,
    }
    return {f"{key}_{suffix}": value for key, value in stats.items()}


def compare_hedged(
    backtest_results: Dict,
    df_return_daily: pd.DataFrame,
    market_return_daily: pd.Series,
    market_return: pd.Series,
    cost_bps: float = 20.0
) -> Tuple[pd.DataFrame, Dict]:
    """
    给每个策略加上市场对冲, 并和对冲前比较

    Returns:
        (对比表, {策略名: 对冲后的回测结果})
        对比表每个策略一行; 对冲前的指标是在"对冲后那段时间"上重新算的, 两边可比。
    """
    df_beta = beta_hedge.rolling_stock_beta(df_return_daily, market_return_daily)

    rows, hedged_results = [], {}
    for name, result in backtest_results.items():
        hedged = beta_hedge.apply_market_hedge(result, df_beta, market_return, cost_bps=cost_bps)
        unhedged = beta_hedge.restrict_to_dates(result, hedged['returns'].index)
        hedged_results[name] = hedged

        row = {
            'factor': name,
            'start': hedged['returns'].index[0].strftime('%Y-%m'),
            'end': hedged['returns'].index[-1].strftime('%Y-%m'),
            'n_periods': len(hedged['returns']),
            # 事前估计的组合 Beta (对冲仓位 = 它的相反数)
            'ex_ante_beta_mean': float(hedged['portfolio_beta'].mean()),
            'ex_ante_beta_min': float(hedged['portfolio_beta'].min()),
            'ex_ante_beta_max': float(hedged['portfolio_beta'].max()),
            'hedge_cost_annual': float(
                (hedged['cost_series'] - unhedged['cost_series']).mean() * PERIODS_PER_YEAR
            ),
        }
        row.update(_side_stats(unhedged, market_return, 'before'))
        row.update(_side_stats(hedged, market_return, 'after'))
        rows.append(row)

    return pd.DataFrame(rows), hedged_results


def create_markdown(df_comparison: pd.DataFrame, benchmark_name: str, conclusion: str) -> str:
    """对比表的 Markdown 报告。conclusion 由 report_narrative.describe_beta_hedge() 给出。"""
    md = f"""# Beta 对冲前后对比

生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 做了什么

原来的多空组合只做到资金中性 (多空两边金额相等), 它的收益仍然会跟着大盘走。
这里在组合之外加一份 {benchmark_name} 仓位把这部分抵消掉:

1. 用过去 {beta_hedge.BETA_WINDOW_DAYS} 个交易日的日收益对 {benchmark_name} 回归, 得到每只股票的 Beta
2. 组合 Beta = Σ(权重 × 股票 Beta), 只用上个月末已知的 Beta
3. 对冲仓位 = -组合 Beta, 每月更新一次
4. 调整对冲仓位按同样的成本计入 (换手率 = 0.5 × |仓位变化|)

选股和权重没有任何改动。对冲前、对冲后用的是同一段时间。

---

## 市场暴露: 对冲有没有效

"实现 Beta"是事后用策略月收益对 {benchmark_name} 月收益回归得到的。"事前组合 Beta"是对冲时用的估计值。

| 策略 | 区间 | 事前组合 Beta (均值) | 实现 Beta (对冲前) | 实现 Beta (对冲后) |
|------|------|---------------------|-------------------|-------------------|
"""
    for _, row in df_comparison.iterrows():
        md += (
            f"| {row['factor']} | {row['start']} ~ {row['end']} ({row['n_periods']} 月) "
            f"| {row['ex_ante_beta_mean']:+.4f} | {row['beta_before']:+.4f} | {row['beta_after']:+.4f} |\n"
        )

    md += """
---

## 绩效: 对冲前 → 对冲后 (均已扣除交易成本)

| 策略 | 年化收益 | Sharpe | 最大回撤 | 年化波动 | 显著性 p 值 |
|------|---------|--------|----------|---------|------------|
"""
    for _, row in df_comparison.iterrows():
        md += (
            f"| {row['factor']} "
            f"| {row['annual_return_before']:.2%} → {row['annual_return_after']:.2%} "
            f"| {row['sharpe_before']:.2f} → {row['sharpe_after']:.2f} "
            f"| {row['max_drawdown_before']:.2%} → {row['max_drawdown_after']:.2%} "
            f"| {row['annual_vol_before']:.2%} → {row['annual_vol_after']:.2%} "
            f"| {row['nw_p_value_before']:.3f} → {row['nw_p_value_after']:.3f} |\n"
        )

    md += f"""
显著性: 对月度净收益做 Newey-West 检验, p 值小于 0.05 才算显著。

---

## 结论

{conclusion}
---

## 读这张表时要注意

- **对冲仓位没有算资金成本**: 相当于用期货对冲且不计无风险利率。对冲仓位是买入 {benchmark_name} 的策略
  (事前组合 Beta 为负的), 对冲后的收益因此偏高。
- **做空 {benchmark_name} 的借券费没有算**: 影响事前组合 Beta 为正的策略。
- **Beta 窗口没有调过**: {beta_hedge.BETA_WINDOW_DAYS} 天是事先定的常规取值, 没有拿结果去挑。
- 幸存者偏差等其他局限和正式结果一样。

---

*本报告由统一评估器自动生成*
"""
    return md
