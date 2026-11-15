"""
[INPUT]: evaluation/robustness.py, portfolio/portfolio_builder.py
[OUTPUT]: 稳健性测试的回归测试 (分位数敏感性每个分位数只跑一组; 参数组合失败时报错)
[POS]: 防止"进入阈值和退出阈值被两两组合, 5个分位数跑出25组"再次出现

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import numpy as np
import pandas as pd
import pytest

from evaluation.robustness import RobustnessTest
from portfolio.portfolio_builder import PortfolioBuilder


def _random_panels(n_periods: int = 36, n_stocks: int = 40):
    """随机的因子值和月收益率, 只用来让回测能跑通"""
    rng = np.random.default_rng(0)
    dates = pd.date_range("2020-01-31", periods=n_periods, freq="ME")
    columns = [f"S{i}" for i in range(n_stocks)]
    df_factor = pd.DataFrame(rng.normal(size=(n_periods, n_stocks)), index=dates, columns=columns)
    df_return = pd.DataFrame(
        rng.normal(scale=0.05, size=(n_periods, n_stocks)), index=dates, columns=columns
    )
    return df_factor, df_return


def test_quantile_sensitivity_runs_one_pair_per_quantile():
    """5个进入阈值 → 正好5行, 每行的退出阈值 = 进入阈值 + 5%"""
    df_factor, df_return = _random_panels()
    quantile_list = [0.1, 0.15, 0.2, 0.25, 0.3]

    result = RobustnessTest().test_quantile_sensitivity(df_factor, df_return, quantile_list)

    assert len(result) == len(quantile_list)
    assert result["entry_quantile"].tolist() == pytest.approx(quantile_list)
    assert result["exit_quantile"].tolist() == pytest.approx([0.15, 0.2, 0.25, 0.3, 0.35])


def test_quantile_sensitivity_never_uses_exit_tighter_than_entry():
    """退出阈值不会比进入阈值更严"""
    df_factor, df_return = _random_panels()

    result = RobustnessTest().test_quantile_sensitivity(df_factor, df_return)

    assert (result["exit_quantile"] >= result["entry_quantile"]).all()


def test_exit_quantile_below_entry_quantile_is_rejected():
    """退出线比进入线还严(如25%进入/15%退出)没有意义, 构建器直接报错"""
    with pytest.raises(ValueError):
        PortfolioBuilder(entry_quantile=0.25, exit_quantile=0.15)


def test_exit_quantile_equal_to_entry_quantile_is_allowed():
    """进入线 = 退出线(没有缓冲带)是合法配置"""
    PortfolioBuilder(entry_quantile=0.2, exit_quantile=0.2)


def test_failing_parameter_combination_raises_instead_of_being_skipped():
    """某组参数跑不了(这里是退出阈值小于进入阈值)时要报错, 不能悄悄少一行"""
    df_factor, df_return = _random_panels()
    param_grid = {"entry_quantile": [0.25], "exit_quantile": [0.30, 0.15]}

    with pytest.raises(ValueError):
        RobustnessTest().test_parameter_sensitivity(df_factor, df_return, param_grid)
