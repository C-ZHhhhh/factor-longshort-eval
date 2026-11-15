"""
Beta 对冲

[INPUT]:
- df_return_daily (DataFrame): 股票日收益率
- market_return_daily (Series): 市场基准 (SPY) 日收益率
- market_return (Series): 市场基准月收益率
- backtest_result (dict): BacktestEngine.run() 的结果, 需含 effective_weights

[OUTPUT]:
- rolling_stock_beta(): 每只股票在每个月末的 Beta (只用到该月末及之前的日数据)
- apply_market_hedge(): 加上市场对冲仓位后的回测结果 (键与引擎结果相同, 可直接算绩效)

[POS]:
回测层的对冲叠加模块。不改动选股和权重, 只在原来的多空组合之外加一份市场基准仓位,
把组合对大盘的敏感度 (Beta) 抵消掉。

做法:
1. 用过去 252 个交易日的日收益, 对市场回归, 得到每只股票的 Beta
2. 组合 Beta = Σ(权重 × 股票 Beta), 用的是上个月末已知的 Beta
3. 对冲仓位 = -组合 Beta (组合 Beta 为 -0.3 就买入 0.3 份市场基准)
4. 对冲后收益 = 原收益 + 对冲仓位 × 市场当月收益 - 调整对冲仓位的交易成本

[PROTOCOL]:
1. 不偷看未来: 第 t 月的对冲仓位只能用 t-1 月末及之前的数据。
   滞后统一通过 TimeAligner.lag_to_return_dates() 完成, 这里不自己 shift。
2. Beta 的窗口 (252 天) 是事先定好的常规取值, 不拿回测结果去挑, 否则又是事后挑选。
3. 对冲仓位每月更新一次 (股票仓位不动时也更新), 换手率按 0.5 × |仓位变化| 计入成本,
   与股票仓位的换手率口径一致。
4. 没有扣对冲仓位的资金成本 (相当于用期货对冲且不计无风险利率); 做空基准的借券费也没算。
5. 逻辑变更时同步更新此头部, 并检查 backtest/CLAUDE.md。
"""

from typing import Dict

import numpy as np
import pandas as pd

from backtest.time_aligner import TimeAligner
from utils.logger import get_logger

logger = get_logger(__name__)

BETA_WINDOW_DAYS = 252      # 约一年的交易日
BETA_MIN_DAYS = 126         # 至少半年的数据才给出 Beta
MIN_BETA_COVERAGE = 0.8     # 持仓里至少这么大比例(按权重绝对值)有 Beta, 这一期才做对冲
INITIAL_NAV = 1.0


def rolling_stock_beta(
    df_return_daily: pd.DataFrame,
    market_return_daily: pd.Series,
    window: int = BETA_WINDOW_DAYS,
    min_periods: int = BETA_MIN_DAYS
) -> pd.DataFrame:
    """
    每只股票在每个月末的滚动 Beta

    Beta = Cov(股票日收益, 市场日收益) / Var(市场日收益), 用最近 window 个交易日。
    股票某天没有数据时, 那一天在它的协方差和方差里都不参与, 所以结果就是
    "在有数据的那些天上做一元回归"的斜率。

    Args:
        df_return_daily: 日期 × 股票 的日收益率
        market_return_daily: 市场基准日收益率
        window: 滚动窗口 (交易日)
        min_periods: 窗口内至少要有多少天数据

    Returns:
        月末日期 × 股票 的 Beta。第 t 行只用到 t 月最后一个交易日及之前的数据。
    """
    common_dates = df_return_daily.index.intersection(market_return_daily.index)
    if len(common_dates) == 0:
        raise ValueError("股票日收益和市场日收益没有共同的日期")
    stock = df_return_daily.loc[common_dates]
    market = market_return_daily.loc[common_dates]

    observed = stock.notna()
    x = stock.fillna(0.0)
    # 市场收益只在该股票有数据的那些天计入, 保证协方差和方差用的是同一批日子
    m = observed.mul(market, axis=0)

    rolling = lambda frame: frame.rolling(window, min_periods=1).sum()
    n = rolling(observed.astype(float))
    sum_x, sum_m = rolling(x), rolling(m)
    sum_xm, sum_mm = rolling(x * m), rolling(m * m)

    covariance = sum_xm - sum_x * sum_m / n
    variance = sum_mm - sum_m * sum_m / n
    beta = (covariance / variance).where((n >= min_periods) & (variance > 0))

    return beta.resample('ME').last()


