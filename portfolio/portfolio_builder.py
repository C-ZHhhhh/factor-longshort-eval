"""
[INPUT]: 标准化后的因子值
[OUTPUT]: 持仓标记 (多头+1, 空头-1, 不持有0)
[POS]: 组合构建器 - 带进出阈值和最小持有期约束的排序选股模块

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md

[UPDATE 2026-02-03]:
- 添加进入/退出阈值逻辑: 买入Top 25%, 卖出需掉出Top 30%
- 添加最小持有期约束: 新进股票必须持有N期才能卖出
- build方法从无状态改为有状态(需要记录上期持仓和持有期)
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict
from utils.logger import get_logger

logger = get_logger(__name__)


class PortfolioBuilder:
    """组合构建器（带进出阈值和最小持有期约束）

    关键特性:
    1. 进入阈值: 排名 <= entry_quantile (如Top 25%) 才买入
    2. 退出阈值: 排名 > exit_quantile (如Top 30%) 才卖出
    3. 最小持有期: 新进股票必须持有 min_holding_periods 期才允许退出

    这种机制可以显著降低换手率
    """

    def __init__(
        self,
        entry_quantile: float = 0.25,      # 进入阈值: Top 25%
        exit_quantile: float = 0.30,       # 退出阈值: Top 30%
        min_holding_periods: int = 6,      # 最小持有期(月数)
        long_top: bool = True
    ):
        """
        初始化

        Args:
            entry_quantile: 进入阈值, 默认0.25 (买入Top 25%)
            exit_quantile: 退出阈值, 默认0.30 (掉出Top 30%才卖)
            min_holding_periods: 最小持有期(月数), 默认6个月
            long_top: 是否做多因子值高的股票, 默认True
        """
        self.entry_quantile = entry_quantile
        self.exit_quantile = exit_quantile
        self.min_holding_periods = min_holding_periods
        self.long_top = long_top

        # 状态变量（有状态构建器）
        self.prev_holdings_long = None   # 上期多头持仓
        self.prev_holdings_short = None  # 上期空头持仓
        self.holding_periods_long = {}   # 多头持有期: {ticker: periods}
        self.holding_periods_short = {}  # 空头持有期: {ticker: periods}

        logger.info(
            f"初始化组合构建器: entry={entry_quantile:.0%}, "
            f"exit={exit_quantile:.0%}, min_holding={min_holding_periods}月, "
            f"long_top={long_top}"
        )

    def build(self, df_factor: pd.DataFrame, neutralize: bool = True) -> pd.DataFrame:
        """
        构建组合持仓并转换为中性化权重

        Args:
            df_factor: 因子值 (月末日期 × 股票)
            neutralize: 是否进行中性化，默认True

        Returns:
            权重矩阵 (月末日期 × 股票)
            - 如果neutralize=True: 多头权重和=+1, 空头权重和=-1, 总和≈0
            - 如果neutralize=False: 返回持仓标记 (+1/-1/0)
        """
        logger.info(f"开始构建组合(带约束): {df_factor.shape}")

        df_holdings = pd.DataFrame(0, index=df_factor.index, columns=df_factor.columns)

        # 重置状态（每次调用build重新开始）
        self.prev_holdings_long = None
        self.prev_holdings_short = None
        self.holding_periods_long = {}
        self.holding_periods_short = {}

        # 按时间顺序逐月构建
        for i, date in enumerate(df_factor.index):
            factor_values = df_factor.loc[date]

            # 移除缺失值
            valid_values = factor_values.dropna()

            if len(valid_values) == 0:
                logger.warning(f"日期 {date}: 没有有效因子值")
                # 如果没有有效数据，继续持有上期持仓
                if self.prev_holdings_long is not None:
                    df_holdings.loc[date, self.prev_holdings_long] = 1
                if self.prev_holdings_short is not None:
                    df_holdings.loc[date, self.prev_holdings_short] = -1
                continue

            # 对多头和空头分别处理
            long_holdings = self._build_long_side(date, valid_values, i)
            short_holdings = self._build_short_side(date, valid_values, i)

            # 更新持仓标记
            df_holdings.loc[date, long_holdings] = 1
            df_holdings.loc[date, short_holdings] = -1

            # 更新上期持仓
            self.prev_holdings_long = long_holdings
            self.prev_holdings_short = short_holdings

            # 定期日志
            if (i + 1) % 20 == 0 or i == 0:
                logger.info(
                    f"  [{i+1}/{len(df_factor)}] {date.strftime('%Y-%m')}: "
                    f"多头{len(long_holdings)}只, 空头{len(short_holdings)}只"
                )

        # 统计
        total_positions = (df_holdings != 0).sum().sum()
        long_positions = (df_holdings == 1).sum().sum()
        short_positions = (df_holdings == -1).sum().sum()

        logger.info(f"组合构建完成:")
        logger.info(f"  总持仓数: {total_positions}")
        logger.info(f"  多头持仓: {long_positions}")
        logger.info(f"  空头持仓: {short_positions}")
        logger.info(f"  每月平均持仓: {total_positions / len(df_factor):.1f}")

        # 如果需要中性化，将持仓转换为中性化权重
        if neutralize:
            df_weights = self._convert_to_weights(df_holdings)
            return df_weights
        else:
            return df_holdings

    def _build_long_side(
        self,
        date: pd.Timestamp,
        valid_values: pd.Series,
        period_index: int
    ) -> list:
        """
        构建多头持仓（带进出阈值和最小持有期约束）

        逻辑:
        1. 计算进入/退出阈值
        2. 判断每只股票: 新进/保持/退出
        3. 更新持有期

        Args:
            date: 当前日期
            valid_values: 当前因子值
            period_index: 当前是第几期

        Returns:
            多头持仓股票列表
        """
        # 排序
        sorted_values = valid_values.sort_values(ascending=False)

        # 计算分位数阈值
        n_stocks = len(sorted_values)

        if self.long_top:
            # 做多高因子值: Top 25%进入, Top 30%退出
            entry_rank = int(n_stocks * self.entry_quantile)
            exit_rank = int(n_stocks * self.exit_quantile)

            # 候选股票（排名靠前）
            entry_candidates = sorted_values.head(entry_rank).index.tolist()
            exit_threshold_stocks = sorted_values.head(exit_rank).index.tolist()
        else:
            # 做多低因子值: Bottom 25%进入, Bottom 30%退出
            entry_rank = int(n_stocks * self.entry_quantile)
            exit_rank = int(n_stocks * self.exit_quantile)

            entry_candidates = sorted_values.tail(entry_rank).index.tolist()
            exit_threshold_stocks = sorted_values.tail(exit_rank).index.tolist()

        # 第一期: 直接买入候选股票
        if self.prev_holdings_long is None:
            new_holdings = entry_candidates
            # 初始化持有期
            for ticker in new_holdings:
                self.holding_periods_long[ticker] = 1
            return new_holdings

        # 非第一期: 应用进出阈值和最小持有期约束
        new_holdings = []

        # 1. 遍历上期持仓，判断是否继续持有
        for ticker in self.prev_holdings_long:
            # 检查是否仍在退出阈值内
            still_in_exit_zone = ticker in exit_threshold_stocks

            # 检查持有期
            current_holding_period = self.holding_periods_long.get(ticker, 0)

            # 决策: 是否继续持有
            if still_in_exit_zone and current_holding_period < self.min_holding_periods:
                # 继续持有: 仍在阈值内 且 未满最小持有期
                new_holdings.append(ticker)
                self.holding_periods_long[ticker] = current_holding_period + 1
            elif not still_in_exit_zone and current_holding_period < self.min_holding_periods:
                # 已掉出阈值但未满最小持有期: 继续持有（强制）
                new_holdings.append(ticker)
                self.holding_periods_long[ticker] = current_holding_period + 1
            elif still_in_exit_zone and current_holding_period >= self.min_holding_periods:
                # 仍在阈值内且已满最小持有期: 继续持有
                new_holdings.append(ticker)
                self.holding_periods_long[ticker] = current_holding_period + 1
            else:
                # 掉出阈值且已满最小持有期: 退出
                # 从持有期字典中删除
                if ticker in self.holding_periods_long:
                    del self.holding_periods_long[ticker]

        # 2. 遍历候选新股票，判断是否买入
        for ticker in entry_candidates:
            if ticker not in new_holdings:
                # 新买入: 排名在进入阈值内 且 当前未持有
                new_holdings.append(ticker)
                self.holding_periods_long[ticker] = 1  # 初始化持有期为1

        return new_holdings

    def _build_short_side(
        self,
        date: pd.Timestamp,
        valid_values: pd.Series,
        period_index: int
    ) -> list:
        """
        构建空头持仓（带进出阈值和最小持有期约束）

        逻辑与多头类似，但方向相反

        Args:
            date: 当前日期
            valid_values: 当前因子值
            period_index: 当前是第几期

        Returns:
            空头持仓股票列表
        """
        # 排序
        sorted_values = valid_values.sort_values(ascending=False)

        # 计算分位数阈值
        n_stocks = len(sorted_values)

        if self.long_top:
            # 做空低因子值: Bottom 25%进入, Bottom 30%退出
            entry_rank = int(n_stocks * self.entry_quantile)
            exit_rank = int(n_stocks * self.exit_quantile)

            entry_candidates = sorted_values.tail(entry_rank).index.tolist()
            exit_threshold_stocks = sorted_values.tail(exit_rank).index.tolist()
        else:
            # 做空高因子值: Top 25%进入, Top 30%退出
            entry_rank = int(n_stocks * self.entry_quantile)
            exit_rank = int(n_stocks * self.exit_quantile)

            entry_candidates = sorted_values.head(entry_rank).index.tolist()
            exit_threshold_stocks = sorted_values.head(exit_rank).index.tolist()

        # 第一期: 直接买入候选股票
        if self.prev_holdings_short is None:
            new_holdings = entry_candidates
            # 初始化持有期
            for ticker in new_holdings:
                self.holding_periods_short[ticker] = 1
            return new_holdings

        # 非第一期: 应用进出阈值和最小持有期约束
        new_holdings = []

        # 1. 遍历上期持仓，判断是否继续持有
        for ticker in self.prev_holdings_short:
            # 检查是否仍在退出阈值内
            still_in_exit_zone = ticker in exit_threshold_stocks

            # 检查持有期
            current_holding_period = self.holding_periods_short.get(ticker, 0)

            # 决策: 是否继续持有
            if still_in_exit_zone and current_holding_period < self.min_holding_periods:
                # 继续持有
                new_holdings.append(ticker)
                self.holding_periods_short[ticker] = current_holding_period + 1
            elif not still_in_exit_zone and current_holding_period < self.min_holding_periods:
                # 已掉出阈值但未满最小持有期: 继续持有（强制）
                new_holdings.append(ticker)
                self.holding_periods_short[ticker] = current_holding_period + 1
            elif still_in_exit_zone and current_holding_period >= self.min_holding_periods:
                # 仍在阈值内且已满最小持有期: 继续持有
                new_holdings.append(ticker)
                self.holding_periods_short[ticker] = current_holding_period + 1
            else:
                # 掉出阈值且已满最小持有期: 退出
                if ticker in self.holding_periods_short:
                    del self.holding_periods_short[ticker]

        # 2. 遍历候选新股票，判断是否买入
        for ticker in entry_candidates:
            if ticker not in new_holdings:
                # 新买入
                new_holdings.append(ticker)
                self.holding_periods_short[ticker] = 1

        return new_holdings

    def _convert_to_weights(self, df_holdings: pd.DataFrame) -> pd.DataFrame:
        """
        将持仓标记转换为中性化权重

        确保每期:
        - 多头权重和 = +1
        - 空头权重和 = -1
        - 总权重和 ≈ 0

        Args:
            df_holdings: 持仓标记 (+1/-1/0)

        Returns:
            中性化后的权重矩阵
        """
        from portfolio.neutralization import Neutralizer

        logger.info("将持仓转换为中性化权重...")

        # 先转换为等权重
        df_weights = df_holdings.copy().astype(float)

        for date in df_holdings.index:
            holdings = df_holdings.loc[date]

            # 多头: 等权分配，总和=1
            long_mask = holdings == 1
            n_long = long_mask.sum()
            if n_long > 0:
                df_weights.loc[date, long_mask] = 1.0 / n_long

            # 空头: 等权分配，总和=-1
            short_mask = holdings == -1
            n_short = short_mask.sum()
            if n_short > 0:
                df_weights.loc[date, short_mask] = -1.0 / n_short

        # 使用Neutralizer进行中性化（确保数值精度）
        neutralizer = Neutralizer()
        df_weights_neutral = neutralizer.market_neutral(df_weights)

        logger.info("持仓转换为权重完成")
        return df_weights_neutral

    def get_long_short_counts(self, df_holdings: pd.DataFrame) -> pd.DataFrame:
        """
        获取每月多空持仓数量

        Args:
            df_holdings: 持仓标记

        Returns:
            DataFrame with columns ['long_count', 'short_count', 'total_count']
        """
        long_count = (df_holdings == 1).sum(axis=1)
        short_count = (df_holdings == -1).sum(axis=1)
        total_count = (df_holdings != 0).sum(axis=1)

        return pd.DataFrame({
            'long_count': long_count,
            'short_count': short_count,
            'total_count': total_count
        })
