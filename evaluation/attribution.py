"""
归因分析模块

[INPUT]:
- df_portfolio_return (Series): 组合收益率
- df_weights (DataFrame): 组合权重
- df_stock_return (DataFrame): 股票收益率
- df_factor (DataFrame): 因子值(可选)

[OUTPUT]:
- 收益归因 (dict): 多头贡献、空头贡献、选股收益等
- 因子归因 (dict): 各因子对收益的贡献(可选)

[POS]:
归因分析模块，拆解收益来源

[PROTOCOL]:
1. 分解多空收益贡献
2. 计算选股收益 vs 时机收益
3. 如果有因子数据,做因子归因
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class AttributionAnalyzer:
    """
    归因分析器

    拆解组合收益的来源
    """

    def __init__(self):
        pass

    def decompose_long_short(
        self,
        df_weights: pd.DataFrame,
        df_stock_return: pd.DataFrame
    ) -> Dict:
        """
        分解多空收益贡献

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重
        df_stock_return : DataFrame
            股票收益率

        Returns:
        --------
        result : dict
            多空收益分解
        """
        # 对齐权重和收益率
        common_dates = df_weights.index.intersection(df_stock_return.index)
        common_stocks = df_weights.columns.intersection(df_stock_return.columns)

        df_weights_aligned = df_weights.loc[common_dates, common_stocks]
        df_return_aligned = df_stock_return.loc[common_dates, common_stocks]

        # 分离多空权重
        df_weights_long = df_weights_aligned.copy()
        df_weights_long[df_weights_long < 0] = 0

        df_weights_short = df_weights_aligned.copy()
        df_weights_short[df_weights_short > 0] = 0

        # 计算多空收益贡献
        long_contrib = (df_weights_long * df_return_aligned).sum(axis=1)
        short_contrib = (df_weights_short * df_return_aligned).sum(axis=1)
        total_return = long_contrib + short_contrib

        result = {
            'long_contrib_series': long_contrib,
            'short_contrib_series': short_contrib,
            'total_return_series': total_return,
            'long_contrib_mean': long_contrib.mean(),
            'short_contrib_mean': short_contrib.mean(),
            'long_contrib_std': long_contrib.std(),
            'short_contrib_std': short_contrib.std(),
            'long_sharpe': long_contrib.mean() / long_contrib.std() * np.sqrt(12) if long_contrib.std() > 0 else np.nan,
            'short_sharpe': short_contrib.mean() / short_contrib.std() * np.sqrt(12) if short_contrib.std() > 0 else np.nan,
            'long_pct': long_contrib.sum() / total_return.sum() if total_return.sum() != 0 else np.nan,
            'short_pct': short_contrib.sum() / total_return.sum() if total_return.sum() != 0 else np.nan
        }

        return result

    def calculate_stock_selection(
        self,
        df_weights: pd.DataFrame,
        df_stock_return: pd.DataFrame
    ) -> Dict:
        """
        计算选股收益

        选股收益 = 实际收益 - 基准收益
        这里基准为等权组合

        Parameters:
        -----------
        df_weights : DataFrame
            实际权重
        df_stock_return : DataFrame
            股票收益率

        Returns:
        --------
        result : dict
            选股收益分解
        """
        # 对齐
        common_dates = df_weights.index.intersection(df_stock_return.index)
        common_stocks = df_weights.columns.intersection(df_stock_return.columns)

        df_weights_aligned = df_weights.loc[common_dates, common_stocks]
        df_return_aligned = df_stock_return.loc[common_dates, common_stocks]

        # 实际收益
        actual_return = (df_weights_aligned * df_return_aligned).sum(axis=1)

        # 构建等权基准
        # 多头等权 + 空头等权
        df_benchmark_weights = pd.DataFrame(0.0, index=df_weights_aligned.index, columns=df_weights_aligned.columns)

        for date in df_weights_aligned.index:
            weights = df_weights_aligned.loc[date]
            long_stocks = weights[weights > 0].index
            short_stocks = weights[weights < 0].index

            if len(long_stocks) > 0:
                df_benchmark_weights.loc[date, long_stocks] = 1.0 / len(long_stocks)
            if len(short_stocks) > 0:
                df_benchmark_weights.loc[date, short_stocks] = -1.0 / len(short_stocks)

        # 基准收益
        benchmark_return = (df_benchmark_weights * df_return_aligned).sum(axis=1)

        # 选股收益 = 实际收益 - 基准收益
        selection_return = actual_return - benchmark_return

        result = {
            'actual_return': actual_return.mean(),
            'benchmark_return': benchmark_return.mean(),
            'selection_return_series': selection_return,
            'selection_return_mean': selection_return.mean(),
            'selection_return_std': selection_return.std(),
            'selection_sharpe': selection_return.mean() / selection_return.std() * np.sqrt(12) if selection_return.std() > 0 else np.nan,
            'selection_contribution': selection_return.sum() / actual_return.sum() if actual_return.sum() != 0 else np.nan
        }

        return result

    def analyze_top_contributors(
        self,
        df_weights: pd.DataFrame,
        df_stock_return: pd.DataFrame,
        top_n: int = 10
    ) -> Dict:
        """
        分析收益贡献最大的股票

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重
        df_stock_return : DataFrame
            股票收益率
        top_n : int
            Top N 股票

        Returns:
        --------
        result : dict
            包含累计贡献Top N的股票
        """
        # 对齐
        common_dates = df_weights.index.intersection(df_stock_return.index)
        common_stocks = df_weights.columns.intersection(df_stock_return.columns)

        df_weights_aligned = df_weights.loc[common_dates, common_stocks]
        df_return_aligned = df_stock_return.loc[common_dates, common_stocks]

        # 计算每只股票的累计贡献
        stock_contrib = (df_weights_aligned * df_return_aligned).sum(axis=0)

        # 排序
        top_contributors = stock_contrib.nlargest(top_n)
        bottom_contributors = stock_contrib.nsmallest(top_n)

        result = {
            'top_contributors': top_contributors,
            'bottom_contributors': bottom_contributors,
            'total_contribution': stock_contrib.sum()
        }

        return result

    def analyze(
        self,
        df_weights: pd.DataFrame,
        df_stock_return: pd.DataFrame
    ) -> Dict:
        """
        完整的归因分析

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重
        df_stock_return : DataFrame
            股票收益率

        Returns:
        --------
        result : dict
            归因分析结果
        """
        result = {}

        # 1. 多空收益分解
        result['long_short_decomposition'] = self.decompose_long_short(
            df_weights, df_stock_return
        )

        # 2. 选股收益
        result['stock_selection'] = self.calculate_stock_selection(
            df_weights, df_stock_return
        )

        # 3. Top贡献者
        result['top_contributors'] = self.analyze_top_contributors(
            df_weights, df_stock_return, top_n=10
        )

        return result
