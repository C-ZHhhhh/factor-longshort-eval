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

[UPDATE 2026-11-15]:
- 修复同一只股票同时出现在多头和空头名单: 原实现多空两侧各自独立决策,
  被最小持有期锁住的多头掉到空头进入区时会被同时做空(空头标记覆盖多头)。
- 现在两侧一起决策: 一侧仍在持有的股票, 另一侧不允许新开仓, 等它退出后才能反向进入。
- 多空两侧共用同一套 保留/进入 逻辑(_entry_and_exit_zones/_retain/_enter), 不再复制两份。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Set, Tuple
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
        if not 0 < entry_quantile <= 0.5:
            # 超过50%时多头进入区和空头进入区会重叠, 同一只股票会被同时做多和做空
            raise ValueError(f"entry_quantile必须在(0, 0.5]之间, 当前为{entry_quantile}")

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

            # 多头和空头一起决策（保证同一只股票不会同时在两侧）
            long_holdings, short_holdings = self._build_sides(valid_values)

            overlap = set(long_holdings) & set(short_holdings)
            if overlap:
                raise RuntimeError(
                    f"日期 {date}: {len(overlap)} 只股票同时在多头和空头名单中: "
                    f"{sorted(overlap)[:5]}"
                )

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

    def _build_sides(self, valid_values: pd.Series) -> Tuple[List[str], List[str]]:
        """
        同时构建多头和空头持仓（带进出阈值和最小持有期约束）

        逻辑:
        1. 两侧各自决定上期持仓中哪些继续持有（仍在退出阈值内, 或未满最小持有期）
        2. 两侧各自从进入候选中新开仓, 但跳过另一侧仍在持有的股票
           （否则被最小持有期锁住的多头会被同时做空）

        Args:
            valid_values: 当期有效因子值（已去除缺失）

        Returns:
            (多头持仓列表, 空头持仓列表), 两者不相交
        """
        long_entry, long_exit_zone = self._entry_and_exit_zones(valid_values, 'long')
        short_entry, short_exit_zone = self._entry_and_exit_zones(valid_values, 'short')

        # 1. 上期持仓中继续持有的部分（第一期没有上期持仓）
        retained_long = self._retain(
            self.prev_holdings_long or [], self.holding_periods_long, long_exit_zone
        )
        retained_short = self._retain(
            self.prev_holdings_short or [], self.holding_periods_short, short_exit_zone
        )

        # 2. 新开仓: 另一侧仍持有的股票不允许反向进入
        long_holdings = self._enter(
            retained_long, long_entry, set(retained_short), self.holding_periods_long
        )
        short_holdings = self._enter(
            retained_short, short_entry, set(retained_long), self.holding_periods_short
        )

        return long_holdings, short_holdings

    def _entry_and_exit_zones(
        self,
        valid_values: pd.Series,
        side: str
    ) -> Tuple[List[str], Set[str]]:
        """
        计算某一侧的进入候选和退出阈值区

        Args:
            valid_values: 当期有效因子值
            side: 'long' 或 'short'

        Returns:
            (进入候选列表, 退出阈值内的股票集合)
            例如 entry=25%, exit=30%: 排名进入前25%才买入, 掉出前30%才算离开
        """
        sorted_values = valid_values.sort_values(ascending=False)
        n_stocks = len(sorted_values)
        entry_rank = int(n_stocks * self.entry_quantile)
        exit_rank = int(n_stocks * self.exit_quantile)

        # long_top=True时: 多头取因子值高的一端, 空头取低的一端; 否则反过来
        take_top = (side == 'long') == self.long_top
        if take_top:
            entry_candidates = sorted_values.head(entry_rank).index.tolist()
            exit_zone = set(sorted_values.head(exit_rank).index)
        else:
            entry_candidates = sorted_values.tail(entry_rank).index.tolist()
            exit_zone = set(sorted_values.tail(exit_rank).index)

        return entry_candidates, exit_zone

    def _retain(
        self,
        prev_holdings: List[str],
        holding_periods: Dict[str, int],
        exit_zone: Set[str]
    ) -> List[str]:
        """
        决定上期持仓中哪些继续持有, 并更新持有期

        继续持有的条件（满足其一）:
        - 仍在退出阈值内
        - 未满最小持有期（强制持有）

        Args:
            prev_holdings: 上期持仓
            holding_periods: 持有期字典 {ticker: periods}, 会被原地更新
            exit_zone: 退出阈值内的股票集合

        Returns:
            继续持有的股票列表
        """
        retained = []
        for ticker in prev_holdings:
            held_periods = holding_periods.get(ticker, 0)
            if ticker in exit_zone or held_periods < self.min_holding_periods:
                retained.append(ticker)
                holding_periods[ticker] = held_periods + 1
            else:
                # 掉出阈值且已满最小持有期: 退出
                holding_periods.pop(ticker, None)
        return retained

    def _enter(
        self,
        retained: List[str],
        entry_candidates: List[str],
        blocked: Set[str],
        holding_periods: Dict[str, int]
    ) -> List[str]:
        """
        在继续持有的基础上加入新开仓的股票

        Args:
            retained: 本侧继续持有的股票
            entry_candidates: 本侧进入候选
            blocked: 另一侧仍在持有的股票（不允许反向进入）
            holding_periods: 本侧持有期字典, 会被原地更新

        Returns:
            本侧本期完整持仓列表
        """
        holdings = list(retained)
        held = set(retained)
        for ticker in entry_candidates:
            if ticker in held or ticker in blocked:
                continue
            holdings.append(ticker)
            holding_periods[ticker] = 1  # 初始化持有期为1
        return holdings

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
