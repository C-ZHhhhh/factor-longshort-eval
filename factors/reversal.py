"""
[INPUT]: 价格数据或月收益率数据
[OUTPUT]: 短期反转因子值, 索引t的值 = -(t月收益率)
[POS]: 短期反转因子实现

[UPDATE 2026-11-15]:
- 修复多滞后一个月: 原实现在因子内部shift(1), 回测引擎的时间对齐又shift(1),
  实际用的是两个月前的收益。现在因子内部不再shift, 滞后统一交给
  backtest/time_aligner.py (因子t → 收益t+1)

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

    定义: -R_t (t月收益率的负值, t月末即可得)
    说明: 刚过去这个月收益率的负值（捕捉短期均值回归效应）
          防look-ahead的滞后由回测引擎的时间对齐统一处理, 这里不重复shift
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

        # 3. 反转因子 = -R_t (本月收益率的负值)
        # 注意: 不在这里shift, 时间对齐器会把因子t对到收益t+1
        df_reversal = -df_return_monthly

        # 4. 移除第一个月的NaN值
        df_reversal = df_reversal.iloc[1:]

        logger.info(f"反转因子计算完成: {df_reversal.shape[0]} 月 × {df_reversal.shape[1]} 股票")
        logger.info(f"有效数据范围: {df_reversal.index[0]} ~ {df_reversal.index[-1]}")

        return df_reversal
