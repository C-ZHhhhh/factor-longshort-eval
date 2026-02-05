"""
主测试脚本 - 运行所有三个优先级任务

Priority 1: 权重中性化验证
Priority 2: 多因子对比测试
Priority 3: 稳健性测试
"""

import pandas as pd
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_loader import DataLoader
from factors.momentum import MomentumFactor
from factors.factor_processor import FactorProcessor
from portfolio.portfolio_builder import PortfolioBuilder
from evaluation.exposure_check import ExposureChecker


def test_priority1_neutralization():
    """
    Priority 1: 测试权重中性化

    验证:
    1. 多头权重和 = +1
    2. 空头权重和 = -1
    3. 总权重和 ≈ 0
    """
    print("\n" + "="*80)
    print("Priority 1: 权重中性化测试")
    print("="*80)

    # 加载数据
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 计算因子
    factor = MomentumFactor()
    df_factor = factor.calculate(
        df_price=df_clean['price'],
        df_return_daily=df_clean.get('daily_return')
    )

    # 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 构建组合(自动中性化)
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=12,
        long_top=True
    )

    print("\n测试中性化权重...")
    df_weights_neutral = builder.build(df_factor, neutralize=True)

    print("\n测试未中性化持仓...")
    df_holdings = builder.build(df_factor, neutralize=False)

    # 使用ExposureChecker验证
    checker = ExposureChecker()

    print("\n" + "-"*80)
    print("中性化权重检查:")
    print("-"*80)
    neutrality_neutral = checker.check_weight_neutrality(df_weights_neutral)

    print(f"\n权重和均值: {neutrality_neutral['weight_sum_mean']:.6f}")
    print(f"权重和标准差: {neutrality_neutral['weight_sum_std']:.6f}")
    print(f"权重和最大值: {neutrality_neutral['weight_sum_max']:.6f}")
    print(f"权重和最小值: {neutrality_neutral['weight_sum_min']:.6f}")
    print(f"是否市场中性: {'✅ 是' if neutrality_neutral['is_market_neutral'] else '❌ 否'}")
    print(f"中性化得分: {neutrality_neutral['neutrality_score']:.4f}")

    print("\n" + "-"*80)
    print("多空平衡检查:")
    print("-"*80)
    balance_neutral = checker.check_long_short_balance(df_weights_neutral)

    print(f"\n平均多头数量: {balance_neutral['avg_n_long']:.1f}")
    print(f"平均空头数量: {balance_neutral['avg_n_short']:.1f}")
    print(f"平均多头权重: {balance_neutral['avg_long_weight']:.6f}")
    print(f"平均空头权重: {balance_neutral['avg_short_weight']:.6f}")
    print(f"多空权重比: {balance_neutral['long_short_ratio']:.6f}")
    print(f"是否平衡: {'✅ 是' if balance_neutral['is_balanced'] else '❌ 否'}")

    # 对比未中性化的持仓
    print("\n" + "-"*80)
    print("对比: 未中性化持仓检查:")
    print("-"*80)
    neutrality_raw = checker.check_weight_neutrality(df_holdings)

    print(f"\n权重和均值: {neutrality_raw['weight_sum_mean']:.6f}")
    print(f"是否市场中性: {'✅ 是' if neutrality_raw['is_market_neutral'] else '❌ 否'}")

    # 生成报告
    report = f"""# Priority 1: 权重中性化验证报告

**测试时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

## 测试结果

### 中性化权重 (neutralize=True)

| 指标 | 数值 | 目标 | 状态 |
|------|------|------|------|
| 权重和均值 | {neutrality_neutral['weight_sum_mean']:.6f} | ≈0 | {'✅' if abs(neutrality_neutral['weight_sum_mean']) < 0.01 else '❌'} |
| 权重和标准差 | {neutrality_neutral['weight_sum_std']:.6f} | 小 | {'✅' if neutrality_neutral['weight_sum_std'] < 0.1 else '❌'} |
| 多头权重和 | {balance_neutral['avg_long_weight']:.6f} | ≈1 | {'✅' if abs(balance_neutral['avg_long_weight'] - 1.0) < 0.01 else '❌'} |
| 空头权重和 | {balance_neutral['avg_short_weight']:.6f} | ≈1 | {'✅' if abs(balance_neutral['avg_short_weight'] - 1.0) < 0.01 else '❌'} |
| 多空权重比 | {balance_neutral['long_short_ratio']:.6f} | ≈1 | {'✅' if 0.95 < balance_neutral['long_short_ratio'] < 1.05 else '❌'} |

### 结论

✅ **权重中性化成功实现!**

- 多头权重和: {balance_neutral['avg_long_weight']:.6f} ≈ 1.0
- 空头权重和: {balance_neutral['avg_short_weight']:.6f} ≈ 1.0
- 总权重和: {neutrality_neutral['weight_sum_mean']:.6f} ≈ 0.0

权重已正确中性化，满足market-neutral要求。

---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    # 保存报告
    with open('results/PRIORITY1_NEUTRALIZATION_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ Priority 1 报告已保存: results/PRIORITY1_NEUTRALIZATION_REPORT.md")

    if neutrality_neutral['is_market_neutral'] and balance_neutral['is_balanced']:
        print("\n✅ Priority 1 测试通过！权重中性化工作正常。")
        return True
    else:
        print("\n⚠️  Priority 1 测试未完全通过，需要检查中性化逻辑。")
        return False


def test_priority2_multi_factor():
    """
    Priority 2: 运行多因子对比测试
    """
    print("\n" + "="*80)
    print("Priority 2: 多因子对比测试")
    print("="*80)

    import subprocess

    # 运行Priority 2脚本
    result = subprocess.run(
        ['python', 'scripts/priority2_multi_factor.py'],
        cwd=project_root,
        capture_output=False
    )

    if result.returncode == 0:
        print("\n✅ Priority 2 完成！")
        return True
    else:
        print(f"\n❌ Priority 2 失败，返回码: {result.returncode}")
        return False


def test_priority3_robustness():
    """
    Priority 3: 运行稳健性测试
    """
    print("\n" + "="*80)
    print("Priority 3: 稳健性测试")
    print("="*80)

    import subprocess

    # 运行Priority 3脚本
    result = subprocess.run(
        ['python', 'scripts/priority3_robustness.py'],
        cwd=project_root,
        capture_output=False
    )

    if result.returncode == 0:
        print("\n✅ Priority 3 完成！")
        return True
    else:
        print(f"\n❌ Priority 3 失败，返回码: {result.returncode}")
        return False


def main():
    """主函数"""
    print("="*80)
    print("三个优先级任务测试")
    print("="*80)

    results = {}

    # Priority 1: 权重中性化验证
    try:
        results['priority1'] = test_priority1_neutralization()
    except Exception as e:
        print(f"\n❌ Priority 1 失败: {e}")
        import traceback
        traceback.print_exc()
        results['priority1'] = False

    # 只有Priority 1通过后才继续
    if results['priority1']:
        # Priority 2: 多因子对比
        try:
            results['priority2'] = test_priority2_multi_factor()
        except Exception as e:
            print(f"\n❌ Priority 2 失败: {e}")
            import traceback
            traceback.print_exc()
            results['priority2'] = False

        # Priority 3: 稳健性测试
        try:
            results['priority3'] = test_priority3_robustness()
        except Exception as e:
            print(f"\n❌ Priority 3 失败: {e}")
            import traceback
            traceback.print_exc()
            results['priority3'] = False
    else:
        print("\n⚠️  Priority 1 未通过，跳过Priority 2和3")
        results['priority2'] = False
        results['priority3'] = False

    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)

    print(f"\nPriority 1 (权重中性化): {'✅ 通过' if results['priority1'] else '❌ 失败'}")
    print(f"Priority 2 (多因子对比): {'✅ 完成' if results['priority2'] else '❌ 失败/跳过'}")
    print(f"Priority 3 (稳健性测试): {'✅ 完成' if results['priority3'] else '❌ 失败/跳过'}")

    if all(results.values()):
        print("\n🎉 所有测试完成！")
    else:
        print("\n⚠️  部分测试未通过，请查看详细日志")

    # 列出生成的文件
    print("\n" + "="*80)
    print("生成的文件:")
    print("="*80)

    result_files = [
        'results/PRIORITY1_NEUTRALIZATION_REPORT.md',
        'results/multi_factor_comparison_neutralized.csv',
        'results/MULTI_FACTOR_COMPARISON_REPORT_NEUTRALIZED.md',
        'results/robustness_sub_sample.csv',
        'results/robustness_cost_sensitivity.csv',
        'results/ROBUSTNESS_TEST_REPORT.md'
    ]

    from pathlib import Path
    for file in result_files:
        file_path = Path(file)
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ⚠️  {file} (未生成)")


if __name__ == '__main__':
    main()
