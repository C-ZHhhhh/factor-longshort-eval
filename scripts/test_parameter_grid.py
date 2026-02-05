"""
测试不同参数组合的回测效果

测试内容:
1. 调仓频率: monthly / 2monthly / quarterly
2. 最小持有期: 6 / 12 / 18 / 24 月
3. 进入/退出阈值: 固定为 25%/30%

目标: 找到最优参数组合以提升回测表现
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from utils.logger import get_logger
from factors.momentum import MomentumFactor
from factors.factor_processor import FactorProcessor
from portfolio.portfolio_builder import PortfolioBuilder
from portfolio.weighting import WeightingScheme
from portfolio.neutralization import Neutralizer
from backtest.engine import BacktestEngine

logger = get_logger(__name__)


def run_single_backtest(
    df_factor,
    df_return_monthly,
    entry_quantile=0.25,
    exit_quantile=0.30,
    min_holding_periods=6,
    rebalance_freq='monthly',
    cost_bps=20.0
):
    """
    运行单次回测

    Args:
        df_factor: 因子值
        df_return_monthly: 月度收益率
        entry_quantile: 进入阈值
        exit_quantile: 退出阈值
        min_holding_periods: 最小持有期
        rebalance_freq: 调仓频率
        cost_bps: 交易成本

    Returns:
        回测结果
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"参数配置:")
    logger.info(f"  进入阈值: {entry_quantile:.0%}")
    logger.info(f"  退出阈值: {exit_quantile:.0%}")
    logger.info(f"  最小持有期: {min_holding_periods}月")
    logger.info(f"  调仓频率: {rebalance_freq}")
    logger.info(f"  交易成本: {cost_bps} bps")
    logger.info(f"{'='*70}")

    # 1. 构建组合
    builder = PortfolioBuilder(
        entry_quantile=entry_quantile,
        exit_quantile=exit_quantile,
        min_holding_periods=min_holding_periods,
        long_top=True
    )
    df_holdings = builder.build(df_factor)

    # 2. 分配权重
    weighting = WeightingScheme()
    df_weights = weighting.assign_weights(df_holdings)

    # 3. 中性化
    neutralizer = Neutralizer()
    df_weights_neutral = neutralizer.market_neutral(df_weights)

    # 4. 运行回测
    engine = BacktestEngine(
        cost_bps=cost_bps,
        periods_per_year=12,
        rebalance_freq=rebalance_freq
    )

    results = engine.run(
        df_weights=df_weights_neutral,
        df_return=df_return_monthly,
        align_time=True
    )

    return results


