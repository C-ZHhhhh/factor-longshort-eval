"""
评估层测试脚本

测试IC/IR分析、暴露检查、归因分析和稳健性测试
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
from factors.liquidity import LiquidityFactor
from factors.factor_processor import FactorProcessor
from portfolio.portfolio_builder import PortfolioBuilder
from backtest.engine import BacktestEngine
from evaluation.ic_analysis import ICAnalyzer
from evaluation.exposure_check import ExposureChecker
from evaluation.attribution import AttributionAnalyzer
from evaluation.robustness import RobustnessTest


def test_ic_analysis():
    """测试IC/IR分析"""
    print("\n" + "=" * 80)
    print("测试1: IC/IR分析")
    print("=" * 80)

    # 加载数据
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 计算因子
    # 注意: Liquidity因子需要成交量数据,这里使用Momentum因子替代
    factor = MomentumFactor()  # 使用Momentum因子(不需要成交量数据)
    df_factor = factor.calculate(
        df_price=df_clean['price'],
        df_return_daily=df_clean.get('daily_return')
    )

    # 标准化因子
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 获取收益率
    df_return = df_clean['monthly_return']

    # IC分析
    analyzer = ICAnalyzer()
    ic_result = analyzer.analyze(df_factor, df_return)

    print("\n📊 IC/IR分析结果:")
    print(f"IC均值: {ic_result['ic_mean']:.4f}")
    print(f"IC中位数: {ic_result['ic_median']:.4f}")
    print(f"IC标准差: {ic_result['ic_std']:.4f}")
    print(f"IR (信息比率): {ic_result['ir']:.4f}")
    print(f"IC正占比: {ic_result['ic_positive_ratio']:.2%}")
    print(f"t统计量: {ic_result['t_statistic']:.4f}")
    print(f"样本期数: {ic_result['n_periods']}")

    # IC时间序列
    ic_series = ic_result['ic_series']
    print(f"\nIC时间序列统计:")
    print(f"最大IC: {ic_series.max():.4f} ({ic_series.idxmax().strftime('%Y-%m')})")
    print(f"最小IC: {ic_series.min():.4f} ({ic_series.idxmin().strftime('%Y-%m')})")

    # 保存IC序列
    ic_series.to_csv('results/ic_series_momentum.csv')
    print(f"\n✅ IC序列已保存到: results/ic_series_momentum.csv")

    return ic_result


def test_exposure_check():
    """测试暴露检查"""
    print("\n" + "=" * 80)
    print("测试2: 暴露检查")
    print("=" * 80)

    # 加载数据
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 计算因子
    factor = MomentumFactor()
    df_factor = factor.calculate(df_price=df_clean["price"], df_return_daily=df_clean.get("daily_return"))

    # 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 构建组合
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=12,
        long_top=True
    )

    df_weights = builder.build(df_factor)

    # 暴露检查
    checker = ExposureChecker()

    # 1. 权重中性化检查
    neutrality = checker.check_weight_neutrality(df_weights)
    print("\n🔍 权重中性化检查:")
    print(f"权重和均值: {neutrality['weight_sum_mean']:.6f}")
    print(f"权重和标准差: {neutrality['weight_sum_std']:.6f}")
    print(f"权重和最大值: {neutrality['weight_sum_max']:.6f}")
    print(f"权重和最小值: {neutrality['weight_sum_min']:.6f}")
    print(f"是否市场中性: {'✅ 是' if neutrality['is_market_neutral'] else '❌ 否'}")
    print(f"中性化得分: {neutrality['neutrality_score']:.4f}")

    # 2. 多空平衡检查
    balance = checker.check_long_short_balance(df_weights)
    print("\n⚖️  多空平衡检查:")
    print(f"平均多头数量: {balance['avg_n_long']:.1f}")
    print(f"平均空头数量: {balance['avg_n_short']:.1f}")
    print(f"平均多头权重: {balance['avg_long_weight']:.4f}")
    print(f"平均空头权重: {balance['avg_short_weight']:.4f}")
    print(f"多空权重比: {balance['long_short_ratio']:.4f}")
    print(f"是否平衡: {'✅ 是' if balance['is_balanced'] else '❌ 否'}")

    return neutrality, balance


def test_attribution():
    """测试归因分析"""
    print("\n" + "=" * 80)
    print("测试3: 归因分析")
    print("=" * 80)

    # 加载数据
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 计算因子
    factor = MomentumFactor()
    df_factor = factor.calculate(df_price=df_clean["price"], df_return_daily=df_clean.get("daily_return"))

    # 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 构建组合
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=12,
        long_top=True
    )

    df_weights = builder.build(df_factor)

    # 获取收益率
    df_return = df_clean['monthly_return']

    # 归因分析
    analyzer = AttributionAnalyzer()
    attribution = analyzer.analyze(df_weights, df_return)

    # 多空分解
    ls_decomp = attribution['long_short_decomposition']
    print("\n📊 多空收益分解:")
    print(f"多头月均收益: {ls_decomp['long_contrib_mean']:.4%}")
    print(f"空头月均收益: {ls_decomp['short_contrib_mean']:.4%}")
    print(f"多头收益标准差: {ls_decomp['long_contrib_std']:.4%}")
    print(f"空头收益标准差: {ls_decomp['short_contrib_std']:.4%}")
    print(f"多头Sharpe: {ls_decomp['long_sharpe']:.4f}")
    print(f"空头Sharpe: {ls_decomp['short_sharpe']:.4f}")
    print(f"多头贡献占比: {ls_decomp['long_pct']:.2%}")
    print(f"空头贡献占比: {ls_decomp['short_pct']:.2%}")

    # 选股收益
    selection = attribution['stock_selection']
    print("\n🎯 选股收益分析:")
    print(f"实际月均收益: {selection['actual_return']:.4%}")
    print(f"基准月均收益: {selection['benchmark_return']:.4%}")
    print(f"选股月均收益: {selection['selection_return_mean']:.4%}")
    print(f"选股Sharpe: {selection['selection_sharpe']:.4f}")
    print(f"选股贡献占比: {selection['selection_contribution']:.2%}")

    # Top贡献者
    top_contrib = attribution['top_contributors']
    print("\n🏆 Top 10 收益贡献股票:")
    for ticker, contrib in top_contrib['top_contributors'].items():
        print(f"  {ticker}: {contrib:.4%}")

    print("\n💥 Bottom 10 收益拖累股票:")
    for ticker, contrib in top_contrib['bottom_contributors'].items():
        print(f"  {ticker}: {contrib:.4%}")

    return attribution


def test_robustness():
    """测试稳健性分析"""
    print("\n" + "=" * 80)
    print("测试4: 稳健性分析")
    print("=" * 80)

    # 加载数据
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 计算因子
    factor = MomentumFactor()
    df_factor = factor.calculate(df_price=df_clean["price"], df_return_daily=df_clean.get("daily_return"))

    # 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 获取收益率
    df_return = df_clean['monthly_return']

    # 稳健性测试
    tester = RobustnessTest()

    print("\n🔬 开始稳健性测试...")
    robustness = tester.analyze_robustness(
        df_factor, df_return,
        split_date='2020-01-01'
    )

    # 1. 子样本测试
    print("\n📅 子样本测试结果:")
    for period_name, result in robustness['sub_sample'].items():
        print(f"\n{period_name}:")
        print(f"  年化收益: {result['annual_return']:.2%}")
        print(f"  Sharpe比率: {result['sharpe_ratio']:.4f}")
        print(f"  最大回撤: {result['max_drawdown']:.2%}")
        print(f"  平均换手率: {result['avg_turnover']:.2%}")

    # 2. 成本敏感性
    print("\n💰 成本敏感性测试:")
    cost_df = robustness['cost_sensitivity']
    print(cost_df[['cost_bps', 'annual_return', 'sharpe_ratio', 'max_drawdown', 'avg_turnover']].to_string(index=False))

    # 保存
    cost_df.to_csv('results/cost_sensitivity.csv', index=False)
    print(f"\n✅ 成本敏感性结果已保存到: results/cost_sensitivity.csv")

    # 3. 分位数敏感性
    print("\n📊 分位数敏感性测试:")
    quantile_df = robustness['quantile_sensitivity']
    print(quantile_df[['entry_quantile', 'annual_return', 'sharpe_ratio', 'max_drawdown', 'avg_turnover']].to_string(index=False))

    # 保存
    quantile_df.to_csv('results/quantile_sensitivity.csv', index=False)
    print(f"\n✅ 分位数敏感性结果已保存到: results/quantile_sensitivity.csv")

    return robustness


def main():
    """主函数"""
    print("=" * 80)
    print("评估层测试")
    print("=" * 80)

    try:
        # 测试1: IC/IR分析
        ic_result = test_ic_analysis()

        # 测试2: 暴露检查
        neutrality, balance = test_exposure_check()

        # 测试3: 归因分析
        attribution = test_attribution()

        # 测试4: 稳健性分析
        robustness = test_robustness()

        print("\n" + "=" * 80)
        print("✅ 所有评估层测试完成!")
        print("=" * 80)

        # 生成评估报告
        print("\n生成评估报告...")
        generate_evaluation_report(ic_result, neutrality, balance, attribution, robustness)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def generate_evaluation_report(ic_result, neutrality, balance, attribution, robustness):
    """生成评估报告"""
    report = f"""# 评估层测试报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试因子**: Momentum