def portfolio_beta(effective_weights: pd.DataFrame, df_beta_lagged: pd.DataFrame) -> pd.Series:
    """
    每一期的组合 Beta = Σ(权重 × 股票 Beta)

    个别持仓股票没有 Beta (上市不满半年等) 时, 用当期持仓里其他股票 Beta 的中位数代替;
    有 Beta 的持仓占比 (按权重绝对值) 低于 MIN_BETA_COVERAGE 时, 这一期不给出组合 Beta (NaN)。

    Args:
        effective_weights: 收益月份 × 股票, 每期实际生效的权重
        df_beta_lagged: 同索引, 第 t 行是 t-1 月末已知的股票 Beta

    Returns:
        组合 Beta 序列, 与 effective_weights 同索引
    """
    betas = df_beta_lagged.reindex(index=effective_weights.index, columns=effective_weights.columns)
    held = effective_weights != 0
    gross = effective_weights.abs()

    coverage = gross.where(betas.notna(), 0.0).sum(axis=1) / gross.sum(axis=1)
    held_median = betas.where(held).median(axis=1)
    filled = betas.where(betas.notna(), held_median, axis=0)

    result = (effective_weights * filled.where(held, 0.0)).sum(axis=1)
    return result.where(coverage >= MIN_BETA_COVERAGE)


def apply_market_hedge(
    backtest_result: Dict,
    df_beta: pd.DataFrame,
    market_return: pd.Series,
    cost_bps: float = 20.0
) -> Dict:
    """
    在回测结果上叠加市场对冲仓位

    Args:
        backtest_result: BacktestEngine.run() 的结果 (需含 effective_weights)
        df_beta: rolling_stock_beta() 的结果 (月末日期 × 股票, 未滞后)
        market_return: 市场基准月收益率
        cost_bps: 调整对冲仓位的交易成本 (基点), 与股票仓位同一口径

    Returns:
        对冲后的回测结果, 键与引擎结果一致 (nav / nav_no_cost / returns / returns_no_cost /
        turnover / cost_series), 另有:
        - hedge_ratio: 每期的对冲仓位 (= -组合Beta)
        - portfolio_beta: 每期对冲前的组合 Beta (事前估计)
        只包含能算出组合 Beta 的那些月份 (样本最开头 Beta 数据不够的月份会被去掉)。
    """
    weights = backtest_result['effective_weights']
    # 第 t 月用 t-1 月末已知的 Beta: 滞后统一由时间对齐器完成
    beta_lagged = TimeAligner().lag_to_return_dates(df_beta, weights.index)
    book_beta = portfolio_beta(weights, beta_lagged)

    dates = book_beta.dropna().index.intersection(market_return.dropna().index)
    if len(dates) == 0:
        raise ValueError("没有任何一期能算出组合Beta, 无法对冲 (Beta数据或市场收益缺失)")
    if not weights.index[weights.index >= dates[0]].equals(dates):
        raise ValueError("对冲样本中间出现了算不出组合Beta或缺少市场收益的月份")
    dropped = len(weights.index) - len(dates)
    if dropped:
        logger.info(f"Beta对冲: 样本开头 {dropped} 期没有足够的Beta数据, 对冲后的结果从 {dates[0].date()} 开始")

    book_beta = book_beta.loc[dates]
    hedge_ratio = -book_beta
    hedge_return = hedge_ratio * market_return.loc[dates]

    # 对冲仓位的换手率: 与股票仓位同一口径 0.5 × Σ|Δw|, 建仓前的仓位为 0
    hedge_turnover = 0.5 * hedge_ratio.diff().abs()
    hedge_turnover.iloc[0] = 0.5 * abs(hedge_ratio.iloc[0])
    hedge_cost = hedge_turnover * cost_bps / 10000

    returns_no_cost = backtest_result['returns_no_cost'].loc[dates] + hedge_return
    returns = backtest_result['returns'].loc[dates] + hedge_return - hedge_cost

    return {
        'nav': INITIAL_NAV * (1 + returns).cumprod(),
        'nav_no_cost': INITIAL_NAV * (1 + returns_no_cost).cumprod(),
        'returns': returns,
        'returns_no_cost': returns_no_cost,
        'turnover': backtest_result['turnover'].loc[dates] + hedge_turnover,
        'cost_series': backtest_result['cost_series'].loc[dates] + hedge_cost,
        'effective_weights': weights.loc[dates],
        'hedge_ratio': hedge_ratio,
        'portfolio_beta': book_beta,
    }


def restrict_to_dates(backtest_result: Dict, dates: pd.Index) -> Dict:
    """
    把未对冲的回测结果截到指定的月份, 净值从 1.0 重新起算

    对冲后的样本可能比原样本短 (开头几个月没有 Beta)。比较"对冲前 vs 对冲后"时,
    两边必须用同一段时间, 否则差别里混进了样本期不同的影响。
    """
    returns = backtest_result['returns'].loc[dates]
    returns_no_cost = backtest_result['returns_no_cost'].loc[dates]
    return {
        'nav': INITIAL_NAV * (1 + returns).cumprod(),
        'nav_no_cost': INITIAL_NAV * (1 + returns_no_cost).cumprod(),
        'returns': returns,
        'returns_no_cost': returns_no_cost,
        'turnover': backtest_result['turnover'].loc[dates],
        'cost_series': backtest_result['cost_series'].loc[dates],
        'effective_weights': backtest_result['effective_weights'].loc[dates],
    }
