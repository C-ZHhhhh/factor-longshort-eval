"""
[INPUT]: 日收益率数据
[OUTPUT]: 低波动率因子值
[POS]: 低波动率因子实现

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


class LowVolatilityFactor(BaseFactor):
    """低波动率因子

    定义: -σ(日收益, 过去3个月)
    说明: 过去3个月日收益率标准差的负值（低波动率股票表现更好）
    """

    def __init__(self, window_months: int = 3):
        """
        初始化

        Args:
            window_months: 计算波动率的窗口(月数), 默认3个月
        """
        super().__init__(name='LowVolatility')
        self.window_months = window_months
        # 假设1个月约21个交易日
        self.window_days = window_months * 21

    def calculate(
        self,
        df_price: pd.DataFrame,
        df_volume: Optional[pd.DataFrame] = None,
        df_return_daily: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算低波动率因子

        Args:
            df_price: 价格数据 (日期 × 股票)
            df_volume: 未使用
            df_return_daily: 日收益率数据 (日期 × 股票), 可选

        Returns:
            低波因子值 (月末日期 × 股票)
        """
        logger.info(f"开始计算低波动率因子 ({self.window_months}个月)...")

        # 1. 计算日收益率（如果未提供）
        if df_return_daily is None:
            df_return_daily = df_price.pct_change()
            logger.info("从价格数据计算日收益率")

        # 2. 计算滚动标准差（过去N个交易日）
        df_volatility = df_return_daily.rolling(window=self.window_days, min_periods=int(self.window_days * 0.8)).std()

        # 3. 重采样到月末（取月末的波动率值）
        df_volatility_monthly = df_volatility.resample('ME').last()

        # 4. 低波因子 = -波动率 (负值，因为我们偏好低波动率)
        df_low_vol = -df_volatility_monthly

        # 5. 移除前几个月的NaN值
        df_low_vol = df_low_vol.dropna(how='all')

        logger.info(f"低波因子计算完成: {df_low_vol.shape[0]} 月 × {df_low_vol.shape[1]} 股票")
        logger.info(f"有效数据范围: {df_low_vol.index[0]} ~ {df_low_vol.index[-1]}")

        return df_low_vol