**测试配置**: 2monthly + 12月持有期 + 25%/30%阈值

---

## 1. IC/IR分析

### 信息系数统计

| 指标 | 数值 |
|------|------|
| IC均值 | {ic_result['ic_mean']:.4f} |
| IC中位数 | {ic_result['ic_median']:.4f} |
| IC标准差 | {ic_result['ic_std']:.4f} |
| **IR (信息比率)** | **{ic_result['ir']:.4f}** |
| IC正占比 | {ic_result['ic_positive_ratio']:.2%} |
| t统计量 | {ic_result['t_statistic']:.4f} |
| 样本期数 | {ic_result['n_periods']} |

### IC解读

- **IR = {ic_result['ir']:.4f}**: {'优秀' if ic_result['ir'] > 0.5 else '良好' if ic_result['ir'] > 0.3 else '一般' if ic_result['ir'] > 0.1 else '较弱'}
- **IC正占比 = {ic_result['ic_positive_ratio']:.2%}**: {'稳定性强' if ic_result['ic_positive_ratio'] > 0.55 else '稳定性中等' if ic_result['ic_positive_ratio'] > 0.5 else '稳定性较弱'}
- **t统计量 = {ic_result['t_statistic']:.2f}**: {'显著' if abs(ic_result['t_statistic']) > 2 else '不显著'}

