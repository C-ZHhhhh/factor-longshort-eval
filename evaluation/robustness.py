"""
稳健性测试模块

[INPUT]:
- df_factor (DataFrame): 因子值
- df_return (DataFrame): 收益率
- 参数列表: cost_bps, quantile, 时间段等

[OUTPUT]:
- 稳健性对比表 (DataFrame): 不同参数下的回测结果
- 子样本测试 (dict): 不同时间段的表现对比
- 参数敏感性 (DataFrame): 参数变化对结果的影响

[POS]:
稳健性测试模块，验证策略在不同条件下的稳定性

[PROTOCOL]:
1. 子样本测试: 至少分2个时间段
2. 参数敏感性: 测试成本、分位数等关键参数
3. 结果汇总为对比表
4. test_parameter_sensitivity 对 param_grid 做的是笛卡尔积(所有取值两两组合)。
   两个参数需要"成对变化"时(如退出阈值 = 进入阈值 + 5%), 不能把两个列表都塞进
   param_grid, 要像 test_quantile_sensitivity 那样逐对调用

修复记录:
- 分位数敏感性原来把进入阈值列表和退出阈值列表一起交给笛卡尔积, 5 个分位数跑出了
  25 组, 其中还有退出阈值比进入阈值更严的无意义组合。现在逐对运行, 每个分位数一行。
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backtest.engine import BacktestEngine
from portfolio.portfolio_builder import PortfolioBuilder


class RobustnessTest:
    """
    稳健性测试器

    测试策略在不同参数和时间段下的稳健性
    """

    def __init__(self):
        pass

    def test_sub_samples(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        split_dates: List[str],
        **backtest_params
    ) -> Dict:
        """
        子样本测试

        将数据分成多个时间段,分别回测

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率
        split_dates : list of str
            时间段分割点,如['2020-01-01']表示分成2段
        **backtest_params : dict
            回测参数

        Returns:
        --------
        result : dict
            各子样本的回测结果
        """
        # 确保split_dates排序并转换为Timestamp
        split_dates = [pd.Timestamp(d) for d in split_dates]
        split_dates = sorted(split_dates)

        # 添加起止日期
        all_dates = [df_factor.index.min()] + split_dates + [df_factor.index.max()]

        results = {}

        # 对每个时间段进行回测
        for i in range(len(all_dates) - 1):
            start_date = all_dates[i]
            end_date = all_dates[i + 1]

            # 筛选数据 - 对齐因子和收益率的时间范围
            common_dates = df_factor.index.intersection(df_return.index)
            mask = (common_dates >= start_date) & (common_dates <= end_date)
            dates_sub = common_dates[mask]

            df_factor_sub = df_factor.loc[dates_sub]
            df_return_sub = df_return.loc[dates_sub]

            if len(df_factor_sub) == 0:
                print(f"跳过时间段 {start_date} ~ {end_date}: 无数据")
                continue

            # 回测
            builder = PortfolioBuilder(
                entry_quantile=backtest_params.get('entry_quantile', 0.25),
                exit_quantile=backtest_params.get('exit_quantile', 0.30),
                min_holding_periods=backtest_params.get('min_holding_periods', 12),
                long_top=backtest_params.get('long_top', True)
            )

            df_weights = builder.build(df_factor_sub)

            engine = BacktestEngine(
                cost_bps=backtest_params.get('cost_bps', 20.0),
                rebalance_freq=backtest_params.get('rebalance_freq', '2monthly')
            )

            backtest_result = engine.run(df_weights, df_return_sub)

            results[f'period_{i+1}_{start_date.strftime("%Y-%m")}_{end_date.strftime("%Y-%m")}'] = backtest_result

        return results

    def test_parameter_sensitivity(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        param_grid: Dict
    ) -> pd.DataFrame:
        """
        参数敏感性测试

        测试不同参数组合下的回测表现

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率
        param_grid : dict
            参数网格,如:
            {
                'cost_bps': [10, 20, 30],
                'entry_quantile': [0.2, 0.25, 0.3],
                'min_holding_periods': [6, 12, 18]
            }

        Returns:
        --------
        result_df : DataFrame
            参数敏感性测试结果表
        """
        import itertools

        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))

        results = []

        for combo in param_combinations:
            # 构建参数字典
            params = dict(zip(param_names, combo))

            # 回测
            try:
                builder = PortfolioBuilder(
                    entry_quantile=params.get('entry_quantile', 0.25),
                    exit_quantile=params.get('exit_quantile', 0.30),
                    min_holding_periods=params.get('min_holding_periods', 12),
                    long_top=True
                )

                df_weights = builder.build(df_factor)

                engine = BacktestEngine(
                    cost_bps=params.get('cost_bps', 20.0),
                    rebalance_freq=params.get('rebalance_freq', '2monthly')
                )

                backtest_result = engine.run(df_weights, df_return)

                # 提取关键指标 - 从嵌套的metrics字典中获取
                metrics = backtest_result['metrics']
                row = params.copy()
                row.update({
                    'annual_return': metrics['annual_return'],
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'max_drawdown': metrics['max_drawdown'],
                    'calmar_ratio': metrics['calmar_ratio'],
                    'avg_turnover': backtest_result['turnover'].mean()
                })

                results.append(row)

            except Exception as e:
                print(f"参数组合 {params} 回测失败: {e}")
                continue

        result_df = pd.DataFrame(results)
        return result_df

    def test_cost_sensitivity(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        cost_bps_list: List[float] = [10, 20, 30, 40, 50]
    ) -> pd.DataFrame:
        """
        交易成本敏感性测试

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率
        cost_bps_list : list
            交易成本列表(单位: bps)

        Returns:
        --------
        result_df : DataFrame
            成本敏感性结果
        """
        param_grid = {
            'cost_bps': cost_bps_list,
            'entry_quantile': [0.25],
            'exit_quantile': [0.30],
            'min_holding_periods': [12],
            'rebalance_freq': ['2monthly']
        }

        return self.test_parameter_sensitivity(df_factor, df_return, param_grid)

    def test_quantile_sensitivity(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        quantile_list: List[float] = [0.1, 0.15, 0.2, 0.25, 0.3],
        exit_buffer: float = 0.05
    ) -> pd.DataFrame:
        """
        分位数敏感性测试

        每个进入阈值只配一个退出阈值(进入阈值 + exit_buffer), 所以结果的行数
        等于 quantile_list 的长度。

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率
        quantile_list : list
            进入阈值列表
        exit_buffer : float
            退出阈值比进入阈值宽多少, 默认 0.05 (如 25% 进入 / 30% 退出)

        Returns:
        --------
        result_df : DataFrame
            分位数敏感性结果, 每个进入阈值一行, 含 entry_quantile 和 exit_quantile 两列
        """
        results = []
        for entry_quantile in quantile_list:
            # round: 避免 0.1 + 0.05 = 0.15000000000000002 这类浮点尾巴
            exit_quantile = round(entry_quantile + exit_buffer, 10)
            param_grid = {
                'cost_bps': [20],
                'entry_quantile': [entry_quantile],
                'exit_quantile': [exit_quantile],
                'min_holding_periods': [12],
                'rebalance_freq': ['2monthly']
            }
            results.append(self.test_parameter_sensitivity(df_factor, df_return, param_grid))

        return pd.concat(results, ignore_index=True)

    def analyze_robustness(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame,
        split_date: str = '2020-01-01'
    ) -> Dict:
        """
        完整的稳健性分析

        Parameters:
        -----------
        df_factor : DataFrame
            因子值
        df_return : DataFrame
            收益率
        split_date : str
            子样本分割日期

        Returns:
        --------
        result : dict
            稳健性分析结果
        """
        result = {}

        # 1. 子样本测试
        print("子样本测试...")
        result['sub_sample'] = self.test_sub_samples(
            df_factor, df_return,
            split_dates=[split_date],
            entry_quantile=0.25,
            exit_quantile=0.30,
            min_holding_periods=12,
            rebalance_freq='2monthly',
            cost_bps=20.0
        )

        # 2. 成本敏感性
        print("成本敏感性测试...")
        result['cost_sensitivity'] = self.test_cost_sensitivity(
            df_factor, df_return,
            cost_bps_list=[10, 20, 30, 40, 50]
        )

        # 3. 分位数敏感性
        print("分位数敏感性测试...")
        result['quantile_sensitivity'] = self.test_quantile_sensitivity(
            df_factor, df_return,
            quantile_list=[0.1, 0.15, 0.2, 0.25, 0.3]
        )

        return result
