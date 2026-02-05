"""
稳健性测试脚本 (Priority 3)

测试内容:
1. 子样本测试: 2016-2020 vs 2020-2025
2. 成本敏感性: 10/20/30/40/50 bps
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
from factors.factor_processor import FactorProcessor
from portfolio.portfolio_builder import PortfolioBuilder
from backtest.engine import BacktestEngine


def run_backtest_with_params(
    df_factor: pd.DataFrame,
    df_return: pd.DataFrame,
    cost_bps: float = 20.0,
    rebalance_freq: str = '2monthly',
    min_holding_periods: int = 12
) -> dict:
    """
    运行回测

    Parameters:
    -----------
    df_factor : DataFrame
        因子值
    df_return : DataFrame
        收益率
    cost_bps : float
        交易成本
    rebalance_freq : str
        调仓频率
    min_holding_periods : int
        最小持有期

    Returns:
    --------
    result : dict
        回测结果
    """
    # 构建组合(自动中性化)
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=min_holding_periods,
        long_top=True
    )
    df_weights = builder.build(df_factor, neutralize=True)

    # 回测
    engine = BacktestEngine(
        cost_bps=cost_bps,
        rebalance_freq=rebalance_freq
    )

    backtest_result = engine.run(df_weights, df_return)

    return backtest_result


def test_sub_samples(
    df_factor: pd.DataFrame,
    df_return: pd.DataFrame,
    split_date: str = '2020-01-01'
) -> dict:
    """
    子样本测试

    Parameters:
    -----------
    df_factor : DataFrame
        因子值
    df_return : DataFrame
        收益率
    split_date : str
        分割日期

    Returns:
    --------
    results : dict
        各子样本的回测结果
    """
    print(f"\n{'='*80}")
    print(f"子样本测试 (分割点: {split_date})")
    print(f"{'='*80}")

    split_ts = pd.Timestamp(split_date)

    # 对齐因子和收益率的时间范围
    common_dates = df_factor.index.intersection(df_return.index)

    # 样本1: 分割点之前
    dates_sample1 = common_dates[common_dates < split_ts]
    if len(dates_sample1) > 0:
        df_factor_s1 = df_factor.loc[dates_sample1]
        df_return_s1 = df_return.loc[dates_sample1]

        print(f"\n样本1: {dates_sample1.min()} ~ {dates_sample1.max()} ({len(dates_sample1)}期)")
        result_s1 = run_backtest_with_params(df_factor_s1, df_return_s1)
    else:
        result_s1 = None
        print(f"\n样本1: 无数据")

    # 样本2: 分割点之后
    dates_sample2 = common_dates[common_dates >= split_ts]
    if len(dates_sample2) > 0:
        df_factor_s2 = df_factor.loc[dates_sample2]
        df_return_s2 = df_return.loc[dates_sample2]

        print(f"\n样本2: {dates_sample2.min()} ~ {dates_sample2.max()} ({len(dates_sample2)}期)")
        result_s2 = run_backtest_with_params(df_factor_s2, df_return_s2)
    else:
        result_s2 = None
        print(f"\n样本2: 无数据")

    # 全样本
    print(f"\n全样本: {common_dates.min()} ~ {common_dates.max()} ({len(common_dates)}期)")
    df_factor_full = df_factor.loc[common_dates]
    df_return_full = df_return.loc[common_dates]
    result_full = run_backtest_with_params(df_factor_full, df_return_full)

    results = {
        'sample1': result_s1,
        'sample2': result_s2,
        'full': result_full
    }

    return results


def test_cost_sensitivity(
    df_factor: pd.DataFrame,
    df_return: pd.DataFrame,
    cost_bps_list: list = [10, 20, 30, 40, 50]
) -> pd.DataFrame:
    """
    成本敏感性测试

    Parameters:
    -----------
    df_factor : DataFrame
        因子值
    df_return : DataFrame
        收益率
    cost_bps_list : list
        交易成本列表(bps)

    Returns:
    --------
    df_results : DataFrame
        成本敏感性结果表
    """
    print(f"\n{'='*80}")
    print(f"成本敏感性测试")
    print(f"{'='*80}")

    results = []

    for cost_bps in cost_bps_list:
        print(f"\n测试成本: {cost_bps} bps")

        result = run_backtest_with_params(
            df_factor,
            df_return,
            cost_bps=cost_bps
        )

        metrics = result['metrics']

        row = {
            'cost_bps': cost_bps,
            'annual_return': metrics['annual_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'annual_volatility': metrics['annual_volatility'],
            'calmar_ratio': metrics['calmar_ratio'],
            'win_rate': metrics['win_rate'],
            'avg_turnover': result['turnover'].mean()
        }
        results.append(row)

    df_results = pd.DataFrame(results)
    return df_results


def main():
    """主函数"""
    print("="*80)
    print("稳健性测试 (Priority 3)")
    print("="*80)

    # 加载数据
    print("\n加载数据...")
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 使用Momentum因子作为测试因子
    print("\n计算因子...")
    factor = MomentumFactor()
    df_factor = factor.calculate(
        df_price=df_clean['price'],
        df_return_daily=df_clean.get('daily_return')
    )

    # 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 获取收益率
    df_return = df_clean['monthly_return']

    # 1. 子样本测试
    print(f"\n{'='*80}")
    print("测试1: 子样本稳健性")
    print(f"{'='*80}")

    sub_sample_results = test_sub_samples(df_factor, df_return, split_date='2020-01-01')

    # 生成子样本对比表
    sub_sample_data = []
    for name, result in sub_sample_results.items():
        if result is not None:
            metrics = result['metrics']
            row = {
                'sample': name,
                'annual_return': metrics['annual_return'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown'],
                'annual_volatility': metrics['annual_volatility'],
                'calmar_ratio': metrics['calmar_ratio'],
                'win_rate': metrics['win_rate'],
                'avg_turnover': result['turnover'].mean()
            }
            sub_sample_data.append(row)

    df_sub_sample = pd.DataFrame(sub_sample_data)

    # 保存子样本结果
    output_file_1 = 'results/robustness_sub_sample.csv'
    df_sub_sample.to_csv(output_file_1, index=False)
    print(f"\n✅ 子样本结果已保存: {output_file_1}")

    # 打印子样本结果
    print(f"\n子样本对比:")
    print(df_sub_sample.to_string(index=False))

    # 2. 成本敏感性测试
    print(f"\n{'='*80}")
    print("测试2: 成本敏感性")
    print(f"{'='*80}")

    df_cost_sensitivity = test_cost_sensitivity(
        df_factor,
        df_return,
        cost_bps_list=[10, 20, 30, 40, 50]
    )

    # 保存成本敏感性结果
    output_file_2 = 'results/robustness_cost_sensitivity.csv'
    df_cost_sensitivity.to_csv(output_file_2, index=False)
    print(f"\n✅ 成本敏感性结果已保存: {output_file_2}")

    # 打印成本敏感性结果
    print(f"\n成本敏感性:")
    print(df_cost_sensitivity.to_string(index=False))

    # 3. 生成报告
    generate_robustness_report(df_sub_sample, df_cost_sensitivity)

    print(f"\n{'='*80}")
    print("✅ 稳健性测试完成!")
    print(f"{'='*80}")


def generate_robustness_report(
    df_sub_sample: pd.DataFrame,
    df_cost_sensitivity: pd.DataFrame
):
    """生成稳健性报告"""
    report = f"""# 稳健性测试报告 (中性化权重)

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试因子**: Momentum
**回测配置**: 2monthly + 12月持有期 + 25%/30%阈值