---

## 2. 暴露检查

### 权重中性化

| 指标 | 数值 | 判定 |
|------|------|------|
| 权重和均值 | {neutrality['weight_sum_mean']:.6f} | {'✅ 通过' if abs(neutrality['weight_sum_mean']) < 0.01 else '❌ 未通过'} |
| 权重和标准差 | {neutrality['weight_sum_std']:.6f} | |
| 是否市场中性 | {'是' if neutrality['is_market_neutral'] else '否'} | {'✅ 通过' if neutrality['is_market_neutral'] else '❌ 未通过'} |
| 中性化得分 | {neutrality['neutrality_score']:.4f} | |

### 多空平衡

| 指标 | 数值 | 判定 |
|------|------|------|
| 平均多头数量 | {balance['avg_n_long']:.1f} | |
| 平均空头数量 | {balance['avg_n_short']:.1f} | |
| 平均多头权重 | {balance['avg_long_weight']:.4f} | |
| 平均空头权重 | {balance['avg_short_weight']:.4f} | |
| 多空权重比 | {balance['long_short_ratio']:.4f} | {'✅ 平衡' if 0.95 < balance['long_short_ratio'] < 1.05 else '⚠️  不平衡'} |

---

## 3. 归因分析

### 多空收益分解

| 指标 | 多头 | 空头 |
|------|------|------|
| 月均收益 | {attribution['long_short_decomposition']['long_contrib_mean']:.4%} | {attribution['long_short_decomposition']['short_contrib_mean']:.4%} |
| 收益标准差 | {attribution['long_short_decomposition']['long_contrib_std']:.4%} | {attribution['long_short_decomposition']['short_contrib_std']:.4%} |
| Sharpe比率 | {attribution['long_short_decomposition']['long_sharpe']:.4f} | {attribution['long_short_decomposition']['short_sharpe']:.4f} |
| 贡献占比 | {attribution['long_short_decomposition']['long_pct']:.2%} | {attribution['long_short_decomposition']['short_pct']:.2%} |

### 选股收益

| 指标 | 数值 |
|------|------|
| 实际月均收益 | {attribution['stock_selection']['actual_return']:.4%} |
| 基准月均收益 | {attribution['stock_selection']['benchmark_return']:.4%} |
| 选股月均收益 | {attribution['stock_selection']['selection_return_mean']:.4%} |
| 选股Sharpe | {attribution['stock_selection']['selection_sharpe']:.4f} |
| 选股贡献占比 | {attribution['stock_selection']['selection_contribution']:.2%} |

---

## 4. 稳健性测试

### 子样本测试

"""

    # 子样本结果
    for period_name, result in robustness['sub_sample'].items():
        report += f"""
**{period_name}**:
- 年化收益: {result['annual_return']:.2%}
- Sharpe比率: {result['sharpe_ratio']:.4f}
- 最大回撤: {result['max_drawdown']:.2%}
- 平均换手率: {result['avg_turnover']:.2%}
"""

    report += """
### 成本敏感性

详见: `results/cost_sensitivity.csv`

### 分位数敏感性

详见: `results/quantile_sensitivity.csv`

---

## 总结

### 关键发现

1. **IC/IR表现**: """

    if ic_result['ir'] > 0.3:
        report += "因子预测能力较强，IR显著为正\n"
    elif ic_result['ir'] > 0.1:
        report += "因子预测能力中等，IR为正但不够稳健\n"
    else:
        report += "因子预测能力较弱，IR接近0\n"

    report += f"""
2. **中性化效果**: {'权重中性化良好，Σw ≈ 0' if neutrality['is_market_neutral'] else '权重中性化不理想，存在市场暴露'}

3. **多空平衡**: {'多空权重基本平衡' if balance['is_balanced'] else '多空权重不平衡'}

4. **收益来源**: {'主要来自多头' if attribution['long_short_decomposition']['long_pct'] > 0.6 else '主要来自空头' if attribution['long_short_decomposition']['short_pct'] > 0.6 else '多空贡献均衡'}

5. **稳健性**: 详见成本和分位数敏感性测试结果

---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    # 保存报告
    with open('results/EVALUATION_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 评估报告已保存到: results/EVALUATION_REPORT.md")


if __name__ == '__main__':
    main()
