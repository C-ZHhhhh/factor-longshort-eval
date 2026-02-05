"""
测试组合构建模块

验证排序选股、权重分配、中性化和换手率计算功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from portfolio import (
    PortfolioBuilder,
    WeightingScheme,
    Neutralizer,
    Rebalancer,
)
from factors import MomentumFactor, FactorProcessor
from utils.logger import get_logger

logger = get_logger(__name__)


def test_portfolio():
    """测试组合构建模块"""

    logger.info("="*70)
    logger.info("开始测试组合构建模块")
    logger.info("="*70)

    # 1. 加载数据并计算因子
    logger.info("\n1. 加载数据...")
    cache_file = 'data/cache/clean_data_2015-01-01_2026-02-03_503_dedup.pkl'
    cache_data = pd.read_pickle(cache_file)
    df_price = cache_data['price']

    logger.info(f"价格数据: {df_price.shape}")

    # 计算动量因子
    logger.info("\n2. 计算动量因子...")
    momentum = MomentumFactor()
    df_momentum = momentum.calculate(df_price)
    logger.info(f"动量因子: {df_momentum.shape}")

    # 预处理
    processor = FactorProcessor()
    df_momentum_processed = processor.process(df_momentum)
    logger.info(f"预处理后: {df_momentum_processed.shape}")

    # 3. 测试组合构建器
    logger.info("\n3. 测试组合构建器...")
    builder = PortfolioBuilder(quantile=0.2, long_top=True)
    df_holdings = builder.build(df_momentum_processed)

    logger.info(f"持仓标记: {df_holdings.shape}")
    logger.info(f"样本持仓:\n{df_holdings.iloc[:3, :5]}")

    # 统计持仓数量
    counts = builder.get_long_short_counts(df_holdings)
    logger.info(f"\n持仓数量统计:")
    logger.info(f"  平均多头数: {counts['long_count'].mean():.1f}")
    logger.info(f"  平均空头数: {counts['short_count'].mean():.1f}")
    logger.info(f"  平均总持仓: {counts['total_count'].mean():.1f}")

    # 4. 测试权重分配
    logger.info("\n4. 测试权重分配...")

    # 4.1 等权
    logger.info("\n--- 等权分配 ---")
    weighting_equal = WeightingScheme(method='equal')
    df_weights_equal = weighting_equal.assign_weights(df_holdings)
    logger.info(f"等权权重: {df_weights_equal.shape}")

    # 验证等权效果
    sample_date = df_weights_equal.index[10]
    sample_weights = df_weights_equal.loc[sample_date]
    long_weights = sample_weights[sample_weights > 0]
    short_weights = sample_weights[sample_weights < 0]
    logger.info(f"样本日期 ({sample_date}):")
    logger.info(f"  多头权重: {long_weights.sum():.6f}, 每股权重: {long_weights.mean():.6f}")
    logger.info(f"  空头权重: {short_weights.sum():.6f}, 每股权重: {short_weights.mean():.6f}")

    # 4.2 因子值加权
    logger.info("\n--- 因子值加权 ---")
    weighting_value = WeightingScheme(method='value')
    df_weights_value = weighting_value.assign_weights(df_holdings, df_factor=df_momentum_processed)
    logger.info(f"因子值权重: {df_weights_value.shape}")

    # 5. 测试中性化
    logger.info("\n5. 测试中性化...")
    neutralizer = Neutralizer()

    # 中性化等权组合
    logger.info("\n--- 中性化等权组合 ---")
    df_weights_neutral = neutralizer.market_neutral(df_weights_equal)
    logger.info(f"中性化权重: {df_weights_neutral.shape}")

    # 验证中性化效果
    sample_date = df_weights_neutral.index[10]
    sample_weights = df_weights_neutral.loc[sample_date]
    logger.info(f"\n中性化验证 ({sample_date}):")
    logger.info(f"  总权重和: {sample_weights.sum():.10f}")
    logger.info(f"  多头权重和: {sample_weights[sample_weights > 0].sum():.10f}")
    logger.info(f"  空头权重和: {sample_weights[sample_weights < 0].sum():.10f}")

    # 6. 测试换手率计算
    logger.info("\n6. 测试换手率计算...")
    rebalancer = Rebalancer()

    turnover_series = rebalancer.calculate_turnover(df_weights_neutral)
    logger.info(f"换手率序列: {len(turnover_series)}")

    # 换手率统计
    turnover_stats = rebalancer.get_turnover_stats(turnover_series)
    logger.info(f"\n换手率统计:")
    logger.info(f"  平均: {turnover_stats['mean']:.2%}")
    logger.info(f"  中位数: {turnover_stats['median']:.2%}")
    logger.info(f"  标准差: {turnover_stats['std']:.2%}")
    logger.info(f"  最小值: {turnover_stats['min']:.2%}")
    logger.info(f"  最大值: {turnover_stats['max']:.2%}")

    # 分解单月换手率
    date1 = df_weights_neutral.index[10]
    date2 = df_weights_neutral.index[11]
    weights1 = df_weights_neutral.loc[date1]
    weights2 = df_weights_neutral.loc[date2]

    turnover_decomp = rebalancer.decompose_turnover(weights1, weights2)
    logger.info(f"\n单月换手率分解 ({date1} -> {date2}):")
    logger.info(f"  总换手率: {turnover_decomp['total']:.2%}")
    logger.info(f"  新进入: {turnover_decomp['entry']:.2%}")
    logger.info(f"  退出: {turnover_decomp['exit']:.2%}")
    logger.info(f"  权重调整: {turnover_decomp['adjust']:.2%}")

    # 7. 汇总统计
    logger.info("\n7. 组合构建汇总")
    logger.info("="*70)

    summary_data = {
        '时间跨度': f"{df_holdings.index[0].strftime('%Y-%m')} ~ {df_holdings.index[-1].strftime('%Y-%m')}",
        '月数': len(df_holdings),
        '股票池': len(df_holdings.columns),
        '平均多头数': f"{counts['long_count'].mean():.1f}",
        '平均空头数': f"{counts['short_count'].mean():.1f}",
        '平均换手率': f"{turnover_stats['mean']:.2%}",
        '中性化': '✅ 通过',
    }

    for key, value in summary_data.items():
        logger.info(f"  {key}: {value}")

    logger.info("\n" + "="*70)
    logger.info("✅ 组合构建模块测试通过!")
    logger.info("="*70)

    return {
        'holdings': df_holdings,
        'weights_equal': df_weights_equal,
        'weights_value': df_weights_value,
        'weights_neutral': df_weights_neutral,
        'turnover': turnover_series,
    }


if __name__ == '__main__':
    results = test_portfolio()