---

## 1. 子样本测试

### 结果对比

| 样本 | 年化收益 | Sharpe | 最大回撤 | 波动率 | 胜率 | 换手率 |
|------|----------|--------|----------|--------|------|--------|
"""

    for _, row in df_sub_sample.iterrows():
        sample_name = {
            'sample1': '样本1 (2016-2020)',
            'sample2': '样本2 (2020-2025)',
            'full': '全样本'
        }.get(row['sample'], row['sample'])

        report += f"| {sample_name} | {row['annual_return']:.2%} | {row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} | {row['annual_volatility']:.2%} | {row['win_rate']:.2%} | {row['avg_turnover']:.2%} |\n"

    report += """
### 稳健性评估

"""

    if len(df_sub_sample) >= 2:
        sample1 = df_sub_sample[df_sub_sample['sample'] == 'sample1'].iloc[0] if 'sample1' in df_sub_sample['sample'].values else None
        sample2 = df_sub_sample[df_sub_sample['sample'] == 'sample2'].iloc[0] if 'sample2' in df_sub_sample['sample'].values else None

        if sample1 is not None and sample2 is not None:
            sharpe_diff = abs(sample1['sharpe_ratio'] - sample2['sharpe_ratio'])
            sharpe_avg = (sample1['sharpe_ratio'] + sample2['sharpe_ratio']) / 2

            if sharpe_avg != 0:
                sharpe_stability = 1 - sharpe_diff / abs(sharpe_avg)
            else:
                sharpe_stability = 0

            report += f"""- Sharpe差异: {sharpe_diff:.4f}
- Sharpe稳定性: {sharpe_stability:.2%}
- 结论: {'稳健' if sharpe_stability > 0.5 else '不稳健'}
"""

    report += f"""
---

## 2. 成本敏感性测试

### 结果对比

| 成本(bps) | 年化收益 | Sharpe | 最大回撤 | 波动率 | 胜率 |
|-----------|----------|--------|----------|--------|------|
"""

    for _, row in df_cost_sensitivity.iterrows():
        report += f"| {row['cost_bps']:.0f} | {row['annual_return']:.2%} | {row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} | {row['annual_volatility']:.2%} | {row['win_rate']:.2%} |\n"

    report += """
### 成本影响分析

"""

    if len(df_cost_sensitivity) > 0:
        min_cost_row = df_cost_sensitivity[df_cost_sensitivity['cost_bps'] == df_cost_sensitivity['cost_bps'].min()].iloc[0]
        max_cost_row = df_cost_sensitivity[df_cost_sensitivity['cost_bps'] == df_cost_sensitivity['cost_bps'].max()].iloc[0]

        return_drop = min_cost_row['annual_return'] - max_cost_row['annual_return']
        sharpe_drop = min_cost_row['sharpe_ratio'] - max_cost_row['sharpe_ratio']

        report += f"""从 {min_cost_row['cost_bps']:.0f} bps 到 {max_cost_row['cost_bps']:.0f} bps:
- 年化收益下降: {return_drop:.2%}
- Sharpe下降: {sharpe_drop:.4f}
- 每增加10bps成本，年化收益下降约: {return_drop / (max_cost_row['cost_bps'] - min_cost_row['cost_bps']) * 10:.2%}
"""

    report += f"""
---

## 总结

### 关键发现

1. **子样本稳健性**: 测试了策略在不同时间段的表现一致性
2. **成本敏感性**: 评估了交易成本对策略收益的影响程度

### 建议

- 如果子样本表现差异大，考虑动态调整参数
- 如果成本敏感性高，考虑降低换手率

---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    # 保存报告
    with open('results/ROBUSTNESS_TEST_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已保存: results/ROBUSTNESS_TEST_REPORT.md")


if __name__ == '__main__':
    main()
