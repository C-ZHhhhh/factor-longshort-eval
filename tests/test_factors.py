"""
[INPUT]: factors/momentum.py, factors/reversal.py, backtest/time_aligner.py
[OUTPUT]: 因子方向与时间约定的回归测试
[POS]: 防止"动量方向写反""反转多滞后一个月"这类错误再次出现

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import numpy as np
import pandas as pd

from backtest.time_aligner import TimeAligner
from factors.momentum import MomentumFactor
from factors.reversal import ReversalFactor


def test_momentum_is_past_return_skipping_latest_month(daily_prices):
    """动量_t = P(t-1月末) / P(t-12月末) - 1"""
    factor = MomentumFactor().calculate(daily_prices)
    monthly = daily_prices.resample("ME").last()

    t = factor.index[5]
    pos = monthly.index.get_loc(t)
    expected = monthly.iloc[pos - 1] / monthly.iloc[pos - 12] - 1

    pd.testing.assert_series_equal(factor.loc[t], expected, check_names=False)


def test_momentum_ranks_past_winners_highest(daily_prices):
    """过去涨得最多的股票因子值最高, 跌得最多的最低 (方向不能反)"""
    factor = MomentumFactor().calculate(daily_prices)

    for _, row in factor.iterrows():
        assert row.idxmax() == "S7"
        assert row.idxmin() == "S0"
        assert row.is_monotonic_increasing


def test_momentum_ignores_latest_month(daily_prices):
    """跳过最近1个月: 改动t月的价格不应改变t月的动量"""
    baseline = MomentumFactor().calculate(daily_prices)
    t = baseline.index[-1]

    shocked = daily_prices.copy()
    in_last_month = (shocked.index.year == t.year) & (shocked.index.month == t.month)
    shocked.loc[in_last_month, "S3"] *= 5.0

    after = MomentumFactor().calculate(shocked)
    pd.testing.assert_series_equal(after.loc[t], baseline.loc[t])


def test_reversal_is_negative_of_same_month_return(daily_prices):
    """反转_t = -(t月收益率), 因子内部不再额外滞后"""
    factor = ReversalFactor().calculate(daily_prices)
    monthly_return = daily_prices.resample("ME").last().pct_change()

    t = factor.index[7]
    pd.testing.assert_series_equal(factor.loc[t], -monthly_return.loc[t], check_names=False)


def test_reversal_is_lagged_exactly_once_by_aligner(daily_prices):
    """经过时间对齐后: t+1月的收益对应的是t月的反转因子(只滞后一期, 不是两期)"""
    factor = ReversalFactor().calculate(daily_prices)
    monthly_return = daily_prices.resample("ME").last().pct_change().dropna(how="all")

    aligned_factor, aligned_return = TimeAligner().align_factor_and_return(factor, monthly_return)

    t_plus_1 = aligned_factor.index[4]
    t = monthly_return.index[monthly_return.index.get_loc(t_plus_1) - 1]

    np.testing.assert_allclose(aligned_factor.loc[t_plus_1], -monthly_return.loc[t])
    assert aligned_return.index.equals(aligned_factor.index)
