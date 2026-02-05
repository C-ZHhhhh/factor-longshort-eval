"""
IC/IR分析模块

[INPUT]:
- df_factor (DataFrame): 月度因子值 (index=日期, columns=股票代码)
- df_return (DataFrame): 月度收益率 (index=日期, columns=股票代码)

[OUTPUT]:
- IC时间序列 (Series): 每月的信息系数
- IR (float): 信息比率 = mean(IC) / std(IC)
- 统计量 (dict): IC均值、中位数、正占比等

[POS]:
核心评估模块，用于评估因子预测能力

[PROTOCOL]:
1. 使用Spearman秩相关计算IC
2. 因子和收益需要时间对齐(factor_t预测return_t+1)
3. 计算时剔除缺失值
"""

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from typing import Dict


class ICAnalyzer:
    """
    IC/IR分析器

    计算因子的信息系数(IC)和信息比率(IR)
    """

    def __init__(self):
        pass

    def calculate_ic_series(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame
    ) -> pd.Series:
        """
        计算IC时间序列

        Parameters:
        -----------
        df_factor : DataFrame
            因子值 (index=日期, columns=股票代码)
        df_return : DataFrame
            收益率 (index=日期, columns=股票代码)

        Returns:
        --------
        ic_series : Series
            IC时间序列 (index=日期)
        """
        # 对齐因子和收益率的时间和股票
        common_dates = df_factor.index.intersection(df_return.index)
        common_stocks = df_factor.columns.intersection(df_return.columns)

        if len(common_dates) == 0 or len(common_stocks) == 0:
            raise ValueError("因子和收益率数据没有共同的日期或股票")

        df_factor_aligned = df_factor.loc[common_dates, common_stocks]
        df_return_aligned = df_return.loc[common_dates, common_stocks]

        ic_list = []
        ic_dates = []

        # 逐月计算IC
        for date in common_dates:
            factor_values = df_factor_aligned.loc[date]
            return_values = df_return_aligned.loc[date]

            # 剔除缺失值
            valid_mask = factor_values.notna() & return_values.notna()

            if valid_mask.sum() < 10:  # 至少需要10只股票
                continue

            factor_valid = factor_values[valid_mask]
            return_valid = return_values[valid_mask]

            # 计算Spearman相关系数
            ic, _ = spearmanr(factor_valid, return_valid)

            ic_list.append(ic)
            ic_dates.append(date)

        ic_series = pd.Series(ic_list, index=ic_dates)
        return ic_series

    def calculate_ir(self, ic_series: pd.Series) -> float:
        """
        计算信息比率 IR = mean(IC) / std(IC)

        Parameters:
        -----------
        ic_series : Series
            IC时间序列

        Returns:
        --------
        ir : float
            信息比率
        """
        if len(ic_series) == 0:
            return np.nan

        ic_mean = ic_series.mean()
        ic_std = ic_series.std()

        if ic_std == 0 or np.isnan(ic_std):
            return np.nan

        ir = ic_mean / ic_std
        return ir

    def analyze(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame
    ) -> Dict:
        """
        完整的IC/IR分析

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率

        Returns:
        --------
        result : dict
            包含IC序列和统计量的字典
        """
        # 计算IC序列
        ic_series = self.calculate_ic_series(df_factor, df_return)

        # Sanity Print: 输出样本期数
        print(f"\n[IC Analysis] 样本期数 N = {len(ic_series)}")

        # 计算IR (确保使用独立的 std 计算)
        ic_mean = ic_series.mean()
        ic_std = ic_series.std(ddof=1)  # 使用样本标准差 (N-1)

        print(f"[IC Analysis] IC 均值 = {ic_mean:.6f}")
        print(f"[IC Analysis] IC 标准差 = {ic_std:.6f} (ddof=1, 样本标准差)")

        if ic_std == 0 or np.isnan(ic_std):
            ir = np.nan
            print(f"[IC Analysis] ⚠️  IR = NaN (IC标准差为0或NaN)")
        else:
            ir = ic_mean / ic_std
            print(f"[IC Analysis] IR = IC均值 / IC标准差 = {ir:.6f}")

        # 计算其他统计量
        ic_median = ic_series.median()
        ic_positive_ratio = (ic_series > 0).sum() / len(ic_series)

        # 计算t统计量(检验IC是否显著异于0)
        t_stat = ic_mean / (ic_std / np.sqrt(len(ic_series)))

        print(f"[IC Analysis] IC 中位数 = {ic_median:.6f}")
        print(f"[IC Analysis] IC 正占比 = {ic_positive_ratio:.2%}")
        print(f"[IC Analysis] t 统计量 = {t_stat:.4f} (|t|>2 表示显著)\n")

        result = {
            'ic_series': ic_series,
            'ir': ir,
            'ic_mean': ic_mean,
            'ic_median': ic_median,
            'ic_std': ic_std,
            'ic_positive_ratio': ic_positive_ratio,
            't_statistic': t_stat,
            'n_periods': len(ic_series)
        }

        return result

    def analyze_with_lag(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        lag: int = 1
    ) -> Dict:
        """
        考虑时间滞后的IC分析

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率
        lag : int, default=1
            滞后期数(factor_t预测return_t+lag)

        Returns:
        --------
        result : dict
            IC分析结果
        """
        # 因子shift lag期
        df_factor_shifted = df_factor.shift(lag)

        # 调用标准analyze方法
        return self.analyze(df_factor_shifted, df_return)

    def sanity_check_alignment(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        factor_name: str = "Factor"
    ) -> Dict:
        """
        IC 时间对齐 Sanity Check

        检查 factor_t vs return_t+1 (正确) vs factor_t vs return_t (错误)
        如果两者非常接近，说明可能存在对齐错误或数据泄露

        Parameters:
        -----------
        df_factor : DataFrame
            因子值 (index=日期, columns=股票代码)
        df_return : DataFrame
            收益率 (index=日期, columns=股票代码)
        factor_name : str
            因子名称（用于报告）

        Returns:
        --------
        sanity_result : dict
            包含 IC_forward, IC_same_period, 对齐示例等
        """
        # 1. 打印日期对齐示例
        common_dates = df_factor.index.intersection(df_return.index)
        if len(common_dates) < 3:
            return {
                'status': 'FAIL',
                'message': '共同日期不足3期，无法进行sanity check'
            }

        alignment_sample = []
        for i in range(min(3, len(common_dates))):
            date = common_dates[i]
            if i < len(common_dates) - 1:
                next_date = common_dates[i + 1]
                alignment_sample.append({
                    'factor_date': str(date),
                    'return_forward': str(next_date),
                    'return_same': str(date)
                })

        # 2. 计算 IC_forward (factor_t vs return_t+1) - 正确的
        df_factor_shifted = df_factor.shift(1)
        ic_series_forward = self.calculate_ic_series(df_factor_shifted, df_return)
        ic_forward_mean = ic_series_forward.mean()
        ic_forward_positive_ratio = (ic_series_forward > 0).sum() / len(ic_series_forward) if len(ic_series_forward) > 0 else 0

        # 3. 计算 IC_same_period (factor_t vs return_t) - 错误的，仅用于对比
        ic_series_same = self.calculate_ic_series(df_factor, df_return)
        ic_same_mean = ic_series_same.mean()
        ic_same_positive_ratio = (ic_series_same > 0).sum() / len(ic_series_same) if len(ic_series_same) > 0 else 0

        # 4. 检测异常
        warnings = []

        # 4.1 检查两者是否过于接近（说明可能没有正确对齐）
        if abs(ic_forward_mean - ic_same_mean) < 0.01:
            warnings.append("⚠️  IC_forward 和 IC_same_period 非常接近，可能存在时间对齐问题")

        # 4.2 检查 IC 是否异常高（可能是数据泄露）
        if abs(ic_forward_mean) > 0.2 and ic_forward_positive_ratio > 0.9:
            warnings.append(f"⚠️  IC_forward 异常高 ({ic_forward_mean:.4f}) 且正占比>90%，可能存在数据泄露或对齐错误")

        # 4.3 检查 IC_same 是否异常高（说明在用同期数据）
        if abs(ic_same_mean) > 0.2 and ic_same_positive_ratio > 0.9:
            warnings.append(f"⚠️  IC_same_period 异常高 ({ic_same_mean:.4f})，说明factor_t与return_t高度相关，不应用于预测")

        # 5. 状态判定
        status = 'PASS'
        if abs(ic_forward_mean) > 0.2 and ic_forward_positive_ratio > 0.9:
            status = 'WARNING'
        if abs(ic_forward_mean - ic_same_mean) < 0.01:
            status = 'WARNING'

        return {
            'status': status,
            'factor_name': factor_name,
            'alignment_sample': alignment_sample,
            'ic_forward_mean': ic_forward_mean,
            'ic_forward_positive_ratio': ic_forward_positive_ratio,
            'ic_same_period_mean': ic_same_mean,
            'ic_same_period_positive_ratio': ic_same_positive_ratio,
            'ic_difference': abs(ic_forward_mean - ic_same_mean),
            'warnings': warnings,
            'n_periods_forward': len(ic_series_forward),
            'n_periods_same': len(ic_series_same)
        }
