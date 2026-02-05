"""
生成可视化图表脚本

生成4种核心图表：
1. 净值曲线对比图
2. IC时间序列图
3. 回撤曲线图
4. 因子相关性热图
"""

import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import load_clean_data
from evaluation.enhanced_report import EnhancedReportGenerator
from visualization.factor_visualizer import FactorVisualizer
from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("生成可视化图表")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("\n加载清洗后的数据...")
    df_clean = load_clean_data()

    # 2. 初始化增强版报告生成器
    logger.info("\n初始化报告生成器...")
    generator = EnhancedReportGenerator(
        rebalance_freq='2monthly',
        min_holding_periods=12,
        entry_quantile=0.25,
        exit_quantile=0.30,
        cost_bps=20.0
    )

    # 3. 生成增强版报告（获取所有数据）
    logger.info("\n生成评估数据...")
    output_dir = project_root / 'results'
    output_dir.mkdir(exist_ok=True)

    results = generator.generate_enhanced_report(
        df_clean=df_clean,
        factor_names=None,  # None = 使用所有因子
        split_date='2020-01-01',
        output_dir=None  # 暂不保存，只获取数据
    )

    # 4. 准备可视化数据
    logger.info("\n准备可视化数据...")

    # 回测结果（从多因子对比中提取）
    backtest_results = {}
    for factor_name in generator.comparator.FACTOR_MAP.keys():
        if factor_name == 'Composite':
            continue  # 跳过合成因子
        try:
            result = generator.comparator.run_single_factor(factor_name, df_clean)
            backtest_results[factor_name] = result
        except Exception as e:
            logger.warning(f"跳过 {factor_name}: {e}")

    # IC结果
    ic_results = results.get('ic_analysis', {})
    # 移除None值
    ic_results = {k: v for k, v in ic_results.items() if v is not None}

    # 因子值
    factor_values = {}
    for factor_name in generator.comparator.FACTOR_MAP.keys():
        if factor_name == 'Composite':
            continue
        try:
            factor_values[factor_name] = generator._calculate_factor(factor_name, df_clean)
        except Exception as e:
            logger.warning(f"跳过 {factor_name} 因子值: {e}")

    # 5. 初始化可视化器
    logger.info("\n初始化可视化器...")
    visualizer = FactorVisualizer(output_dir=str(output_dir / 'figures'))

    # 6. 生成所有图表
    figures = visualizer.generate_all_plots(
        backtest_results=backtest_results,
        ic_results=ic_results,
        factor_values=factor_values
    )

    # 7. 显示结果
    print("\n" + "="*80)
    print("可视化图表生成完成")
    print("="*80)

    print(f"\n📊 生成的图表:")
    print(f"  1. 净值曲线对比图: {output_dir}/figures/nav_comparison.png")
    print(f"  2. IC时间序列图: {output_dir}/figures/ic_timeseries.png")
    print(f"  3. 回撤曲线图: {output_dir}/figures/drawdown_analysis.png")
    print(f"  4. 因子相关性热图: {output_dir}/figures/factor_correlation_heatmap.png")

    print(f"\n🏆 最佳因子: {results['best_factor']}")
    print(f"\n📁 所有文件保存在: {output_dir}")

    print("\n" + "="*80)
    logger.info("完成!")

    # 关闭所有图表
    visualizer.close_all()


if __name__ == '__main__':
    main()
