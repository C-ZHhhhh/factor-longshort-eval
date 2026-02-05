"""
生成增强版综合评估报告

包含：
1. 多因子对比
2. IC/IR分析
3. 因子暴露分析
4. 归因分析（多头/空头收益拆解）
5. 稳健性测试
"""

import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import load_clean_data
from evaluation.enhanced_report import EnhancedReportGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("增强版综合评估报告生成")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("加载清洗后的数据...")
    df_clean = load_clean_data()

    # 2. 初始化增强版报告生成器
    generator = EnhancedReportGenerator(
        rebalance_freq='2monthly',
        min_holding_periods=12,
        entry_quantile=0.25,
        exit_quantile=0.30,
        cost_bps=20.0
    )

    # 3. 生成增强版报告
    output_dir = project_root / 'results'
    output_dir.mkdir(exist_ok=True)

    results = generator.generate_enhanced_report(
        df_clean=df_clean,
        factor_names=None,  # None = 使用所有因子
        split_date='2020-01-01',
        output_dir=str(output_dir)
    )

    # 4. 显示结果摘要
    print("\n" + "="*80)
    print("增强版综合评估报告已生成")
    print("="*80)

    print(f"\n📊 多因子对比:")
    print(results['comparison'][['factor', 'annual_return', 'sharpe_ratio', 'max_drawdown']].to_string(index=False))

    print(f"\n🏆 最佳因子: {results['best_factor']}")

    # IC分析摘要
    if 'ic_analysis' in results:
        print(f"\n📈 IC/IR分析:")
        for factor_name, ic_result in results['ic_analysis'].items():
            if ic_result:
                print(f"  {factor_name}: IR={ic_result['ir']:.4f}, IC均值={ic_result['ic_mean']:.4f}")

    # 暴露分析摘要
    if 'exposure' in results:
        print(f"\n⚖️  暴露分析 (基于{results['best_factor']}):")
        print(f"  市场中性: {'✅ 是' if results['exposure']['neutrality']['is_market_neutral'] else '❌ 否'}")
        print(f"  多空平衡: {'✅ 是' if results['exposure']['balance']['is_balanced'] else '❌ 否'}")

    # 归因分析摘要
    if 'attribution' in results:
        print(f"\n🎯 归因分析 (基于{results['best_factor']}):")
        ls = results['attribution']['long_short_decomposition']
        print(f"  多头Sharpe: {ls['long_sharpe']:.4f}")
        print(f"  空头Sharpe: {ls['short_sharpe']:.4f}")
        print(f"  主要贡献: {'多头' if ls['long_pct'] > 0.6 else '空头' if ls['short_pct'] > 0.6 else '均衡'}")

    print(f"\n📁 输出文件:")
    print(f"  - 增强版报告: {output_dir}/ENHANCED_EVALUATION_REPORT.md")
    print(f"  - 对比表: {output_dir}/multi_factor_comparison.csv")
    print(f"  - IC汇总: {output_dir}/ic_summary.csv")
    print(f"  - 暴露分析: {output_dir}/exposure_*.csv")
    print(f"  - 归因分析: {output_dir}/attribution_*.csv")
    print(f"  - 稳健性测试: {output_dir}/robustness_*.csv")

    print("\n" + "="*80)
    logger.info("完成!")


if __name__ == '__main__':
    main()
