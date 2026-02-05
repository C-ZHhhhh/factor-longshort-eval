"""
暴露检查模块

[INPUT]:
- df_weights (DataFrame): 组合权重 (index=日期, columns=股票代码)
- df_beta (DataFrame): 股票beta值 (可选)
- df_return (DataFrame): 股票收益率
- df_market_return (Series): 市场收益率

[OUTPUT]:
- 市场beta暴露 (Series): 组合对市场的beta
- 中性化验证 (dict): 权重和是否为0、多空平衡等
- 风险暴露 (dict): 各类风险因子暴露

[POS]:
暴露检查模块，验证market-neutral策略的中性化效果

[PROTOCOL]:
1. 计算组合beta = Σ(w_i × β_i)
2. 验证Σw ≈ 0
3. 检查多空对称性
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from scipy.stats import linregress


class ExposureChecker:
    """
    暴露检查器

    检查组合的市场暴露、中性化效果等
    """

    def __init__(self):
        pass

    def check_weight_neutrality(self, df_weights: pd.DataFrame) -> Dict:
        """
        检查权重中性化

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重 (index=日期, columns=股票代码)

        Returns:
        --------
        result : dict
            中性化检查结果
        """
        # 计算每期权重和
        weight_sums = df_weights.sum(axis=1)

        # 计算多头权重和
        long_sums = df_weights[df_weights > 0].sum(axis=1)

        # 计算空头权重和
        short_sums = df_weights[df_weights < 0].sum(axis=1)

        result = {
            'weight_sum_mean': weight_sums.mean(),
            'weight_sum_std': weight_sums.std(),
            'weight_sum_max': weight_sums.max(),
            'weight_sum_min': weight_sums.min(),
            'long_sum_mean': long_sums.mean(),
            'long_sum_std': long_sums.std(),
            'short_sum_mean': short_sums.mean(),
            'short_sum_std': short_sums.std(),
            'is_market_neutral': abs(weight_sums.mean()) < 0.01,  # 阈值0.01
            'neutrality_score': 1 - abs(weight_sums.mean())  # 越接近1越中性
        }

        return result

    def calculate_portfolio_beta(
        self,
        df_weights: pd.DataFrame,
        df_beta: pd.DataFrame
    ) -> pd.Series:
        """
        计算组合beta

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重
        df_beta : DataFrame
            股票beta值

        Returns:
        --------
        portfolio_beta : Series
            组合beta时间序列
        """
        # 对齐权重和beta的日期和股票
        common_dates = df_weights.index.intersection(df_beta.index)
        common_stocks = df_weights.columns.intersection(df_beta.columns)

        df_weights_aligned = df_weights.loc[common_dates, common_stocks]
        df_beta_aligned = df_beta.loc[common_dates, common_stocks]

        # 计算组合beta = Σ(w_i × β_i)
        portfolio_beta = (df_weights_aligned * df_beta_aligned).sum(axis=1)

        return portfolio_beta

    def estimate_beta_from_returns(
        self,
        df_portfolio_return: pd.Series,
        df_market_return: pd.Series
    ) -> Dict:
        """
        从收益率序列估计组合beta

        Parameters:
        -----------
        df_portfolio_return : Series
            组合收益率
        df_market_return : Series
            市场收益率

        Returns:
        --------
        result : dict
            包含beta、alpha、R²等
        """
        # 对齐数据
        common_dates = df_portfolio_return.index.intersection(df_market_return.index)

        if len(common_dates) < 10:
            return {
                'beta': np.nan,
                'alpha': np.nan,
                'r_squared': np.nan,
                'p_value': np.nan
            }

        port_ret = df_portfolio_return.loc[common_dates]
        mkt_ret = df_market_return.loc[common_dates]

        # 剔除缺失值
        valid_mask = port_ret.notna() & mkt_ret.notna()
        port_ret_valid = port_ret[valid_mask]
        mkt_ret_valid = mkt_ret[valid_mask]

        if len(port_ret_valid) < 10:
            return {
                'beta': np.nan,
                'alpha': np.nan,
                'r_squared': np.nan,
                'p_value': np.nan
            }

        # 线性回归: portfolio_return = alpha + beta × market_return
        slope, intercept, r_value, p_value, std_err = linregress(
            mkt_ret_valid, port_ret_valid
        )

        result = {
            'beta': slope,
            'alpha': intercept,
            'r_squared': r_value ** 2,
            'p_value': p_value,
            'std_error': std_err
        }

        return result

    def analyze_exposure(
        self,
        df_weights: pd.DataFrame,
        df_portfolio_return: Optional[pd.Series] = None,
        df_market_return: Optional[pd.Series] = None,
        df_beta: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        完整的暴露分析

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重
        df_portfolio_return : Series, optional
            组合收益率
        df_market_return : Series, optional
            市场收益率
        df_beta : DataFrame, optional
            股票beta值

        Returns:
        --------
        result : dict
            暴露分析结果
        """
        result = {}

        # 1. 权重中性化检查
        result['weight_neutrality'] = self.check_weight_neutrality(df_weights)

        # 2. 如果有股票beta数据,计算组合beta
        if df_beta is not None:
            portfolio_beta = self.calculate_portfolio_beta(df_weights, df_beta)
            result['portfolio_beta_series'] = portfolio_beta
            result['portfolio_beta_mean'] = portfolio_beta.mean()
            result['portfolio_beta_std'] = portfolio_beta.std()

        # 3. 如果有收益率数据,从收益率估计beta
        if df_portfolio_return is not None and df_market_return is not None:
            beta_stats = self.estimate_beta_from_returns(
                df_portfolio_return, df_market_return
            )
            result['estimated_beta'] = beta_stats

        return result

    def check_long_short_balance(self, df_weights: pd.DataFrame) -> Dict:
        """
        检查多空平衡性

        Parameters:
        -----------
        df_weights : DataFrame
            组合权重

        Returns:
        --------
        result : dict
            多空平衡检查结果
        """
        # 分离多空
        df_long = df_weights[df_weights > 0]
        df_short = df_weights[df_weights < 0]

        # 统计多空数量
        n_long = (df_weights > 0).sum(axis=1)
        n_short = (df_weights < 0).sum(axis=1)

        # 统计多空权重
        long_weight = df_long.sum(axis=1)
        short_weight = df_short.sum(axis=1).abs()

        result = {
            'avg_n_long': n_long.mean(),
            'avg_n_short': n_short.mean(),
            'avg_long_weight': long_weight.mean(),
            'avg_short_weight': short_weight.mean(),
            'long_short_ratio': long_weight.mean() / short_weight.mean() if short_weight.mean() != 0 else np.nan,
            'is_balanced': abs(long_weight.mean() - short_weight.mean()) < 0.05  # 阈值5%
        }

        return result
