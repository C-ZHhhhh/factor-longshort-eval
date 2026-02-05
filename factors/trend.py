"""
[INPUT]: 价格数据
[OUTPUT]: 趋势因子值
[POS]: 趋势因子实现

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


class TrendFactor(BaseFactor):
    """趋势因子

    定义: P_t / MA200(P_t) - 1
    说明: 当前价格相对于200日移动平均线的偏离度
    """

    def __init__(self, window: int = 200):
        """
        初始化

        Args:
            window: 移动平均窗口(天数), 默认200天
        """
        super().__init__(name='Trend')
        self.window = window

    def calculate(
        self,
        df_price: pd.DataFrame,
        df_volume: Optional[pd.DataFrame] = None,
        df_return_daily: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算趋势因子

        Args:
            df_price: 价格数据 (日期 × 股票)
            df_volume: 未使用
            df_return_daily: 未使用

        Returns:
            趋势因子值 (月末日期 × 股票)
        """
        logger.info(f"开始计算趋势因子 ({self.window}日均线)...")

        # 1. 计算移动平均线
        df_ma = df_price.rolling(window=self.window, min_periods=int(self.window * 0.8)).mean()

        # 2. 趋势因子 = (P_t / MA_t) - 1
        df_trend = (df_price / df_ma) - 1

        # 3. 重采样到月末（取月末的趋势值）
        df_trend_monthly = df_trend.resample('ME').last()

        # 4. 移除前几个月的NaN值
        df_trend_monthly = df_trend_monthly.dropna(how='all')

        logger.info(f"趋势因子计算完成: {df_trend_monthly.shape[0]} 月 × {df_trend_monthly.shape[1]} 股票")
        logger.info(f"有效数据范围: {df_trend_monthly.index[0]} ~ {df_trend_monthly.index[-1]}")

        return df_trend_monthly
