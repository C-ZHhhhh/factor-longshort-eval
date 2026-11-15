"""
[INPUT]: 对齐后的因子/权重、收益率数据
[OUTPUT]: 净值曲线、收益率序列、换手率序列、持仓历史
[POS]: 回测引擎核心 - 主回测循环，整合时间对齐、交易成本、绩效计算

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md

[UPDATE 2026-02-03]:
- 添加调仓频率参数: 支持每月/每2月/每季度调仓
- 非调仓期继续持有上期权重，换手率=0

[UPDATE 2026-11-15]:
- 结果里新增 effective_weights: 每一期实际用来算收益的权重 (已剔除当期无收益的股票并重新归一化,
  非调仓期是延续下来的权重)。holdings_history 只是目标权重, 不等于实际生效的权重;
  Beta 对冲 (backtest/beta_hedge.py) 要按实际生效的权重算组合 Beta。
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from utils.logger import get_logger
from backtest.time_aligner import TimeAligner
from backtest.transaction import TransactionCostModel
from backtest.metrics import PerformanceMetrics

logger = get_logger(__name__)


class BacktestEngine:
    """回测引擎（支持不同调仓频率）

    核心回测循环，整合所有回测模块
    """

    def __init__(
        self,
        cost_bps: float = 20.0,
        periods_per_year: int = 12,
        initial_nav: float = 1.0,
        rebalance_freq: str = 'monthly'  # 新增: 调仓频率
    ):
        """
        初始化回测引擎

        Args:
            cost_bps: 交易成本（基点）
            periods_per_year: 每年期数（月度=12，日度=252）
            initial_nav: 初始净值
            rebalance_freq: 调仓频率
                - 'monthly': 每月调仓（默认）
                - '2monthly': 每2月调仓
                - 'quarterly': 每季度调仓
        """
        self.cost_bps = cost_bps
        self.periods_per_year = periods_per_year
        self.initial_nav = initial_nav
        self.rebalance_freq = rebalance_freq

        # 调仓间隔（月数）
        self.rebalance_interval = {
            'monthly': 1,
            '2monthly': 2,
            'quarterly': 3
        }.get(rebalance_freq, 1)

        # 初始化各个组件
        self.time_aligner = TimeAligner()
        self.cost_model = TransactionCostModel(cost_bps=cost_bps)
        self.metrics_calculator = PerformanceMetrics(periods_per_year=periods_per_year)

        logger.info(
            f"初始化回测引擎: cost_bps={cost_bps}, periods_per_year={periods_per_year}, "
            f"rebalance_freq={rebalance_freq} (每{self.rebalance_interval}月)"
        )

    def run(
        self,
        df_weights: pd.DataFrame,
        df_return: pd.DataFrame,
        align_time: bool = True
    ) -> Dict:
        """
        运行回测

        Args:
            df_weights: 组合权重 (月末日期 × 股票)
            df_return: 收益率 (月末日期 × 股票)
            align_time: 是否进行时间对齐（默认True，防look-ahead）

        Returns:
            回测结果字典，包含：
            - nav: 净值曲线
            - nav_no_cost: 不含成本的净值曲线
            - returns: 收益率序列（扣除成本后）
            - returns_no_cost: 收益率序列（不扣成本）
            - turnover: 换手率序列
            - cost_series: 交易成本序列
            - holdings_history: 持仓历史
            - metrics: 绩效指标
            - metrics_no_cost: 不含成本的绩效指标
        """
        logger.info("="*70)
        logger.info("开始回测")
        logger.info("="*70)

        # 1. 时间对齐（防look-ahead bias）
        if align_time:
            logger.info("执行时间对齐...")
            df_weights_aligned, df_return_aligned = self.time_aligner.align_weights_and_return(
                df_weights, df_return
            )
        else:
            logger.info("跳过时间对齐（使用已对齐数据）")
            df_weights_aligned = df_weights
            df_return_aligned = df_return

        # 确保索引和列对齐
        common_dates = df_weights_aligned.index.intersection(df_return_aligned.index)
        common_tickers = df_weights_aligned.columns.intersection(df_return_aligned.columns)

        df_weights_aligned = df_weights_aligned.loc[common_dates, common_tickers]
        df_return_aligned = df_return_aligned.loc[common_dates, common_tickers]

        logger.info(f"对齐后数据: {df_weights_aligned.shape[0]} 期 × {df_weights_aligned.shape[1]} 股票")

        # 2. 主回测循环
        logger.info(f"执行主回测循环(调仓频率: 每{self.rebalance_interval}月)...")
        backtest_results = self._backtest_loop(df_weights_aligned, df_return_aligned)

        # 3. 计算绩效指标
        logger.info("计算绩效指标...")

        # 有成本的指标
        metrics = self.metrics_calculator.calculate_all_metrics(
            returns=backtest_results['returns'],
            nav=backtest_results['nav']
        )

        # 无成本的指标
        metrics_no_cost = self.metrics_calculator.calculate_all_metrics(
            returns=backtest_results['returns_no_cost'],
            nav=backtest_results['nav_no_cost']
        )

        backtest_results['metrics'] = metrics
        backtest_results['metrics_no_cost'] = metrics_no_cost

        # 4. 打印结果摘要
        self._print_summary(backtest_results)

        logger.info("="*70)
        logger.info("回测完成")
        logger.info("="*70)

        return backtest_results

    def _is_rebalance_period(self, period_index: int) -> bool:
        """
        判断当前期是否为调仓期

        Args:
            period_index: 当前期索引（从0开始）

        Returns:
            是否需要调仓
        """
        # 第一期必须调仓（初始建仓）
        if period_index == 0:
            return True

        # 后续期根据调仓频率判断
        return period_index % self.rebalance_interval == 0

    def _backtest_loop(
        self,
        df_weights: pd.DataFrame,
        df_return: pd.DataFrame
    ) -> Dict:
        """
        主回测循环（支持不同调仓频率）

        Args:
            df_weights: 对齐后的权重
            df_return: 对齐后的收益率

        Returns:
            回测结果
        """
        dates = df_weights.index
        n_periods = len(dates)

        # 初始化结果容器
        nav_series = pd.Series(index=dates, dtype=float)
        nav_no_cost_series = pd.Series(index=dates, dtype=float)
        returns_series = pd.Series(index=dates, dtype=float)
        returns_no_cost_series = pd.Series(index=dates, dtype=float)
        turnover_series = pd.Series(index=dates, dtype=float)
        cost_series = pd.Series(index=dates, dtype=float)
        effective_weights = {}  # {日期: 当期实际生效的权重}

        # 初始净值
        current_nav = self.initial_nav
        current_nav_no_cost = self.initial_nav

        # 上期权重（用于计算换手率）
        prev_weights = None

        # 当前生效权重（可能是本期调仓后的新权重，也可能是上期延续的权重）
        current_weights = None

        logger.info(f"开始回测循环: {n_periods} 期")

        for i, date in enumerate(dates):
            # 判断是否为调仓期
            is_rebalance = self._is_rebalance_period(i)

            # 获取当期收益
            returns = df_return.loc[date]

            if is_rebalance:
                # === 调仓期：使用新权重 ===

                # 获取新权重
                weights = df_weights.loc[date]

                # 对齐有效数据（移除缺失值）
                valid_mask = weights.notna() & returns.notna()
                weights_valid = weights[valid_mask]
                returns_valid = returns[valid_mask]

                # 重新归一化权重（确保市场中性）
                if len(weights_valid) > 0:
                    long_mask = weights_valid > 0
                    short_mask = weights_valid < 0

                    if long_mask.sum() > 0:
                        weights_valid.loc[long_mask] = weights_valid[long_mask] / weights_valid[long_mask].sum()
                    if short_mask.sum() > 0:
                        weights_valid.loc[short_mask] = weights_valid[short_mask] / abs(weights_valid[short_mask].sum())

                # 计算换手率
                if prev_weights is not None:
                    # 对齐当期和上期的股票列表
                    all_tickers = weights.index.union(prev_weights.index)
                    weights_aligned = weights.reindex(all_tickers, fill_value=0)
                    prev_weights_aligned = prev_weights.reindex(all_tickers, fill_value=0)

                    # 换手率 = 0.5 × Σ|Δw|
                    turnover = 0.5 * (weights_aligned - prev_weights_aligned).abs().sum()
                else:
                    # 第一期：全部建仓，换手率 = 1.0
                    turnover = 1.0

                # 更新当前生效权重
                current_weights = weights.copy()

            else:
                # === 非调仓期：继续持有上期权重 ===

                # 使用上期权重
                weights_valid = current_weights

                # 对齐有效数据
                valid_mask = weights_valid.notna() & returns.notna()
                weights_valid = weights_valid[valid_mask]
                returns_valid = returns[valid_mask]

                # 重新归一化（防止数值漂移）
                if len(weights_valid) > 0:
                    long_mask = weights_valid > 0
                    short_mask = weights_valid < 0

                    if long_mask.sum() > 0:
                        weights_valid.loc[long_mask] = weights_valid[long_mask] / weights_valid[long_mask].sum()
                    if short_mask.sum() > 0:
                        weights_valid.loc[short_mask] = weights_valid[short_mask] / abs(weights_valid[short_mask].sum())

                # 非调仓期：换手率 = 0
                turnover = 0.0

            # 计算组合收益（不含成本）
            if len(weights_valid) > 0 and len(returns_valid) > 0:
                portfolio_return_no_cost = (weights_valid * returns_valid).sum()
            else:
                portfolio_return_no_cost = 0.0

            # 计算交易成本
            cost = self.cost_model.calculate_cost(turnover)

            # 含成本的收益率
            portfolio_return = portfolio_return_no_cost + cost  # cost是负值

            # 更新净值
            current_nav = current_nav * (1 + portfolio_return)
            current_nav_no_cost = current_nav_no_cost * (1 + portfolio_return_no_cost)

            # 记录结果
            nav_series.iloc[i] = current_nav
            nav_no_cost_series.iloc[i] = current_nav_no_cost
            returns_series.iloc[i] = portfolio_return
            returns_no_cost_series.iloc[i] = portfolio_return_no_cost
            turnover_series.iloc[i] = turnover
            cost_series.iloc[i] = -cost  # 记录为正值
            effective_weights[date] = weights_valid

            # 更新上期权重（用于下次调仓时计算换手率）
            if is_rebalance:
                prev_weights = current_weights.copy()

            # 定期日志
            if (i + 1) % 20 == 0 or i == 0 or i == n_periods - 1:
                rebalance_flag = "[调仓]" if is_rebalance else "[持有]"
                logger.info(
                    f"  [{i+1}/{n_periods}] {date.strftime('%Y-%m')} {rebalance_flag}: "
                    f"收益={portfolio_return:.2%}, 换手={turnover:.2%}, "
                    f"成本={-cost:.4%}, 净值={current_nav:.4f}"
                )

        logger.info("回测循环完成")

        return {
            'nav': nav_series,
            'nav_no_cost': nav_no_cost_series,
            'returns': returns_series,
            'returns_no_cost': returns_no_cost_series,
            'turnover': turnover_series,
            'cost_series': cost_series,
            'holdings_history': df_weights,  # 目标权重 (调仓期的新权重; 非调仓期并未生效)
            # 每期实际生效的权重: 行=收益所在的月份, 列=股票, 未持有为0
            'effective_weights': pd.DataFrame(effective_weights).T.reindex(
                index=dates, columns=df_weights.columns
            ).fillna(0.0),
        }

    def _print_summary(self, results: Dict):
        """打印回测结果摘要"""
        logger.info("\n" + "="*70)
        logger.info("回测结果摘要")
        logger.info("="*70)

        # 净值信息
        logger.info(f"\n净值曲线:")
        logger.info(f"  期数:       {len(results['nav'])}")
        logger.info(f"  起始净值:   {results['nav'].iloc[0]:.4f}")
        logger.info(f"  最终净值:   {results['nav'].iloc[-1]:.4f} (含成本)")
        logger.info(f"  最终净值:   {results['nav_no_cost'].iloc[-1]:.4f} (不含成本)")

        # 换手率统计
        logger.info(f"\n换手率统计:")
        logger.info(f"  平均换手率: {results['turnover'].mean():.2%}")
        logger.info(f"  中位数:     {results['turnover'].median():.2%}")
        logger.info(f"  最大:       {results['turnover'].max():.2%}")
        logger.info(f"  最小:       {results['turnover'].min():.2%}")

        # 调仓次数
        rebalance_count = (results['turnover'] > 0).sum()
        logger.info(f"  调仓次数:   {rebalance_count} / {len(results['turnover'])} 期")

        # 交易成本统计
        logger.info(f"\n交易成本统计:")
        logger.info(f"  平均单期成本: {results['cost_series'].mean():.4%}")
        logger.info(f"  累计成本:     {results['cost_series'].sum():.4%}")
        logger.info(f"  成本拖累年化: {results['cost_series'].sum() / len(results['cost_series']) * self.periods_per_year:.4%}")

        # 绩效指标（含成本）
        logger.info("\n" + "-"*70)
        logger.info("绩效指标（含交易成本）")
        logger.info("-"*70)
        self.metrics_calculator.print_metrics(results['metrics'])

        # 绩效指标（不含成本）
        logger.info("\n" + "-"*70)
        logger.info("绩效指标（不含交易成本）")
        logger.info("-"*70)
        self.metrics_calculator.print_metrics(results['metrics_no_cost'])

        # 成本影响分析
        logger.info("\n" + "-"*70)
        logger.info("交易成本影响分析")
        logger.info("-"*70)

        annual_return_loss = results['metrics']['annual_return'] - results['metrics_no_cost']['annual_return']
        sharpe_loss = results['metrics']['sharpe_ratio'] - results['metrics_no_cost']['sharpe_ratio']

        logger.info(f"  年化收益损失: {annual_return_loss:.2%}")
        logger.info(f"  Sharpe损失:   {sharpe_loss:.2f}")
        if results['metrics_no_cost']['annual_return'] != 0:
            logger.info(f"  成本占比:     {abs(annual_return_loss / results['metrics_no_cost']['annual_return']):.1%}")
