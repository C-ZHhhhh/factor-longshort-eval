"""
[INPUT]: 持仓标记
[OUTPUT]: 原始权重 (未中性化)
[POS]: 权重分配模块

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class WeightingScheme:
    """权重分配器

    为持仓股票分配权重
    """

    def __init__(self, method: str = 'equal'):
        """
        初始化

        Args:
            method: 权重方法
                - 'equal': 等权
                - 'value': 因子值加权
                - 'inv_volatility': 反波动率加权 (需要额外数据)
        """
        self.method = method
        logger.info(f"初始化权重分配器: method={method}")

    def assign_weights(
        self,
        df_holdings: pd.DataFrame,
        df_factor: Optional[pd.DataFrame] = None,
        df_volatility: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        分配权重

        Args:
            df_holdings: 持仓标记 (月末日期 × 股票)
            df_factor: 因子值 (用于value加权), 可选
            df_volatility: 波动率 (用于inv_volatility加权), 可选

        Returns:
            权重 (月末日期 × 股票)
            注意: 返回的权重未中性化,需要后续处理
        """
        logger.info(f"开始分配权重: method={self.method}")

        if self.method == 'equal':
            df_weights = self._equal_weight(df_holdings)

        elif self.method == 'value':
            if df_factor is None:
                raise ValueError("value加权需要提供df_factor参数")
            df_weights = self._value_weight(df_holdings, df_factor)

        elif self.method == 'inv_volatility':
            if df_volatility is None:
                raise ValueError("inv_volatility加权需要提供df_volatility参数")
            df_weights = self._inv_volatility_weight(df_holdings, df_volatility)

        else:
            raise ValueError(f"不支持的权重方法: {self.method}")

        logger.info(f"权重分配完成")
        return df_weights

    def _equal_weight(self, df_holdings: pd.DataFrame) -> pd.DataFrame:
        """
        等权分配

        多头: 每只股票权重 = 1 / n_long
        空头: 每只股票权重 = -1 / n_short
        """
        logger.info("使用等权分配")

        df_weights = df_holdings.copy().astype(float)

        for date in df_holdings.index:
            holdings = df_holdings.loc[date]

            # 多头股票
            long_stocks = holdings[holdings == 1].index
            if len(long_stocks) > 0:
                df_weights.loc[date, long_stocks] = 1.0 / len(long_stocks)

            # 空头股票
            short_stocks = holdings[holdings == -1].index
            if len(short_stocks) > 0:
                df_weights.loc[date, short_stocks] = -1.0 / len(short_stocks)

        return df_weights

    def _value_weight(
        self,
        df_holdings: pd.DataFrame,
        df_factor: pd.DataFrame
    ) -> pd.DataFrame:
        """
        因子值加权

        权重与因子值的绝对值成正比
        """
        logger.info("使用因子值加权")

        df_weights = pd.DataFrame(0.0, index=df_holdings.index, columns=df_holdings.columns)

        for date in df_holdings.index:
            holdings = df_holdings.loc[date]
            factor_values = df_factor.loc[date]

            # 多头股票
            long_stocks = holdings[holdings == 1].index
            if len(long_stocks) > 0:
                long_values = factor_values[long_stocks].abs()
                long_sum = long_values.sum()
                if long_sum > 0:
                    df_weights.loc[date, long_stocks] = long_values / long_sum

            # 空头股票
            short_stocks = holdings[holdings == -1].index
            if len(short_stocks) > 0:
                short_values = factor_values[short_stocks].abs()
                short_sum = short_values.sum()
                if short_sum > 0:
                    df_weights.loc[date, short_stocks] = -(short_values / short_sum)

        return df_weights

    def _inv_volatility_weight(
        self,
        df_holdings: pd.DataFrame,
        df_volatility: pd.DataFrame
    ) -> pd.DataFrame:
        """
        反波动率加权 (风险平价)

        权重与波动率的倒数成正比
        """
        logger.info("使用反波动率加权")

        df_weights = pd.DataFrame(0.0, index=df_holdings.index, columns=df_holdings.columns)

        for date in df_holdings.index:
            holdings = df_holdings.loc[date]
            volatility = df_volatility.loc[date]

            # 避免除以0
            inv_vol = 1.0 / (volatility + 1e-8)

            # 多头股票
            long_stocks = holdings[holdings == 1].index
            if len(long_stocks) > 0:
                long_inv_vol = inv_vol[long_stocks]
                long_sum = long_inv_vol.sum()
                if long_sum > 0:
                    df_weights.loc[date, long_stocks] = long_inv_vol / long_sum

            # 空头股票
            short_stocks = holdings[holdings == -1].index
            if len(short_stocks) > 0:
                short_inv_vol = inv_vol[short_stocks]
                short_sum = short_inv_vol.sum()
                if short_sum > 0:
                    df_weights.loc[date, short_stocks] = -(short_inv_vol / short_sum)

        return df_weights
