"""
[INPUT]: backtest/metrics.py, backtest/engine.py
[OUTPUT]: 绩效指标与回测时间对齐的回归测试
[POS]: 防止"年化收益漏算第一期"再次出现, 并锁定"t期权重吃t+1期收益"

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import numpy as np
import pandas as pd
import pytest

from backtest.engine import BacktestEngine
from backtest.metrics import PerformanceMetrics, drawdown_series


def test_annual_return_includes_first_period():
    """第一个月+10%, 之后11个月不涨不跌 → 一年的年化收益就是10%, 不是0"""
    returns = pd.Series([0.10] + [0.0] * 11)
    nav = (1 + returns).cumprod()

    metrics = PerformanceMetrics(periods_per_year=12).calculate_all_metrics(returns, nav)

    assert metrics["total_return"] == pytest.approx(0.10)
    assert metrics["annual_return"] == pytest.approx(0.10)


def test_annual_return_is_geometric_over_all_periods():
    """24个月每月+1% → 年化 = 1.01^12 - 1"""
    returns = pd.Series([0.01] * 24)

    metrics = PerformanceMetrics(periods_per_year=12).calculate_all_metrics(returns)

    assert metrics["total_return"] == pytest.approx(1.01 ** 24 - 1)
    assert metrics["annual_return"] == pytest.approx(1.01 ** 12 - 1)


def test_drawdown_counts_loss_in_first_period():
    """第一个月就-10%然后走平: 最大回撤是-10%, 不是0 (初始净值1.0也是高点)"""
    returns = pd.Series([-0.10, 0.0, 0.0])
    nav = (1 + returns).cumprod()

    metrics = PerformanceMetrics(periods_per_year=12).calculate_all_metrics(returns, nav)

    assert metrics["max_drawdown"] == pytest.approx(-0.10)
    np.testing.assert_allclose(drawdown_series(nav), [-0.10, -0.10, -0.10])


def test_drawdown_measured_from_running_peak():
    """涨到1.2再跌到0.9: 回撤从1.2算起 = -25%"""
    nav = pd.Series([1.1, 1.2, 0.9, 1.0])

    np.testing.assert_allclose(drawdown_series(nav), [0.0, 0.0, -0.25, 1.0 / 1.2 - 1])


def _two_stock_setup():
    dates = pd.date_range("2021-01-31", periods=4, freq="ME")
    weights = pd.DataFrame({"A": [1.0] * 4, "B": [-1.0] * 4}, index=dates)
    returns = pd.DataFrame(0.0, index=dates, columns=["A", "B"])
    return dates, weights, returns


def test_engine_applies_weights_to_next_period_returns():
    """1月底定的权重(多A空B), 吃到的是2月的收益; 1月自己的收益不能算进来"""
    dates, weights, returns = _two_stock_setup()
    returns.loc[dates[0]] = [0.50, -0.50]   # 1月: 建仓之前的收益, 不该拿到
    returns.loc[dates[1]] = [0.10, -0.10]   # 2月: 多A赚10%, 空B赚10%

    result = BacktestEngine(cost_bps=0.0).run(weights, returns)

    assert result["returns"].index[0] == dates[1]
    assert result["returns"].iloc[0] == pytest.approx(0.20)
    assert result["returns"].iloc[1:].abs().sum() == pytest.approx(0.0)


def test_engine_metrics_match_final_nav():
    """指标里的总收益 = 最终净值 / 初始净值(1.0) - 1, 含第一期和交易成本"""
    dates, weights, returns = _two_stock_setup()
    returns.loc[dates[1]] = [0.10, -0.10]
    returns.loc[dates[2]] = [-0.02, 0.03]

    result = BacktestEngine(cost_bps=20.0).run(weights, returns)

    assert result["metrics"]["total_return"] == pytest.approx(result["nav"].iloc[-1] - 1.0)
    assert result["metrics_no_cost"]["total_return"] == pytest.approx(
        result["nav_no_cost"].iloc[-1] - 1.0
    )
    np.testing.assert_allclose(
        result["nav"].values, (1 + result["returns"]).cumprod().values
    )
