"""
测试回测引擎

测试完整的回测流程:
1. 加载数据
2. 计算因子
3. 构建组合
4. 运行回测
5. 验证结果
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


def main():
    logger.info("="*70)
    logger.info("开始测试回测引擎")
    logger.info("="*70)

    # 1. 加载数据
    logger.info("\n1. 加载数据...")
    cache_file = 'data/cache/clean_data_2015-01-01_2026-02-03_503_dedup.pkl'
    cache_data = pd.read_pickle(cache_file)

    df_price_monthly = cache_data['price']  # 已经是月度数据
    df_return_daily = cache_data['return_daily']

    # 计算月度收益率
    df_return_monthly = df_price_monthly.pct_change()

    # 假设成交量（仅用于因子计算）
    df_volume_daily = pd.DataFrame(
        100000.0,
        index=df_return_daily.index,
        columns=df_return_daily.columns
    )

    logger.info(f"月度价格: {df_price_monthly.shape}")
    logger.info(f"月度收益: {df_return_monthly.shape}")

    # 2. 计算因子（使用动量因子作为示例）
    logger.info("\n2. 计算因子...")
    momentum = MomentumFactor()
    df_factor = momentum.calculate(df_price_monthly, df_volume_daily, df_return_daily)
    logger.info(f"因子形状: {df_factor.shape}")

    # 3. 标准化因子
    logger.info("\n3. 标准化因子...")
    processor = FactorProcessor()
    df_factor_processed = processor.winsorize(df_factor)
    df_factor_processed = processor.zscore_standardize(df_factor_processed)

    # 验证标准化
    logger.info("验证标准化效果...")
    mean_by_date = df_factor_processed.mean(axis=1)
    std_by_date = df_factor_processed.std(axis=1)
    logger.info(f"  均值范围: [{mean_by_date.min():.6f}, {mean_by_date.max():.6f}]")
    logger.info(f"  标准差范围: [{std_by_date.min():.6f}, {std_by_date.max():.6f}]")

    # 4. 构建组合
    logger.info("\n4. 构建组合...")
    builder = PortfolioBuilder(quantile=0.2)
    df_holdings = builder.build(df_factor_processed)
    logger.info(f"持仓形状: {df_holdings.shape}")

    # 5. 分配权重
    logger.info("\n5. 分配权重...")
    weighting = WeightingScheme()
    df_weights = weighting.assign_weights(df_holdings)
    logger.info(f"权重形状: {df_weights.shape}")

    # 6. 中性化
    logger.info("\n6. 中性化...")
    neutralizer = Neutralizer()
    df_weights_neutral = neutralizer.market_neutral(df_weights)

    # 验证中性化
    weight_sums = df_weights_neutral.sum(axis=1)
    logger.info(f"权重和范围: [{weight_sums.min():.10f}, {weight_sums.max():.10f}]")

    if weight_sums.abs().max() < 1e-10:
        logger.info("✅ 中性化验证通过: 所有期数权重和 = 0")
    else:
        logger.warning(f"⚠️  中性化验证失败: 最大偏差 = {weight_sums.abs().max()}")

    # 7. 运行回测
    logger.info("\n7. 运行回测...")
    engine = BacktestEngine(cost_bps=20.0, periods_per_year=12)

    results = engine.run(
        df_weights=df_weights_neutral,
        df_return=df_return_monthly,
        align_time=True  # 启用时间对齐，防look-ahead
    )

    # 8. 验证结果
    logger.info("\n" + "="*70)
    logger.info("验证回测结果")
    logger.info("="*70)

    # 8.1 净值曲线检查
    logger.info("\n净值曲线检查:")
    nav = results['nav']
    nav_no_cost = results['nav_no_cost']

    logger.info(f"  初始净值: {nav.iloc[0]:.4f}")
    logger.info(f"  最终净值(含成本): {nav.iloc[-1]:.4f}")
    logger.info(f"  最终净值(不含成本): {nav_no_cost.iloc[-1]:.4f}")
    logger.info(f"  总收益(含成本): {(nav.iloc[-1] / nav.iloc[0] - 1):.2%}")
    logger.info(f"  总收益(不含成本): {(nav_no_cost.iloc[-1] / nav_no_cost.iloc[0] - 1):.2%}")

    # 检查净值单调性（不应该有异常跳变）
    nav_pct_change = nav.pct_change().dropna()
    if nav_pct_change.abs().max() > 0.5:
        logger.warning(f"⚠️  净值有异常跳变: 最大单期变化 = {nav_pct_change.abs().max():.2%}")
    else:
        logger.info(f"✅ 净值曲线正常: 最大单期变化 = {nav_pct_change.abs().max():.2%}")

    # 8.2 收益率检查
    logger.info("\n收益率检查:")
    returns = results['returns']
    returns_no_cost = results['returns_no_cost']

    logger.info(f"  平均月收益(含成本): {returns.mean():.4%}")
    logger.info(f"  平均月收益(不含成本): {returns_no_cost.mean():.4%}")
    logger.info(f"  收益率标准差: {returns.std():.4%}")
    logger.info(f"  胜率(含成本): {(returns > 0).sum() / len(returns):.2%}")
    logger.info(f"  胜率(不含成本): {(returns_no_cost > 0).sum() / len(returns_no_cost):.2%}")

    # 8.3 换手率检查
    logger.info("\n换手率检查:")
    turnover = results['turnover']
    logger.info(f"  平均换手率: {turnover.mean():.2%}")
    logger.info(f"  中位数换手率: {turnover.median():.2%}")
    logger.info(f"  换手率范围: [{turnover.min():.2%}, {turnover.max():.2%}]")

    if turnover.mean() > 1.0:
        logger.warning("⚠️  平均换手率 > 100%, 可能过于频繁")
    elif turnover.mean() < 0.1:
        logger.warning("⚠️  平均换手率 < 10%, 可能过于稳定")
    else:
        logger.info("✅ 换手率在合理范围内")

    # 8.4 绩效指标检查
    logger.info("\n绩效指标检查:")
    metrics = results['metrics']
    metrics_no_cost = results['metrics_no_cost']

    logger.info(f"  年化收益(含成本): {metrics['annual_return']:.2%}")
    logger.info(f"  年化收益(不含成本): {metrics_no_cost['annual_return']:.2%}")
    logger.info(f"  年化波动率: {metrics['annual_volatility']:.2%}")
    logger.info(f"  Sharpe(含成本): {metrics['sharpe_ratio']:.2f}")
    logger.info(f"  Sharpe(不含成本): {metrics_no_cost['sharpe_ratio']:.2f}")
    logger.info(f"  最大回撤(含成本): {metrics['max_drawdown']:.2%}")
    logger.info(f"  Calmar(含成本): {metrics['calmar_ratio']:.2f}")

    # 合理性检查
    logger.info("\n合理性检查:")

    checks = []

    # 年化收益检查
    if -0.3 <= metrics['annual_return'] <= 0.5:
        checks.append(("✅ 年化收益", f"{metrics['annual_return']:.2%}", "在合理范围内"))
    else:
        checks.append(("⚠️  年化收益", f"{metrics['annual_return']:.2%}", "可能异常"))

    # Sharpe检查
    if -1.0 <= metrics['sharpe_ratio'] <= 3.0:
        checks.append(("✅ Sharpe比率", f"{metrics['sharpe_ratio']:.2f}", "在合理范围内"))
    else:
        checks.append(("⚠️  Sharpe比率", f"{metrics['sharpe_ratio']:.2f}", "可能异常"))

    # 最大回撤检查
    if -0.5 <= metrics['max_drawdown'] <= 0.0:
        checks.append(("✅ 最大回撤", f"{metrics['max_drawdown']:.2%}", "在合理范围内"))
    else:
        checks.append(("⚠️  最大回撤", f"{metrics['max_drawdown']:.2%}", "可能异常"))

    # 换手率检查
    if 0.1 <= turnover.mean() <= 1.0:
        checks.append(("✅ 平均换手率", f"{turnover.mean():.2%}", "在合理范围内"))
    else:
        checks.append(("⚠️  平均换手率", f"{turnover.mean():.2%}", "可能异常"))

    # 成本合理性检查
    cost_impact = metrics['annual_return'] - metrics_no_cost['annual_return']
    expected_cost = turnover.mean() * 12 * 0.002  # 20bps
    if abs(cost_impact + expected_cost) / expected_cost < 0.2:  # 允许20%误差
        checks.append(("✅ 成本计算", f"{-cost_impact:.2%}", "与预期相符"))
    else:
        checks.append(("⚠️  成本计算", f"{-cost_impact:.2%}", f"预期约{expected_cost:.2%}"))

    for check in checks:
        logger.info(f"  {check[0]}: {check[1]} - {check[2]}")

    # 8.5 Look-ahead bias检查
    logger.info("\nLook-ahead bias检查:")
    logger.info("  通过时间对齐 (shift 1期) 防止未来信息泄露")
    logger.info("  因子在t期末计算，用于预测t+1期收益")

    # 检查是否存在异常高的IC（可能暗示look-ahead）
    # 这里简单检查，如果Sharpe > 3.0可能有问题
    if metrics_no_cost['sharpe_ratio'] > 3.0:
        logger.warning(f"⚠️  Sharpe过高({metrics_no_cost['sharpe_ratio']:.2f})，请检查是否有look-ahead bias")
    else:
        logger.info(f"✅ Sharpe在合理范围，无明显look-ahead bias迹象")

    # 9. 保存结果
    logger.info("\n9. 保存测试结果...")
    results['nav'].to_csv('results/test_nav.csv')
    results['returns'].to_csv('results/test_returns.csv')
    results['turnover'].to_csv('results/test_turnover.csv')

    # 保存绩效指标
    metrics_df = pd.DataFrame({
        '含成本': pd.Series(metrics),
        '不含成本': pd.Series(metrics_no_cost)
    })
    metrics_df.to_csv('results/test_metrics.csv')
    logger.info("结果已保存到 results/ 目录")

    logger.info("\n" + "="*70)
    logger.info("回测引擎测试完成！")
    logger.info("="*70)

    return results


if __name__ == '__main__':
    main()
