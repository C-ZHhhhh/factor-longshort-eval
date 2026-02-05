"""
多因子对比测试脚本 (Priority 2)

运行所有因子回测并生成对比表:
- 5个单因子: Momentum, Reversal, LowVolatility, Trend, Liquidity
- 1个合成因子: Composite
- 输出指标: 年化收益, Sharpe, MaxDD, 换手率(含成本)
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_loader import DataLoader
from factors.momentum import MomentumFactor
from factors.reversal import ReversalFactor
from factors.low_volatility import LowVolatilityFactor
from factors.trend import TrendFactor
from factors.factor_processor import FactorProcessor
from factors.factor_combiner import FactorCombiner
from portfolio.portfolio_builder import PortfolioBuilder
from backtest.engine import BacktestEngine


def run_single_factor(
    factor_name: str,
    df_clean: dict,
    rebalance_freq: str = '2monthly',
    min_holding_periods: int = 12,
    cost_bps: float = 20.0
) -> dict:
    """
    运行单个因子回测

    Parameters:
    -----------
    factor_name : str
        因子名称
    df_clean : dict
        清洗后的数据
    rebalance_freq : str
        调仓频率
    min_holding_periods : int
        最小持有期
    cost_bps : float
        交易成本(bps)

    Returns:
    --------
    result : dict
        回测结果
    """
    print(f"\n{'='*80}")
    print(f"测试因子: {factor_name}")
    print(f"{'='*80}")

    # 1. 计算因子
    factor_map = {
        'Momentum': MomentumFactor(),
        'Reversal': ReversalFactor(),
        'LowVolatility': LowVolatilityFactor(),
        'Trend': TrendFactor(),
    }

    if factor_name not in factor_map:
        raise ValueError(f"未知因子: {factor_name}")

    factor = factor_map[factor_name]
    df_factor = factor.calculate(
        df_price=df_clean['price'],
        df_return_daily=df_clean.get('daily_return')
    )

    # 2. 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 3. 构建组合(自动中性化)
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=min_holding_periods,
        long_top=True
    )
    df_weights = builder.build(df_factor, neutralize=True)

    # 4. 回测
    engine = BacktestEngine(
        cost_bps=cost_bps,
        rebalance_freq=rebalance_freq
    )

    df_return = df_clean['monthly_return']
    backtest_result = engine.run(df_weights, df_return)

    return backtest_result


def run_composite_factor(
    df_clean: dict,
    rebalance_freq: str = '2monthly',
    min_holding_periods: int = 12,
    cost_bps: float = 20.0
) -> dict:
    """
    运行合成因子回测

    Parameters:
    -----------
    df_clean : dict
        清洗后的数据
    rebalance_freq : str
        调仓频率
    min_holding_periods : int
        最小持有期
    cost_bps : float
        交易成本(bps)

    Returns:
    --------
    result : dict
        回测结果
    """
    print(f"\n{'='*80}")
    print(f"测试因子: Composite (多因子合成)")
    print(f"{'='*80}")

    # 1. 计算所有单因子
    factors = {
        'Momentum': MomentumFactor(),
        'Reversal': ReversalFactor(),
        'LowVolatility': LowVolatilityFactor(),
        'Trend': TrendFactor(),
    }

    df_factors = {}
    for name, factor in factors.items():
        df_factor = factor.calculate(
            df_price=df_clean['price'],
            df_return_daily=df_clean.get('daily_return')
        )
        df_factors[name] = df_factor

    # 2. 标准化
    processor = FactorProcessor()
    processed_factors = {}
    for name, df_factor in df_factors.items():
        df_processed = processor.winsorize(df_factor)
        df_processed = processor.zscore_standardize(df_processed)
        processed_factors[name] = df_processed

    # 3. 合成因子
    combiner = FactorCombiner()
    df_composite = combiner.combine(
        list(processed_factors.values()),
        factor_names=list(processed_factors.keys())
    )

    # 4. 构建组合(自动中性化)
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=min_holding_periods,
        long_top=True
    )
    df_weights = builder.build(df_composite, neutralize=True)

    # 5. 回测
    engine = BacktestEngine(
        cost_bps=cost_bps,
        rebalance_freq=rebalance_freq
    )

    df_return = df_clean['monthly_return']
    backtest_result = engine.run(df_weights, df_return)

    return backtest_result


def main():
    """主函数"""
    print("="*80)
    print("多因子对比测试 (Priority 2)")
    print("="*80)

    # 加载数据
    print("\n加载数据...")
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 配置参数
    rebalance_freq = '2monthly'
    min_holding_periods = 12
    cost_bps = 20.0

    print(f"\n回测配置:")
    print(f"  调仓频率: {rebalance_freq}")
    print(f"  最小持有期: {min_holding_periods}月")
    print(f"  交易成本: {cost_bps} bps")

    # 运行所有因子
    factors_to_test = ['Momentum', 'Reversal', 'LowVolatility', 'Trend']
    results = {}

    # 1. 单因子回测
    for factor_name in factors_to_test:
        try:
            result = run_single_factor(
                factor_name,
                df_clean,
                rebalance_freq=rebalance_freq,
                min_holding_periods=min_holding_periods,
                cost_bps=cost_bps
            )
            results[factor_name] = result
        except Exception as e:
            print(f"❌ {factor_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()

    # 2. 合成因子回测
    try:
        result = run_composite_factor(
            df_clean,
            rebalance_freq=rebalance_freq,
            min_holding_periods=min_holding_periods,
            cost_bps=cost_bps
        )
        results['Composite'] = result
    except Exception as e:
        print(f"❌ Composite 测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 3. 生成对比表
    print(f"\n{'='*80}")
    print("生成对比表...")
    print(f"{'='*80}")

    comparison_data = []
    for factor_name, result in results.items():
        metrics = result['metrics']
        metrics_no_cost = result['metrics_no_cost']

        row = {
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
            'avg_turnover': result['turnover'].mean(),
            'rebalance_count': (result['turnover'] > 0).sum(),
            'total_cost': result['cost_series'].sum()
        }
        comparison_data.append(row)

    df_comparison = pd.DataFrame(comparison_data)

    # 按Sharpe排序
    df_comparison = df_comparison.sort_values('sharpe_ratio', ascending=False)

    # 保存结果
    output_file = 'results/multi_factor_comparison_neutralized.csv'
    df_comparison.to_csv(output_file, index=False)
    print(f"\n✅ 对比表已保存: {output_file}")

    # 打印结果
    print(f"\n{'='*80}")
    print("多因子对比结果 (按Sharpe排序)")
    print(f"{'='*80}\n")

    # 格式化输出
    print(df_comparison[[
        'factor', 'annual_return', 'sharpe_ratio',
        'max_drawdown', 'avg_turnover'
    ]].to_string(index=False))

    # 生成markdown报告
    generate_report(df_comparison)

    print(f"\n{'='*80}")
    print("✅ 多因子对比测试完成!")
    print(f"{'='*80}")


def generate_report(df_comparison: pd.DataFrame):
    """生成markdown报告"""
    report = f"""# 多因子对比报告 (中性化权重)

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**回测配置**: 2monthly + 12月持有期 + 25%/30%阈值 + 20bps成本

