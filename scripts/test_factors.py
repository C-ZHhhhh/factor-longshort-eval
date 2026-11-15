"""
测试因子计算模块

验证5个因子的计算和预处理功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from factors import (
    MomentumFactor,
    ReversalFactor,
    LowVolatilityFactor,
    TrendFactor,
    LiquidityFactor,
    FactorProcessor,
    FactorCombiner,
)
from utils.logger import get_logger
from data.data_loader import DataLoader

logger = get_logger(__name__)


def test_factors():
    """测试所有因子"""

    logger.info("="*70)
    logger.info("开始测试因子计算模块")
    logger.info("="*70)

    # 1. 加载数据
    logger.info("\n1. 加载数据...")
    cache_file = DataLoader().latest_cache_file()  # 最新的缓存文件, 不写死文件名
    cache_data = pd.read_pickle(cache_file)

    df_price = cache_data['price']
    df_return_daily = cache_data['return_daily']

    # 成交量用缓存里的真实数据; 旧缓存没有时退回恒定值(仅保证能跑, 此时流动性因子没有意义)
    df_volume = cache_data.get('volume')
    if df_volume is None:
        logger.warning("缓存中没有成交量数据, 使用恒定成交量, 流动性因子结果无意义")
        df_volume = pd.DataFrame(
            100000.0,
            index=df_price.index,
            columns=df_price.columns
        )

    logger.info(f"价格数据: {df_price.shape}")
    logger.info(f"日收益率: {df_return_daily.shape}")

    # 2. 计算5个因子
    logger.info("\n2. 计算5个因子...")

    factors_dict = {}

    # 动量因子
    logger.info("\n--- 动量因子 ---")
    momentum = MomentumFactor()
    df_momentum = momentum.calculate(df_price)
    factors_dict['Momentum'] = df_momentum
    logger.info(f"形状: {df_momentum.shape}")
    logger.info(f"样本值:\n{df_momentum.iloc[:3, :5]}")

    # 反转因子
    logger.info("\n--- 反转因子 ---")
    reversal = ReversalFactor()
    df_reversal = reversal.calculate(df_price)
    factors_dict['Reversal'] = df_reversal
    logger.info(f"形状: {df_reversal.shape}")
    logger.info(f"样本值:\n{df_reversal.iloc[:3, :5]}")

    # 低波因子
    logger.info("\n--- 低波因子 ---")
    low_vol = LowVolatilityFactor()
    df_low_vol = low_vol.calculate(df_price, df_return_daily=df_return_daily)
    factors_dict['LowVolatility'] = df_low_vol
    logger.info(f"形状: {df_low_vol.shape}")
    logger.info(f"样本值:\n{df_low_vol.iloc[:3, :5]}")

    # 趋势因子
    logger.info("\n--- 趋势因子 ---")
    trend = TrendFactor()
    df_trend = trend.calculate(df_price)
    factors_dict['Trend'] = df_trend
    logger.info(f"形状: {df_trend.shape}")
    logger.info(f"样本值:\n{df_trend.iloc[:3, :5]}")

    # 流动性因子
    logger.info("\n--- 流动性因子 ---")
    liquidity = LiquidityFactor()
    df_liquidity = liquidity.calculate(df_price, df_volume=df_volume)
    factors_dict['Liquidity'] = df_liquidity
    logger.info(f"形状: {df_liquidity.shape}")
    logger.info(f"样本值:\n{df_liquidity.iloc[:3, :5]}")

    # 3. 测试因子预处理
    logger.info("\n3. 测试因子预处理...")

    processor = FactorProcessor(winsorize_limits=(0.01, 0.99), standardize=True)

    # 预处理动量因子
    logger.info("\n--- 预处理动量因子 ---")
    df_momentum_processed = processor.process(df_momentum)
    logger.info(f"形状: {df_momentum_processed.shape}")

    # 验证标准化效果
    sample_date = df_momentum_processed.index[50]
    sample_values = df_momentum_processed.loc[sample_date].dropna()
    logger.info(f"标准化验证 ({sample_date}):")
    logger.info(f"  均值: {sample_values.mean():.6f}")
    logger.info(f"  标准差: {sample_values.std():.6f}")
    logger.info(f"  最小值: {sample_values.min():.2f}")
    logger.info(f"  最大值: {sample_values.max():.2f}")

    # 预处理所有因子
    processed_factors = {}
    for name, factor in factors_dict.items():
        logger.info(f"\n预处理 {name} 因子...")
        processed_factors[name] = processor.process(factor)

    # 4. 测试因子合成
    logger.info("\n4. 测试因子合成...")

    combiner = FactorCombiner(method='equal_weight')
    df_composite = combiner.combine_dict(processed_factors)

    logger.info(f"合成因子形状: {df_composite.shape}")
    logger.info(f"样本值:\n{df_composite.iloc[:5, :5]}")

    # 5. 汇总统计
    logger.info("\n5. 因子统计汇总")
    logger.info("="*70)

    summary_data = []
    for name, factor in factors_dict.items():
        processed = processed_factors[name]

        summary_data.append({
            '因子': name,
            '时间跨度': f"{factor.index[0].strftime('%Y-%m')} ~ {factor.index[-1].strftime('%Y-%m')}",
            '月数': len(factor),
            '股票数': len(factor.columns),
            '原始缺失率': f"{factor.isna().sum().sum() / factor.size:.2%}",
            '处理后缺失率': f"{processed.isna().sum().sum() / processed.size:.2%}",
        })

    summary_df = pd.DataFrame(summary_data)
    logger.info(f"\n{summary_df.to_string(index=False)}")

    # 合成因子统计
    logger.info(f"\n合成因子:")
    logger.info(f"  时间跨度: {df_composite.index[0].strftime('%Y-%m')} ~ {df_composite.index[-1].strftime('%Y-%m')}")
    logger.info(f"  月数: {len(df_composite)}")
    logger.info(f"  股票数: {len(df_composite.columns)}")
    logger.info(f"  缺失率: {df_composite.isna().sum().sum() / df_composite.size:.2%}")

    logger.info("\n" + "="*70)
    logger.info("✅ 因子计算模块测试通过!")
    logger.info("="*70)

    return {
        'raw_factors': factors_dict,
        'processed_factors': processed_factors,
        'composite_factor': df_composite,
    }


if __name__ == '__main__':
    results = test_factors()
