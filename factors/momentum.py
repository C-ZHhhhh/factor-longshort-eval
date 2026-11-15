"""
[INPUT]: 价格数据
[OUTPUT]: 动量因子值 (12-1个月动量), 索引t的值只用到t-1月末及之前的价格
[POS]: 动量因子实现

[UPDATE 2026-11-15]:
- 修复方向写反: 原实现为 P_t-12 / P_t-1 - 1 (排序与真实动量完全相反)
- 现为 P_t-1 / P_t-12 - 1, 过去涨得多的股票因子值高

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Optional
from factors.base_factor import BaseFactor
from utils.logger import get_logger

logger = get_logger(__name__)


class MomentumFactor(BaseFactor):
    """动量因子

    定义: (P_t-1m / P_t-12m) - 1
    说明: 过去12个月收益率，跳过最近1个月（避免短期反转效应）
          过去涨得多 → 因子值高 → 做多
    """

    def __init__(self):
        super().__init__(name='Momentum')

    def calculate(
        self,
        df_price: pd.DataFrame,
        df_volume: Optional[pd.DataFrame] = None,
        df_return_daily: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算12-1个月动量因子

        Args:
            df_price: 价格数据 (日期 × 股票)
            df_volume: 未使用
            df_return_daily: 未使用

        Returns:
            动量因子值 (月末日期 × 股票)
        """
        logger.info("开始计算动量因子 (12-1个月)...")

        # 1. 重采样到月末价格
        df_price_monthly = df_price.resample('ME').last()

        # 2. 计算动量: (P_t-1 / P_t-12) - 1
        # P_t-1: 1个月前的价格
        price_t_minus_1 = df_price_monthly.shift(1)
        # P_t-12: 12个月前的价格
        price_t_minus_12 = df_price_monthly.shift(12)

        # 动量 = (P_t-1 / P_t-12) - 1  (近的价格在分子, 远的价格在分母)
        df_momentum = (price_t_minus_1 / price_t_minus_12) - 1

        # 3. 移除前12个月的NaN值（数据不足）
        df_momentum = df_momentum.iloc[12:]

        logger.info(f"动量因子计算完成: {df_momentum.shape[0]} 月 × {df_momentum.shape[1]} 股票")
        logger.info(f"有效数据范围: {df_momentum.index[0]} ~ {df_momentum.index[-1]}")

        return df_momentum
