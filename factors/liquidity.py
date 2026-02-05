"""
[INPUT]: 价格和成交量数据
[OUTPUT]: 流动性因子值
[POS]: 流动性因子实现

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


class LiquidityFactor(BaseFactor):
    """流动性因子

    定义: 平均成交额 (Price × Volume的过去N天平均)
    说明: 成交额越高，流动性越好
    """

    def __init__(self, window_days: int = 63):
        """
        初始化

        Args:
            window_days: 计算平均成交额的窗口(天数), 默认63天(约3个月)
        """
        super().__init__(name='Liquidity')
        self.window_days = window_days

    def calculate(
        self,
        df_price: pd.DataFrame,
        df_volume: Optional[pd.DataFrame] = None,
        df_return_daily: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算流动性因子

        Args:
            df_price: 价格数据 (日期 × 股票)
            df_volume: 成交量数据 (日期 × 股票)
            df_return_daily: 未使用

        Returns:
            流动性因子值 (月末日期 × 股票)
        """
        logger.info(f"开始计算流动性因子 ({self.window_days}天平均成交额)...")

        if df_volume is None:
            raise ValueError("流动性因子需要成交量数据")

        # 1. 计算日成交额 = 价格 × 成交量
        df_dollar_volume = df_price * df_volume

        # 2. 计算滚动平均成交额
        df_avg_dollar_volume = df_dollar_volume.rolling(
            window=self.window_days,
            min_periods=int(self.window_days * 0.8)
        ).mean()

        # 3. 对成交额取对数（降低偏度）
        df_liquidity = np.log(df_avg_dollar_volume + 1)

        # 4. 重采样到月末
        df_liquidity_monthly = df_liquidity.resample('ME').last()

        # 5. 移除前几个月的NaN值
        df_liquidity_monthly = df_liquidity_monthly.dropna(how='all')

        logger.info(f"流动性因子计算完成: {df_liquidity_monthly.shape[0]} 月 × {df_liquidity_monthly.shape[1]} 股票")
        logger.info(f"有效数据范围: {df_liquidity_monthly.index[0]} ~ {df_liquidity_monthly.index[-1]}")

        return df_liquidity_monthly
