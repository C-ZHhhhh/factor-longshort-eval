"""
[INPUT]: backtest/beta_hedge.py, backtest/engine.py, backtest/time_aligner.py, data/data_cleaner.py
[OUTPUT]: Beta 对冲的回归测试
[POS]: 锁定四件事: (1) 股票Beta算得对; (2) 对冲仓位只用上个月末已知的Beta, 不偷看未来;
       (3) 对冲确实把市场暴露抵消掉, 成本按约定扣; (4) 给旧缓存补SPY日收益时不会弄坏缓存

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import numpy as np
import pandas as pd
import pytest

from backtest import beta_hedge
from backtest.engine import BacktestEngine
from backtest.time_aligner import TimeAligner
from data import data_cleaner


# ============================================================
# 股票的滚动 Beta
# ============================================================

def _daily_market(n_days: int = 400, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    return pd.Series(rng.normal(0.0005, 0.01, n_days), index=dates, name="SPY")


def test_rolling_beta_recovers_exact_slope():
    """股票日收益 = 2 × 市场 → Beta 正好是 2; = -0.5 × 市场 + 常数 → Beta 是 -0.5"""
    market = _daily_market()
    stocks = pd.DataFrame({"A": 2.0 * market, "B": -0.5 * market + 0.001})

    beta = beta_hedge.rolling_stock_beta(stocks, market, window=252, min_periods=126)

    last = beta.iloc[-1]
    assert last["A"] == pytest.approx(2.0)
    assert last["B"] == pytest.approx(-0.5)


def test_rolling_beta_ignores_days_without_stock_data():
    """股票有些天没数据: 只在有数据的那些天上回归, 斜率不变"""
    market = _daily_market()
    stock = 1.5 * market
    stock.iloc[::7] = np.nan  # 每7天缺一天

    beta = beta_hedge.rolling_stock_beta(stock.to_frame("A"), market, window=252, min_periods=126)

    assert beta["A"].iloc[-1] == pytest.approx(1.5)


def test_rolling_beta_needs_enough_history():
    """数据不够 min_periods 天时不给 Beta"""
    market = _daily_market(n_days=200)
    stocks = pd.DataFrame({"A": 2.0 * market})

    beta = beta_hedge.rolling_stock_beta(stocks, market, window=252, min_periods=126)

    days_seen = market.groupby(market.index.to_period("M")).size().cumsum()
    days_seen.index = days_seen.index.to_timestamp("M")
    assert beta.loc[days_seen[days_seen < 126].index, "A"].isna().all()
    assert beta.loc[days_seen[days_seen >= 126].index, "A"].notna().all()


def test_rolling_beta_does_not_use_future_data():
    """把某个月之后的数据全部改掉, 该月及之前的 Beta 不能变"""
    market = _daily_market()
    rng = np.random.default_rng(1)
    stocks = pd.DataFrame({"A": 1.2 * market + rng.normal(0, 0.005, len(market))})
    cutoff = pd.Timestamp("2021-01-31")

    original = beta_hedge.rolling_stock_beta(stocks, market)
    changed_stocks = stocks.copy()
    changed_stocks.loc[changed_stocks.index > cutoff, "A"] = 0.5
    changed = beta_hedge.rolling_stock_beta(changed_stocks, market)

    pd.testing.assert_series_equal(original.loc[:cutoff, "A"], changed.loc[:cutoff, "A"])
    assert not np.isclose(original["A"].iloc[-1], changed["A"].iloc[-1])


# ============================================================
# 对冲叠加
# ============================================================

def _book(market_monthly: pd.Series, beta_a: float = 1.5, beta_b: float = 0.5, cost: float = 0.0) -> dict:
    """做多A、做空B的组合; A、B的月收益正好是各自Beta乘以市场, 所以组合收益 = (beta_a - beta_b) × 市场"""
    dates = market_monthly.index
    weights = pd.DataFrame({"A": 1.0, "B": -1.0}, index=dates)
    returns_no_cost = (beta_a - beta_b) * market_monthly
    cost_series = pd.Series(cost, index=dates)
    returns = returns_no_cost - cost_series
    return {
        "nav": (1 + returns).cumprod(),
        "nav_no_cost": (1 + returns_no_cost).cumprod(),
        "returns": returns,
        "returns_no_cost": returns_no_cost,
        "turnover": pd.Series(0.0, index=dates),
        "cost_series": cost_series,
        "effective_weights": weights,
    }


def _monthly_market(n_months: int = 12) -> pd.Series:
    rng = np.random.default_rng(2)
    dates = pd.date_range("2021-01-31", periods=n_months, freq="ME")
    return pd.Series(rng.normal(0.01, 0.04, n_months), index=dates, name="SPY")


def _constant_beta(dates: pd.DatetimeIndex, beta_a: float = 1.5, beta_b: float = 0.5) -> pd.DataFrame:
    """比收益月份早一个月开始的 Beta 表 (第一个收益月要用到上个月末的 Beta)"""
    index = pd.date_range(dates[0] - pd.offsets.MonthEnd(1), dates[-1], freq="ME")
    return pd.DataFrame({"A": beta_a, "B": beta_b}, index=index)


def test_hedge_removes_market_exposure():
    """组合收益正好是 1.0 × 市场 → 对冲仓位 -1.0, 对冲后(不含成本)每个月收益都是 0"""
    market = _monthly_market()
    hedged = beta_hedge.apply_market_hedge(_book(market), _constant_beta(market.index), market, cost_bps=0.0)

    assert hedged["portfolio_beta"].tolist() == pytest.approx([1.0] * len(market))
    assert hedged["hedge_ratio"].tolist() == pytest.approx([-1.0] * len(market))
    assert hedged["returns_no_cost"].abs().max() == pytest.approx(0.0, abs=1e-12)
    assert hedged["nav_no_cost"].iloc[-1] == pytest.approx(1.0)


def test_hedge_uses_beta_known_at_previous_month_end():
    """第 t 月的对冲仓位只能用 t-1 月末的 Beta: 把每个月的 Beta 设成不同的数来检查"""
    market = _monthly_market(n_months=6)
    beta = _constant_beta(market.index)
    beta["A"] = np.arange(len(beta), dtype=float)  # 第k行(从0起)的A = k
    beta["B"] = 0.0

    hedged = beta_hedge.apply_market_hedge(_book(market), beta, market, cost_bps=0.0)

    # 第一个收益月用的是 Beta 表第0行(上个月末) → 组合Beta 0; 之后依次是 1, 2, ...
    assert hedged["portfolio_beta"].tolist() == pytest.approx([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    # 如果偷看了当月末的Beta, 会是 1, 2, 3, ...
    assert hedged["portfolio_beta"].iloc[0] != pytest.approx(1.0)


def test_hedge_cost_follows_position_changes():
    """对冲仓位的换手率 = 0.5 × |仓位变化| (建仓时从0算起), 成本 = 换手率 × bps"""
    market = _monthly_market(n_months=4)
    beta = _constant_beta(market.index)
    beta["A"] = [1.5, 1.5, 2.5, 2.5, 2.5]  # 组合Beta: 1.0, 1.0, 2.0, 2.0
    book = _book(market, cost=0.001)

    hedged = beta_hedge.apply_market_hedge(book, beta, market, cost_bps=20.0)

    hedge_turnover = [0.5, 0.0, 0.5, 0.0]
    assert hedged["turnover"].tolist() == pytest.approx(hedge_turnover)
    expected_cost = [0.001 + t * 20.0 / 10000 for t in hedge_turnover]
    assert hedged["cost_series"].tolist() == pytest.approx(expected_cost)
    # 含成本收益 = 不含成本收益 - 股票成本 - 对冲成本
    assert (hedged["returns_no_cost"] - hedged["returns"]).tolist() == pytest.approx(expected_cost)


def test_hedge_drops_leading_periods_without_beta():
    """样本开头没有 Beta 的月份不做对冲, 对冲后的结果从有 Beta 的那个月开始"""
    market = _monthly_market(n_months=6)
    beta = _constant_beta(market.index)
    beta.iloc[:3] = np.nan  # 前3行没有Beta → 前3个收益月没法对冲

    hedged = beta_hedge.apply_market_hedge(_book(market), beta, market, cost_bps=0.0)

    assert hedged["returns"].index.equals(market.index[3:])
    unhedged = beta_hedge.restrict_to_dates(_book(market), hedged["returns"].index)
    assert unhedged["returns"].index.equals(hedged["returns"].index)
    assert unhedged["nav"].iloc[0] == pytest.approx(1 + unhedged["returns"].iloc[0])


def test_portfolio_beta_fills_a_missing_stock_with_the_median_of_holdings():
    """个别持仓没有 Beta 时用其他持仓的中位数代替; 缺得太多则不给组合Beta"""
    dates = pd.date_range("2021-01-31", periods=2, freq="ME")
    weights = pd.DataFrame(
        {"A": [0.25, 0.25], "B": [0.25, 0.25], "C": [0.25, 0.25], "D": [0.25, 0.25],
         "E": [-0.5, -0.5], "F": [-0.5, -0.5]},
        index=dates,
    )
    betas = pd.DataFrame(1.0, index=dates, columns=weights.columns)
    betas.loc[dates[0], "A"] = np.nan                       # 第1期只缺一只 (权重占 12.5%)
    betas.loc[dates[1], ["A", "B", "C", "D"]] = np.nan      # 第2期缺了一半

    result = beta_hedge.portfolio_beta(weights, betas)

    assert result.iloc[0] == pytest.approx(0.0)  # A 用中位数 1.0 补上: 多头1.0 - 空头1.0
    assert np.isnan(result.iloc[1])


def test_lag_to_return_dates_rejects_missing_months():
    """月份不连续时 shift(1) 不等于滞后一个月, 必须报错"""
    index = pd.to_datetime(["2021-01-31", "2021-02-28", "2021-04-30"])
    frame = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=index)

    with pytest.raises(ValueError):
        TimeAligner().lag_to_return_dates(frame, index)


# ============================================================
# 回测引擎: 实际生效的权重
# ============================================================

def test_engine_reports_the_weights_actually_used():
    """effective_weights 乘以当月收益再求和 = 引擎算出的组合收益; 非调仓月沿用上次调仓的权重"""
    rng = np.random.default_rng(3)
    dates = pd.date_range("2021-01-31", periods=7, freq="ME")
    columns = [f"S{i}" for i in range(6)]
    weights = pd.DataFrame(0.0, index=dates, columns=columns)
    for i, date in enumerate(dates):
        long_stock, short_stock = columns[i % 6], columns[(i + 3) % 6]
        weights.loc[date, long_stock] = 1.0
        weights.loc[date, short_stock] = -1.0
    returns = pd.DataFrame(rng.normal(0, 0.05, (7, 6)), index=dates, columns=columns)

    result = BacktestEngine(cost_bps=20.0, rebalance_freq="2monthly").run(weights, returns)

    effective = result["effective_weights"]
    assert effective.index.equals(result["returns"].index)
    recomputed = (effective * returns.loc[effective.index]).sum(axis=1)
    pd.testing.assert_series_equal(recomputed, result["returns_no_cost"], check_names=False)
    # 第2期不调仓: 权重和第1期一样
    pd.testing.assert_series_equal(effective.iloc[1], effective.iloc[0], check_names=False)
    assert not effective.iloc[2].equals(effective.iloc[1])


# ============================================================
# 市场基准的日收益率
# ============================================================

class _FakeFetcher:
    """测试用: 不联网, 返回预先造好的价格"""

    def __init__(self, price: pd.Series):
        self.price = price

    def fetch(self, tickers, start_date, end_date=None):
        return {tickers[0]: pd.DataFrame({"Adj Close": self.price})}


def _benchmark_price() -> pd.Series:
    rng = np.random.default_rng(4)
    dates = pd.bdate_range("2021-01-01", "2021-06-30")
    return pd.Series(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, len(dates))), index=dates)


def test_benchmark_daily_and_monthly_returns_agree():
    """日收益率按月连乘 = 月收益率 (两者来自同一份价格)"""
    monthly, daily = data_cleaner.fetch_benchmark_returns(
        _FakeFetcher(_benchmark_price()), "2021-01-01", "2021-07-01"
    )

    compounded = (1 + daily).groupby(daily.index.to_period("M")).prod() - 1
    compounded.index = compounded.index.to_timestamp("M")
    pd.testing.assert_series_equal(
        compounded.loc[monthly.index], monthly, check_names=False, check_freq=False
    )


def _write_cache(path, price: pd.Series) -> dict:
    monthly, _ = data_cleaner.fetch_benchmark_returns(_FakeFetcher(price), "2021-01-01", "2021-07-01")
    cache = {"price": pd.DataFrame({"AAA": price}), "SPY": monthly}
    pd.to_pickle(cache, path)
    return cache


def test_add_benchmark_daily_only_adds_one_key(tmp_path):
    """给旧缓存补日收益率: 只多出 SPY_daily 一个键, 原有数据不变"""
    price = _benchmark_price()
    cache_file = tmp_path / "cache.pkl"
    original = _write_cache(cache_file, price)

    daily = data_cleaner.add_benchmark_daily_to_cache(cache_file, yf_fetcher=_FakeFetcher(price))

    patched = pd.read_pickle(cache_file)
    assert set(patched) == set(original) | {"SPY_daily"}
    pd.testing.assert_frame_equal(patched["price"], original["price"])
    pd.testing.assert_series_equal(patched["SPY"], original["SPY"])
    pd.testing.assert_series_equal(patched["SPY_daily"], daily)
    assert not (tmp_path / "cache.pkl.tmp").exists()


def test_add_benchmark_daily_refuses_a_different_benchmark(tmp_path):
    """新下载的基准和缓存里的月收益率对不上 → 报错, 缓存文件原样不动"""
    price = _benchmark_price()
    cache_file = tmp_path / "cache.pkl"
    _write_cache(cache_file, price)
    before = cache_file.read_bytes()

    other_price = price * np.linspace(1.0, 1.5, len(price))  # 另一条价格
    with pytest.raises(RuntimeError):
        data_cleaner.add_benchmark_daily_to_cache(cache_file, yf_fetcher=_FakeFetcher(other_price))

    assert cache_file.read_bytes() == before
