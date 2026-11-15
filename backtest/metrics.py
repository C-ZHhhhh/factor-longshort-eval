"""
[INPUT]: 净值曲线、收益率序列
[OUTPUT]: 绩效指标
[POS]: 绩效指标计算模块

[UPDATE 2026-11-15]:
- 修复总收益/年化收益漏算第一期: 原实现用 nav[-1]/nav[0]-1, 但回测引擎的nav[0]
  已经是第一期结束后的净值, 第一期的收益被丢掉而期数仍按len(nav)算。
- 现在总收益和年化收益统一从收益率序列计算: prod(1+r)-1, 期数=len(returns)。
  total_return/annual_return/calmar_ratio 的入参相应从nav改为returns。
- 修复回撤没把初始净值当作高点: 第一期就亏损时, 这段亏损原来不计入回撤。
  新增模块级函数 drawdown_series(nav, initial_nav), 全系统的回撤都从这里算。

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

INITIAL_NAV = 1.0  # 回测初始净值, 与BacktestEngine的initial_nav默认值一致


def drawdown_series(nav: pd.Series, initial_nav: float = INITIAL_NAV) -> pd.Series:
    """
    回撤序列: 当前净值相对历史最高净值的跌幅 (<=0)

    历史最高净值要把初始净值算进去。回测引擎的nav[0]是第一期结束后的净值,
    如果第一期就亏了, 只用nav.cummax()会把nav[0]当成起点, 漏掉这段回撤。

    Args:
        nav: 净值序列 (第一个值是第一期结束后的净值)
        initial_nav: 初始净值

    Returns:
        回撤序列, 与nav同索引
    """
    running_peak = nav.cummax().clip(lower=initial_nav)
    return (nav - running_peak) / running_peak


class PerformanceMetrics:
    """绩效指标计算器

    计算各种回测绩效指标
    """

    def __init__(self, periods_per_year: int = 12):
        """
        初始化

        Args:
            periods_per_year: 每年期数（月度=12，日度=252）
        """
        self.periods_per_year = periods_per_year
        logger.info(f"初始化绩效指标计算器: periods_per_year={periods_per_year}")

    def calculate_all_metrics(
        self,
        returns: pd.Series,
        nav: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """
        计算所有绩效指标

        Args:
            returns: 收益率序列
            nav: 净值序列（可选，如无则从returns计算）

        Returns:
            指标字典
        """
        if nav is None:
            nav = (1 + returns).cumprod()

        metrics = {
            # 收益指标
            'total_return': self.total_return(returns),
            'annual_return': self.annual_return(returns),
            'monthly_return': returns.mean(),

            # 风险指标
            'annual_volatility': self.annual_volatility(returns),
            'max_drawdown': self.max_drawdown(nav),

            # 风险调整收益
            'sharpe_ratio': self.sharpe_ratio(returns),
            'calmar_ratio': self.calmar_ratio(returns, nav),
            'sortino_ratio': self.sortino_ratio(returns),

            # 其他统计
            'win_rate': self.win_rate(returns),
            'avg_win': self.avg_win(returns),
            'avg_loss': self.avg_loss(returns),
            'profit_factor': self.profit_factor(returns),
        }

        return metrics

    def total_return(self, returns: pd.Series) -> float:
        """
        总收益率 = prod(1 + r_t) - 1

        从收益率序列计算, 包含第一期的收益。
        （不能用 nav[-1]/nav[0]-1: nav[0]是第一期结束后的净值, 会漏掉第一期）
        """
        if len(returns) == 0:
            return 0.0
        return float((1 + returns).prod() - 1)

    def annual_return(self, returns: pd.Series) -> float:
        """年化收益率（几何）: (1 + 总收益) ^ (每年期数 / 期数) - 1"""
        n_periods = len(returns)
        if n_periods == 0:
            return 0.0
        total_return = self.total_return(returns)
        n_years = n_periods / self.periods_per_year
        annual_return = (1 + total_return) ** (1 / n_years) - 1
        return annual_return

    def annual_volatility(self, returns: pd.Series) -> float:
        """年化波动率"""
        return returns.std() * np.sqrt(self.periods_per_year)

    def sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: float = 0.0
    ) -> float:
        """
        夏普比率

        Sharpe = (E[R] - Rf) / σ[R]
        """
        excess_returns = returns - risk_free_rate / self.periods_per_year
        if excess_returns.std() == 0:
            return 0.0
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(self.periods_per_year)
        return sharpe

    def max_drawdown(self, nav: pd.Series) -> float:
        """
        最大回撤

        MaxDD = max(1 - nav_t / nav_peak), nav_peak包含初始净值
        """
        return drawdown_series(nav).min()

    def calmar_ratio(self, returns: pd.Series, nav: Optional[pd.Series] = None) -> float:
        """
        卡玛比率

        Calmar = 年化收益 / |最大回撤|
        """
        if nav is None:
            nav = (1 + returns).cumprod()
        annual_ret = self.annual_return(returns)
        max_dd = abs(self.max_drawdown(nav))
        if max_dd == 0:
            return 0.0
        return annual_ret / max_dd

    def sortino_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: float = 0.0
    ) -> float:
        """
        索提诺比率

        Sortino = (E[R] - Rf) / σ_downside[R]
        只考虑下行波动率
        """
        excess_returns = returns - risk_free_rate / self.periods_per_year
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        sortino = excess_returns.mean() / downside_returns.std() * np.sqrt(self.periods_per_year)
        return sortino

    def win_rate(self, returns: pd.Series) -> float:
        """胜率（正收益期数占比）"""
        return (returns > 0).sum() / len(returns)

    def avg_win(self, returns: pd.Series) -> float:
        """平均盈利"""
        wins = returns[returns > 0]
        return wins.mean() if len(wins) > 0 else 0.0

    def avg_loss(self, returns: pd.Series) -> float:
        """平均亏损"""
        losses = returns[returns < 0]
        return losses.mean() if len(losses) > 0 else 0.0

    def profit_factor(self, returns: pd.Series) -> float:
        """
        盈亏比

        Profit Factor = 总盈利 / |总亏损|
        """
        total_wins = returns[returns > 0].sum()
        total_losses = abs(returns[returns < 0].sum())

        if total_losses == 0:
            return 0.0

        return total_wins / total_losses

    def print_metrics(self, metrics: Dict[str, float]):
        """打印指标"""
        logger.info("="*70)
        logger.info("绩效指标")
        logger.info("="*70)

        logger.info("\n收益指标:")
        logger.info(f"  总收益率:   {metrics['total_return']:>10.2%}")
        logger.info(f"  年化收益:   {metrics['annual_return']:>10.2%}")
        logger.info(f"  月均收益:   {metrics['monthly_return']:>10.2%}")

        logger.info("\n风险指标:")
        logger.info(f"  年化波动:   {metrics['annual_volatility']:>10.2%}")
        logger.info(f"  最大回撤:   {metrics['max_drawdown']:>10.2%}")

        logger.info("\n风险调整收益:")
        logger.info(f"  Sharpe:     {metrics['sharpe_ratio']:>10.2f}")
        logger.info(f"  Calmar:     {metrics['calmar_ratio']:>10.2f}")
        logger.info(f"  Sortino:    {metrics['sortino_ratio']:>10.2f}")

        logger.info("\n交易统计:")
        logger.info(f"  胜率:       {metrics['win_rate']:>10.2%}")
        logger.info(f"  平均盈利:   {metrics['avg_win']:>10.2%}")
        logger.info(f"  平均亏损:   {metrics['avg_loss']:>10.2%}")
        logger.info(f"  盈亏比:     {metrics['profit_factor']:>10.2f}")

        logger.info("="*70)
