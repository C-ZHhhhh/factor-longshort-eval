"""
[INPUT]: portfolio/portfolio_builder.py
[OUTPUT]: 组合构建的回归测试 (多空不重叠、权重中性、阈值与最小持有期)
[POS]: 防止"同一只股票同时在多头和空头名单"再次出现

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import numpy as np
import pandas as pd
import pytest

from portfolio.portfolio_builder import PortfolioBuilder


def _factor_panel(rows: list) -> pd.DataFrame:
    """每行是一期的因子值, 列为S0..Sn"""
    dates = pd.date_range("2021-01-31", periods=len(rows), freq="ME")
    columns = [f"S{i}" for i in range(len(rows[0]))]
    return pd.DataFrame(rows, index=dates, columns=columns, dtype=float)


def test_locked_long_is_not_shorted_when_it_drops_to_bottom():
    """
    S0第一期排第一(做多), 第二期起跌到最后一名。
    最小持有期=3: 持有满3期之前必须留在多头, 且不能同时被做空。
    """
    top_then_bottom = [
        [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        [-10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        [-10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        [-10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        [-10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    ]
    builder = PortfolioBuilder(entry_quantile=0.2, exit_quantile=0.3, min_holding_periods=3)
    holdings = builder.build(_factor_panel(top_then_bottom), neutralize=False)

    s0 = holdings["S0"].tolist()
    assert s0[:3] == [1, 1, 1]      # 第1~3期: 被最小持有期锁在多头, 期间不会被做空
    assert s0[3:] == [-1, -1]       # 第4期: 满3期且已掉出阈值 → 多头退出, 这时才允许反手做空


def test_no_stock_is_both_long_and_short_on_random_panel():
    """随机因子 + 长最小持有期(最容易产生重叠的配置): 多空名单逐期不相交"""
    rng = np.random.default_rng(0)
    n_periods, n_stocks = 60, 40
    panel = _factor_panel(rng.normal(size=(n_periods, n_stocks)).tolist())

    builder = PortfolioBuilder(entry_quantile=0.25, exit_quantile=0.30, min_holding_periods=12)
    seen = []
    original_build_sides = builder._build_sides

    def record(valid_values):
        long_holdings, short_holdings = original_build_sides(valid_values)
        seen.append((set(long_holdings), set(short_holdings)))
        return long_holdings, short_holdings

    builder._build_sides = record
    holdings = builder.build(panel, neutralize=False)

    assert len(seen) == n_periods
    for (long_set, short_set), (_, row) in zip(seen, holdings.iterrows()):
        assert not (long_set & short_set)
        # 名单和持仓矩阵一致: 没有哪只多头被空头标记覆盖
        assert set(row.index[row == 1]) == long_set
        assert set(row.index[row == -1]) == short_set


def test_weights_are_dollar_neutral():
    """多头权重和=+1, 空头权重和=-1, 合计=0"""
    rng = np.random.default_rng(1)
    panel = _factor_panel(rng.normal(size=(36, 30)).tolist())

    weights = PortfolioBuilder(0.25, 0.30, 12).build(panel, neutralize=True)

    np.testing.assert_allclose(weights.where(weights > 0, 0).sum(axis=1), 1.0)
    np.testing.assert_allclose(weights.where(weights < 0, 0).sum(axis=1), -1.0)
    np.testing.assert_allclose(weights.sum(axis=1), 0.0, atol=1e-12)


def test_plain_quantile_portfolio_without_constraints():
    """进入=退出阈值且最小持有期=1时, 退化为普通的前20%/后20%"""
    rng = np.random.default_rng(2)
    panel = _factor_panel(rng.normal(size=(12, 20)).tolist())

    holdings = PortfolioBuilder(0.2, 0.2, min_holding_periods=1).build(panel, neutralize=False)

    for date, row in holdings.iterrows():
        ranked = panel.loc[date].sort_values(ascending=False)
        assert set(row.index[row == 1]) == set(ranked.index[:4])
        assert set(row.index[row == -1]) == set(ranked.index[-4:])


def test_entry_quantile_above_half_is_rejected():
    """进入阈值超过50%时多空进入区必然重叠, 直接报错"""
    with pytest.raises(ValueError):
        PortfolioBuilder(entry_quantile=0.6, exit_quantile=0.7)
