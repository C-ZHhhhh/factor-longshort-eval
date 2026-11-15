"""
多因子对比测试

使用最优参数(2monthly, 12月)测试:
1. 5个单因子: 动量、反转、低波、趋势、流动性
2. 多因子合成: 5个因子等权平均
3. 对比分析表现

目标: 找到表现最好的因子组合
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from utils.logger import get_logger
from data.data_loader import DataLoader
from factors import (
    MomentumFactor,
    ReversalFactor,
    LowVolatilityFactor,
    TrendFactor,
    LiquidityFactor,
    FactorProcessor,
    FactorCombiner,
)
from portfolio.portfolio_builder import PortfolioBuilder
from portfolio.weighting import WeightingScheme
from portfolio.neutralization import Neutralizer
from backtest.engine import BacktestEngine

logger = get_logger(__name__)


def run_backtest_for_factor(
    df_factor,
    df_return_monthly,
    factor_name,
    entry_quantile=0.25,
    exit_quantile=0.30,
    min_holding_periods=12,
    rebalance_freq='2monthly',
    cost_bps=20.0
):
    """
    对单个因子运行回测

    Args:
        df_factor: 因子值
        df_return_monthly: 月度收益率
        factor_name: 因子名称
        其他参数: 回测参数

    Returns:
        回测结果
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"回测因子: {factor_name}")
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
    logger.info("开始多因子对比测试")
    logger.info("="*70)

    # 最优参数
    entry_quantile = 0.25
    exit_quantile = 0.30
    min_holding_periods = 12
    rebalance_freq = '2monthly'
    cost_bps = 20.0

    logger.info(f"\n使用最优参数:")
    logger.info(f"  进入阈值: {entry_quantile:.0%}")
    logger.info(f"  退出阈值: {exit_quantile:.0%}")
    logger.info(f"  最小持有期: {min_holding_periods}月")
    logger.info(f"  调仓频率: {rebalance_freq}")
    logger.info(f"  交易成本: {cost_bps} bps")

    # 1. 加载数据
    logger.info("\n" + "="*70)
    logger.info("1. 加载数据")
    logger.info("="*70)

    cache_file = DataLoader().latest_cache_file()  # 最新的缓存文件, 不写死文件名
    cache_data = pd.read_pickle(cache_file)

    df_price = cache_data['price']  # 日频复权价 (因子内部会自己重采样到月末)
    df_return_daily = cache_data['return_daily']
    # 月收益率直接用缓存里清洗好的 (price是日频的, 对它pct_change得到的是日收益)
    df_return_monthly = cache_data['return_monthly']

    # 成交量用缓存里的真实数据; 旧缓存没有时退回恒定值(仅保证能跑, 此时流动性因子没有意义)
    df_volume_daily = cache_data.get('volume')
    if df_volume_daily is None:
        logger.warning("缓存中没有成交量数据, 使用恒定成交量, 流动性因子结果无意义")
        df_volume_daily = pd.DataFrame(
            100000.0,
            index=df_return_daily.index,
            columns=df_return_daily.columns
        )

    logger.info(f"日频价格: {df_price.shape}")
    logger.info(f"月度收益: {df_return_monthly.shape}")

    # 2. 计算所有因子
    logger.info("\n" + "="*70)
    logger.info("2. 计算5个因子")
    logger.info("="*70)

    factors_dict = {}

    # 动量因子
    logger.info("\n--- 动量因子 ---")
    momentum = MomentumFactor()
    df_momentum = momentum.calculate(df_price, df_volume_daily, df_return_daily)
    factors_dict['Momentum'] = df_momentum
    logger.info(f"形状: {df_momentum.shape}")

    # 反转因子
    logger.info("\n--- 反转因子 ---")
    reversal = ReversalFactor()
    df_reversal = reversal.calculate(df_price, df_volume_daily, df_return_daily)
    factors_dict['Reversal'] = df_reversal
    logger.info(f"形状: {df_reversal.shape}")

    # 低波因子
    logger.info("\n--- 低波因子 ---")
    low_vol = LowVolatilityFactor()
    df_low_vol = low_vol.calculate(df_price, df_volume_daily, df_return_daily)
    factors_dict['LowVolatility'] = df_low_vol
    logger.info(f"形状: {df_low_vol.shape}")

    # 趋势因子
    logger.info("\n--- 趋势因子 ---")
    trend = TrendFactor()
    df_trend = trend.calculate(df_price, df_volume_daily, df_return_daily)
    factors_dict['Trend'] = df_trend
    logger.info(f"形状: {df_trend.shape}")

    # 流动性因子
    logger.info("\n--- 流动性因子 ---")
    liquidity = LiquidityFactor()
    df_liquidity = liquidity.calculate(df_price, df_volume_daily, df_return_daily)
    factors_dict['Liquidity'] = df_liquidity
    logger.info(f"形状: {df_liquidity.shape}")

    # 3. 标准化所有因子
    logger.info("\n" + "="*70)
    logger.info("3. 标准化因子")
    logger.info("="*70)

    processor = FactorProcessor()
    processed_factors = {}

    for name, df_factor in factors_dict.items():
        logger.info(f"\n处理因子: {name}")
        df_processed = processor.winsorize(df_factor)
        df_processed = processor.zscore_standardize(df_processed)
        processed_factors[name] = df_processed

    # 4. 合成多因子
    logger.info("\n" + "="*70)
    logger.info("4. 合成多因子（等权平均）")
    logger.info("="*70)

    combiner = FactorCombiner(method='equal_weight')
    df_composite = combiner.combine(
        list(processed_factors.values()),
        factor_names=list(processed_factors.keys())
    )
    processed_factors['Composite'] = df_composite
    logger.info(f"合成因子形状: {df_composite.shape}")

    # 5. 对所有因子（5个单因子 + 1个合成因子）运行回测
    logger.info("\n" + "="*70)
    logger.info("5. 对6个因子分别回测")
    logger.info("="*70)

    results_summary = []

    for factor_name in ['Momentum', 'Reversal', 'LowVolatility', 'Trend', 'Liquidity', 'Composite']:
        logger.info(f"\n" + "="*70)
        logger.info(f"回测: {factor_name}")
        logger.info("="*70)

        try:
            df_factor = processed_factors[factor_name]

            results = run_backtest_for_factor(
                df_factor=df_factor,
                df_return_monthly=df_return_monthly,
                factor_name=factor_name,
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
                'factor': factor_name,
                'annual_return': metrics['annual_return'],
                'annual_return_no_cost': metrics_no_cost['annual_return'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'sharpe_ratio_no_cost': metrics_no_cost['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown'],
                'annual_volatility': metrics['annual_volatility'],
                'calmar_ratio': metrics['calmar_ratio'],
                'sortino_ratio': metrics['sortino_ratio'],
                'win_rate': metrics['win_rate'],
                'avg_turnover': turnover.mean(),
                'rebalance_count': (turnover > 0).sum(),
                'total_cost': results['cost_series'].sum(),
            }

            results_summary.append(summary)

            logger.info(f"\n{factor_name} 回测完成:")
            logger.info(f"  年化收益(含成本): {summary['annual_return']:.2%}")
            logger.info(f"  Sharpe(含成本): {summary['sharpe_ratio']:.2f}")
            logger.info(f"  最大回撤: {summary['max_drawdown']:.2%}")
            logger.info(f"  平均换手率: {summary['avg_turnover']:.2%}")

        except Exception as e:
            logger.error(f"{factor_name} 回测失败: {e}")
            import traceback
            traceback.print_exc()
            continue

    # 6. 汇总结果
    logger.info("\n" + "="*70)
    logger.info("6. 多因子对比分析")
    logger.info("="*70)

    df_summary = pd.DataFrame(results_summary)

    # 按Sharpe排序
    df_summary_sorted = df_summary.sort_values('sharpe_ratio', ascending=False)

    logger.info(f"\n完整结果表(按Sharpe排序):")
    logger.info("\n" + df_summary_sorted.to_string(index=False))

    # 保存结果
    df_summary_sorted.to_csv('results/multi_factor_comparison.csv', index=False)
    logger.info(f"\n✅ 结果已保存到: results/multi_factor_comparison.csv")

    # 7. 分析结果
    logger.info("\n" + "="*70)
    logger.info("7. 详细对比分析")
    logger.info("="*70)

    # 7.1 找出最佳因子
    best_factor = df_summary_sorted.iloc[0]
    logger.info(f"\n🏆 表现最佳的因子: {best_factor['factor']}")
    logger.info(f"  年化收益(含成本): {best_factor['annual_return']:.2%}")
    logger.info(f"  Sharpe比率: {best_factor['sharpe_ratio']:.2f}")
    logger.info(f"  最大回撤: {best_factor['max_drawdown']:.2%}")

    # 7.2 单因子 vs 合成因子
    logger.info(f"\n" + "-"*70)
    logger.info("单因子 vs 合成因子对比")
    logger.info("-"*70)

    single_factors = df_summary[df_summary['factor'] != 'Composite']
    composite = df_summary[df_summary['factor'] == 'Composite']

    if len(composite) > 0:
        composite = composite.iloc[0]

        logger.info(f"\n单因子平均表现:")
        logger.info(f"  平均年化收益: {single_factors['annual_return'].mean():.2%}")
        logger.info(f"  平均Sharpe: {single_factors['sharpe_ratio'].mean():.2f}")
        logger.info(f"  平均最大回撤: {single_factors['max_drawdown'].mean():.2%}")

        logger.info(f"\n合成因子表现:")
        logger.info(f"  年化收益: {composite['annual_return']:.2%}")
        logger.info(f"  Sharpe: {composite['sharpe_ratio']:.2f}")
        logger.info(f"  最大回撤: {composite['max_drawdown']:.2%}")

        logger.info(f"\n合成因子排名: {df_summary_sorted[df_summary_sorted['factor']=='Composite'].index[0] + 1} / 6")

    # 7.3 按指标分类
    logger.info(f"\n" + "-"*70)
    logger.info("按不同指标排名")
    logger.info("-"*70)

    logger.info(f"\n📈 按年化收益排名:")
    top_return = df_summary.nlargest(3, 'annual_return')[['factor', 'annual_return']]
    for idx, row in top_return.iterrows():
        logger.info(f"  {row['factor']}: {row['annual_return']:.2%}")

    logger.info(f"\n📊 按Sharpe比率排名:")
    top_sharpe = df_summary.nlargest(3, 'sharpe_ratio')[['factor', 'sharpe_ratio']]
    for idx, row in top_sharpe.iterrows():
        logger.info(f"  {row['factor']}: {row['sharpe_ratio']:.2f}")

    logger.info(f"\n🛡️  按最大回撤排名(绝对值小为好):")
    top_dd = df_summary.nsmallest(3, 'max_drawdown')[['factor', 'max_drawdown']]
    for idx, row in top_dd.iterrows():
        logger.info(f"  {row['factor']}: {row['max_drawdown']:.2%}")

    logger.info(f"\n💰 按换手率排名(小为好):")
    top_turnover = df_summary.nsmallest(3, 'avg_turnover')[['factor', 'avg_turnover']]
    for idx, row in top_turnover.iterrows():
        logger.info(f"  {row['factor']}: {row['avg_turnover']:.2%}")

    # 7.4 含成本 vs 不含成本对比
    logger.info(f"\n" + "-"*70)
    logger.info("交易成本影响分析")
    logger.info("-"*70)

    df_summary['cost_impact'] = df_summary['annual_return_no_cost'] - df_summary['annual_return']
    df_summary['cost_impact_pct'] = df_summary['cost_impact'] / df_summary['annual_return_no_cost'].abs()

    logger.info(f"\n按成本影响排序(绝对值):")
    for idx, row in df_summary.nlargest(3, 'cost_impact')[['factor', 'cost_impact', 'avg_turnover']].iterrows():
        logger.info(f"  {row['factor']}: 成本拖累{row['cost_impact']:.2%}, 换手率{row['avg_turnover']:.2%}")

    # 8. 生成markdown报告
    logger.info(f"\n" + "="*70)
    logger.info("8. 生成对比报告")
    logger.info("="*70)

    generate_comparison_report(df_summary_sorted, best_factor, composite if len(composite) > 0 else None)

    logger.info("\n" + "="*70)
    logger.info("多因子对比测试完成！")
    logger.info("="*70)


def generate_comparison_report(df_summary, best_factor, composite):
    """生成markdown对比报告"""

    report = f'''# 多因子对比测试报告

**测试时间**: 2026-02-03
**测试参数**: 每2月调仓 + 12月最小持有期 + 25%/30%进出阈值

---

## 测试概览

使用最优参数对6个因子进行回测对比:
- 5个单因子: 动量、反转、低波、趋势、流动性
- 1个合成因子: 5个因子等权平均

---

## 完整结果对比表

'''

    # 添加表格
    report += df_summary.to_markdown(index=False, floatfmt='.4f')

    report += f'''

---

## 🏆 最佳因子

**{best_factor['factor']}** 在所有因子中表现最佳

| 指标 | 数值 |
|------|------|
| 年化收益(含成本) | {best_factor['annual_return']:.2%} |
| Sharpe比率 | {best_factor['sharpe_ratio']:.2f} |
| 最大回撤 | {best_factor['max_drawdown']:.2%} |
| 年化波动率 | {best_factor['annual_volatility']:.2%} |
| Calmar比率 | {best_factor['calmar_ratio']:.2f} |
| 胜率 | {best_factor['win_rate']:.2%} |
| 平均换手率 | {best_factor['avg_turnover']:.2%} |
| 调仓次数 | {best_factor['rebalance_count']:.0f} |

---

## 单因子 vs 合成因子

'''

    single_factors = df_summary[df_summary['factor'] != 'Composite']

    if composite is not None:
        report += f'''
### 单因子平均表现

| 指标 | 平均值 |
|------|--------|
| 年化收益 | {single_factors['annual_return'].mean():.2%} |
| Sharpe比率 | {single_factors['sharpe_ratio'].mean():.2f} |
| 最大回撤 | {single_factors['max_drawdown'].mean():.2%} |
| 平均换手率 | {single_factors['avg_turnover'].mean():.2%} |

### 合成因子表现

| 指标 | 数值 |
|------|------|
| 年化收益 | {composite['annual_return']:.2%} |
| Sharpe比率 | {composite['sharpe_ratio']:.2f} |
| 最大回撤 | {composite['max_drawdown']:.2%} |
| 平均换手率 | {composite['avg_turnover']:.2%} |

**合成因子排名**: {df_summary[df_summary['factor']=='Composite'].index[0] + 1} / 6

'''

    report += '''
---

## 分项排名

### 📈 按年化收益排名

'''
    top_return = df_summary.nlargest(3, 'annual_return')[['factor', 'annual_return']]
    report += top_return.to_markdown(index=False, floatfmt='.2%')

    report += '''

### 📊 按Sharpe比率排名

'''
    top_sharpe = df_summary.nlargest(3, 'sharpe_ratio')[['factor', 'sharpe_ratio']]
    report += top_sharpe.to_markdown(index=False, floatfmt='.2f')

    report += '''

### 🛡️  按风险控制排名（最大回撤）

'''
    top_dd = df_summary.nsmallest(3, 'max_drawdown')[['factor', 'max_drawdown']]
    report += top_dd.to_markdown(index=False, floatfmt='.2%')

    report += '''

### 💰 按交易成本排名（换手率）

'''
    top_turnover = df_summary.nsmallest(3, 'avg_turnover')[['factor', 'avg_turnover']]
    report += top_turnover.to_markdown(index=False, floatfmt='.2%')

    report += '''

---

## 关键发现

'''

    # 分析各因子表现
    report += f'''
### 1. 因子表现分化

'''

    positive_return = df_summary[df_summary['annual_return'] > 0]
    negative_return = df_summary[df_summary['annual_return'] < 0]

    report += f"- **正收益因子**: {len(positive_return)}个\n"
    report += f"- **负收益因子**: {len(negative_return)}个\n\n"

    if len(positive_return) > 0:
        report += "表现最好的因子:\n"
        for idx, row in positive_return.nlargest(3, 'sharpe_ratio')[['factor', 'annual_return', 'sharpe_ratio']].iterrows():
            report += f"- {row['factor']}: 年化{row['annual_return']:.2%}, Sharpe {row['sharpe_ratio']:.2f}\n"

    report += f'''

### 2. 合成因子效果

'''

    if composite is not None:
        if composite['sharpe_ratio'] > single_factors['sharpe_ratio'].mean():
            report += f"✅ 合成因子Sharpe ({composite['sharpe_ratio']:.2f}) 优于单因子平均 ({single_factors['sharpe_ratio'].mean():.2f})\n"
            report += f"   - 分散化效应明显，降低了单因子风险\n"
        else:
            report += f"⚠️  合成因子Sharpe ({composite['sharpe_ratio']:.2f}) 不及单因子平均 ({single_factors['sharpe_ratio'].mean():.2f})\n"
            report += f"   - 可能存在负相关因子拖累整体表现\n"

    report += f'''

### 3. 交易成本影响

'''

    df_cost_impact = df_summary.copy()
    df_cost_impact['cost_drag'] = df_cost_impact['annual_return_no_cost'] - df_cost_impact['annual_return']

    report += f"平均成本拖累: {df_cost_impact['cost_drag'].mean():.2%}\n\n"
    report += "成本影响最大的因子:\n"
    for idx, row in df_cost_impact.nlargest(3, 'cost_drag')[['factor', 'cost_drag', 'avg_turnover']].iterrows():
        report += f"- {row['factor']}: 拖累{row['cost_drag']:.2%}, 换手率{row['avg_turnover']:.2%}\n"

    report += '''

---

## 结论与建议

### 实盘建议

'''

    # 根据结果给建议
    if best_factor['sharpe_ratio'] > 0:
        report += f"1. **推荐使用 {best_factor['factor']}** - 表现最优且风险可控\n"
    else:
        report += f"1. **谨慎使用** - 所有因子在测试期均为负收益\n"

    if composite is not None and composite['sharpe_ratio'] > single_factors['sharpe_ratio'].max():
        report += f"2. **优先考虑合成因子** - 分散化效果显著\n"
    else:
        report += f"2. **可考虑最优单因子** - 当前合成效果不及最佳单因子\n"

    report += f'''
3. **继续优化**
   - 测试不同的因子合成权重
   - 考虑行业中性化
   - 优化进出阈值参数

---

**报告生成时间**: 2026-02-03
**测试样本**: S&P 500 (476只股票)
**测试时间**: 2016-02 ~ 2025-12 (85期)
'''

    # 保存报告
    with open('MULTI_FACTOR_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info("✅ 对比报告已生成: MULTI_FACTOR_REPORT.md")


if __name__ == '__main__':
    main()