---

## 完整对比表

| 因子 | 年化收益 | Sharpe | 最大回撤 | 波动率 | Calmar | 胜率 | 换手率 |
|------|----------|--------|----------|--------|--------|------|--------|
"""

    for _, row in df_comparison.iterrows():
        report += f"| {row['factor']} | {row['annual_return']:.2%} | {row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} | {row['annual_volatility']:.2%} | {row['calmar_ratio']:.4f} | {row['win_rate']:.2%} | {row['avg_turnover']:.2%} |\n"

    report += f"""
---

## 关键发现

### 最佳因子

**{df_comparison.iloc[0]['factor']}** 表现最优:
- 年化收益: {df_comparison.iloc[0]['annual_return']:.2%}
- Sharpe比率: {df_comparison.iloc[0]['sharpe_ratio']:.4f}
- 最大回撤: {df_comparison.iloc[0]['max_drawdown']:.2%}
- 平均换手率: {df_comparison.iloc[0]['avg_turnover']:.2%}

### 成本影响

平均成本拖累: {df_comparison['total_cost'].mean():.2%}

### 合成因子表现

"""

    if 'Composite' in df_comparison['factor'].values:
        composite_row = df_comparison[df_comparison['factor'] == 'Composite'].iloc[0]
        composite_rank = df_comparison.index[df_comparison['factor'] == 'Composite'].tolist()[0] + 1
        report += f"""合成因子排名: {composite_rank}/{len(df_comparison)}
- 年化收益: {composite_row['annual_return']:.2%}
- Sharpe比率: {composite_row['sharpe_ratio']:.4f}
- 最大回撤: {composite_row['max_drawdown']:.2%}
"""

    report += f"""
---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    # 保存报告
    with open('results/MULTI_FACTOR_COMPARISON_REPORT_NEUTRALIZED.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已保存: results/MULTI_FACTOR_COMPARISON_REPORT_NEUTRALIZED.md")


if __name__ == '__main__':
    main()
