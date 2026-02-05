"""
[INPUT]: 价格数据或月收益率数据
[OUTPUT]: 短期反转因子值
[POS]: 短期反转因子实现

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


class ReversalFactor(BaseFactor):
    """短期反转因子

    定义: -R_t-1m
    说明: 上个月收益率的负值（捕捉短期均值回归效应）
    """

    def __init__(self):
        super().__init__(name='Reversal')

    def calculate(
        self,
        df_price: pd.DataFrame,
        df_volume: Optional[pd.DataFrame] = None,
        df_return_daily: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算1个月反转因子

        Args:
            df_price: 价格数据 (日期 × 股票)
            df_volume: 未使用
            df_return_daily: 未使用

        Returns:
            反转因子值 (月末日期 × 股票)
        """
        logger.info("开始计算短期反转因子 (1个月)...")

        # 1. 重采样到月末价格
        df_price_monthly = df_price.resample('ME').last()

        # 2. 计算月收益率
        df_return_monthly = df_price_monthly.pct_change()

        # 3. 反转因子 = -R_t-1 (上个月收益率的负值)
        df_reversal = -df_return_monthly.shift(1)

        # 4. 移除第一个月的NaN值
        df_reversal = df_reversal.iloc[1:]

        logger.info(f"反转因子计算完成: {df_reversal.shape[0]} 月 × {df_reversal.shape[1]} 股票")
        logger.info(f"有效数据范围: {df_reversal.index[0]} ~ {df_reversal.index[-1]}")

        return df_reversal
