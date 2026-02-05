"""
[INPUT]: 前后两期权重
[OUTPUT]: 换手率
[POS]: 换手率计算模块

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class Rebalancer:
    """换手率计算器

    计算组合调仓的换手率
    """

    def __init__(self):
        logger.info("初始化换手率计算器")

    def calculate_turnover(
        self,
        df_weights: pd.DataFrame
    ) -> pd.Series:
        """
        计算换手率序列

        换手率定义: TO_t = 0.5 × Σ|w_t - w_{t-1}|

        Args:
            df_weights: 权重序列 (月末日期 × 股票)

        Returns:
            换手率序列 (月末日期)
        """
        logger.info("开始计算换手率...")

        turnover_series = pd.Series(0.0, index=df_weights.index)

        for i in range(1, len(df_weights)):
            date_prev = df_weights.index[i - 1]
            date_curr = df_weights.index[i]

            weights_prev = df_weights.loc[date_prev]
            weights_curr = df_weights.loc[date_curr]

            # 对齐股票列表（处理新增/退出的股票）
            all_tickers = weights_prev.index.union(weights_curr.index)
            w_prev = weights_prev.reindex(all_tickers, fill_value=0.0)
            w_curr = weights_curr.reindex(all_tickers, fill_value=0.0)

            # 计算换手率: TO = 0.5 × Σ|Δw|
            turnover = 0.5 * (w_curr - w_prev).abs().sum()
            turnover_series.loc[date_curr] = turnover

        # 统计
        avg_turnover = turnover_series[turnover_series > 0].mean()
        logger.info(f"换手率计算完成:")
        logger.info(f"  平均换手率: {avg_turnover:.2%}")
        logger.info(f"  最大换手率: {turnover_series.max():.2%}")
        logger.info(f"  最小换手率: {turnover_series[turnover_series > 0].min():.2%}")

        return turnover_series

    def calculate_pairwise_turnover(
        self,
        weights_old: pd.Series,
        weights_new: pd.Series
    ) -> float:
        """
        计算两个权重向量之间的换手率

        Args:
            weights_old: 旧权重 (股票)
            weights_new: 新权重 (股票)

        Returns:
            换手率标量
        """
        # 对齐股票列表
        all_tickers = weights_old.index.union(weights_new.index)
        w_old = weights_old.reindex(all_tickers, fill_value=0.0)
        w_new = weights_new.reindex(all_tickers, fill_value=0.0)

        # TO = 0.5 × Σ|Δw|
        turnover = 0.5 * (w_new - w_old).abs().sum()

        return turnover

    def get_turnover_stats(self, turnover_series: pd.Series) -> dict:
        """
        获取换手率统计信息

        Args:
            turnover_series: 换手率序列

        Returns:
            统计字典
        """
        valid_turnover = turnover_series[turnover_series > 0]

        stats = {
            'mean': valid_turnover.mean(),
            'median': valid_turnover.median(),
            'std': valid_turnover.std(),
            'min': valid_turnover.min(),
            'max': valid_turnover.max(),
            'q25': valid_turnover.quantile(0.25),
            'q75': valid_turnover.quantile(0.75),
        }

        return stats

    def decompose_turnover(
        self,
        weights_old: pd.Series,
        weights_new: pd.Series
    ) -> dict:
        """
        分解换手率来源

        Args:
            weights_old: 旧权重
            weights_new: 新权重

        Returns:
            分解字典:
            - 'total': 总换手率
            - 'entry': 新进入股票贡献
            - 'exit': 退出股票贡献
            - 'adjust': 权重调整贡献
        """
        # 对齐
        all_tickers = weights_old.index.union(weights_new.index)
        w_old = weights_old.reindex(all_tickers, fill_value=0.0)
        w_new = weights_new.reindex(all_tickers, fill_value=0.0)

        # 分类
        entry_mask = (w_old == 0) & (w_new != 0)  # 新进入
        exit_mask = (w_old != 0) & (w_new == 0)   # 退出
        adjust_mask = (w_old != 0) & (w_new != 0)  # 权重调整

        entry_turnover = 0.5 * w_new[entry_mask].abs().sum()
        exit_turnover = 0.5 * w_old[exit_mask].abs().sum()
        adjust_turnover = 0.5 * (w_new[adjust_mask] - w_old[adjust_mask]).abs().sum()

        total_turnover = entry_turnover + exit_turnover + adjust_turnover

        return {
            'total': total_turnover,
            'entry': entry_turnover,
            'exit': exit_turnover,
            'adjust': adjust_turnover,
        }