def main():
    logger.info("="*70)
    logger.info("开始参数网格搜索测试")
    logger.info("="*70)

    # 1. 加载数据
    logger.info("\n1. 加载数据...")
    cache_file = 'data/cache/clean_data_2015-01-01_2026-02-03_503_dedup.pkl'
    cache_data = pd.read_pickle(cache_file)

    df_price_monthly = cache_data['price']
    df_return_daily = cache_data['return_daily']
    df_return_monthly = df_price_monthly.pct_change()

    df_volume_daily = pd.DataFrame(
        100000.0,
        index=df_return_daily.index,
        columns=df_return_daily.columns
    )

    logger.info(f"月度价格: {df_price_monthly.shape}")
    logger.info(f"月度收益: {df_return_monthly.shape}")

    # 2. 计算因子（使用动量因子）
    logger.info("\n2. 计算动量因子...")
    momentum = MomentumFactor()
    df_factor = momentum.calculate(df_price_monthly, df_volume_daily, df_return_daily)

    # 3. 标准化因子
    logger.info("\n3. 标准化因子...")
    processor = FactorProcessor()
    df_factor_processed = processor.winsorize(df_factor)
    df_factor_processed = processor.zscore_standardize(df_factor_processed)

    # 4. 参数网格
    logger.info("\n4. 定义参数网格...")

    # 固定参数
    entry_quantile = 0.25
    exit_quantile = 0.30
    cost_bps = 20.0

    # 变动参数
    min_holding_periods_list = [6, 12, 18, 24]
    rebalance_freq_list = ['monthly', '2monthly', 'quarterly']

    logger.info(f"  进入阈值(固定): {entry_quantile:.0%}")
    logger.info(f"  退出阈值(固定): {exit_quantile:.0%}")
    logger.info(f"  最小持有期: {min_holding_periods_list}")
    logger.info(f"  调仓频率: {rebalance_freq_list}")
    logger.info(f"  总测试组合数: {len(min_holding_periods_list) * len(rebalance_freq_list)}")

    # 5. 运行参数网格搜索
    logger.info("\n5. 开始参数网格搜索...")

    results_summary = []

    for rebalance_freq in rebalance_freq_list:
        for min_holding_periods in min_holding_periods_list:
            logger.info(f"\n{'='*70}")
            logger.info(f"测试组合: rebalance_freq={rebalance_freq}, min_holding={min_holding_periods}月")
            logger.info(f"{'='*70}")

            try:
                results = run_single_backtest(
                    df_factor=df_factor_processed,
                    df_return_monthly=df_return_monthly,
                    entry_quantile=entry_quantile,
                    exit_quantile=exit_quantile,
                    min_holding_periods=min_holding_periods,
                    rebalance_freq=rebalance_freq,
                    cost_bps=cost_bps
                )

                # 提取关键指标
                metrics = results['metrics']
                metrics_no_cost = results['metrics_no_cost']
                turnover = results['turnover']

                summary = {
                    'rebalance_freq': rebalance_freq,
                    'min_holding_periods': min_holding_periods,
                    'annual_return': metrics['annual_return'],
                    'annual_return_no_cost': metrics_no_cost['annual_return'],
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'sharpe_ratio_no_cost': metrics_no_cost['sharpe_ratio'],
                    'max_drawdown': metrics['max_drawdown'],
                    'avg_turnover': turnover.mean(),
                    'rebalance_count': (turnover > 0).sum(),
                    'total_cost': results['cost_series'].sum(),
                }

                results_summary.append(summary)

                logger.info(f"\n关键指标汇总:")
                logger.info(f"  年化收益(含成本): {summary['annual_return']:.2%}")
                logger.info(f"  Sharpe(含成本): {summary['sharpe_ratio']:.2f}")
                logger.info(f"  最大回撤: {summary['max_drawdown']:.2%}")
                logger.info(f"  平均换手率: {summary['avg_turnover']:.2%}")
                logger.info(f"  调仓次数: {summary['rebalance_count']}")

            except Exception as e:
                logger.error(f"测试失败: {e}")
                import traceback
                traceback.print_exc()
                continue

    # 6. 汇总结果
    logger.info("\n" + "="*70)
    logger.info("参数网格搜索结果汇总")
    logger.info("="*70)

    df_summary = pd.DataFrame(results_summary)

    # 按Sharpe排序
    df_summary_sorted = df_summary.sort_values('sharpe_ratio', ascending=False)

    logger.info(f"\n完整结果表(按Sharpe排序):")
    logger.info("\n" + df_summary_sorted.to_string(index=False))

    # 保存结果
    df_summary_sorted.to_csv('results/parameter_grid_search.csv', index=False)
    logger.info(f"\n✅ 结果已保存到: results/parameter_grid_search.csv")

    # 7. 找出最优参数
    best_row = df_summary_sorted.iloc[0]

    logger.info(f"\n" + "="*70)
    logger.info("🏆 最优参数组合")
    logger.info("="*70)
    logger.info(f"  调仓频率: {best_row['rebalance_freq']}")
    logger.info(f"  最小持有期: {best_row['min_holding_periods']:.0f}月")
    logger.info(f"  年化收益(含成本): {best_row['annual_return']:.2%}")
    logger.info(f"  Sharpe(含成本): {best_row['sharpe_ratio']:.2f}")
    logger.info(f"  最大回撤: {best_row['max_drawdown']:.2%}")
    logger.info(f"  平均换手率: {best_row['avg_turnover']:.2%}")
    logger.info(f"  调仓次数: {best_row['rebalance_count']:.0f}")

    # 8. 与基准对比
    logger.info(f"\n" + "="*70)
    logger.info("📊 改进效果对比")
    logger.info("="*70)

    # 假设基准是: monthly调仓 + 6月最小持有期
    baseline = df_summary[
        (df_summary['rebalance_freq'] == 'monthly') &
        (df_summary['min_holding_periods'] == 6)
    ]

    if len(baseline) > 0:
        baseline = baseline.iloc[0]
        logger.info(f"\n基准策略(monthly, 6月):")
        logger.info(f"  年化收益: {baseline['annual_return']:.2%}")
        logger.info(f"  Sharpe: {baseline['sharpe_ratio']:.2f}")
        logger.info(f"  换手率: {baseline['avg_turnover']:.2%}")

        logger.info(f"\n最优策略:")
        logger.info(f"  年化收益: {best_row['annual_return']:.2%}")
        logger.info(f"  Sharpe: {best_row['sharpe_ratio']:.2f}")
        logger.info(f"  换手率: {best_row['avg_turnover']:.2%}")

        logger.info(f"\n改进幅度:")
        return_improvement = best_row['annual_return'] - baseline['annual_return']
        sharpe_improvement = best_row['sharpe_ratio'] - baseline['sharpe_ratio']
        turnover_reduction = baseline['avg_turnover'] - best_row['avg_turnover']

        logger.info(f"  年化收益提升: {return_improvement:+.2%}")
        logger.info(f"  Sharpe提升: {sharpe_improvement:+.2f}")
        logger.info(f"  换手率降低: {turnover_reduction:.2%}")

    logger.info("\n" + "="*70)
    logger.info("参数网格搜索完成！")
    logger.info("="*70)


if __name__ == '__main__':
    main()
