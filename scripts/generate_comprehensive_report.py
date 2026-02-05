"""
综合评估报告生成脚本

[INPUT]:
- 无需手动输入，自动加载清洗后的数据

[OUTPUT]:
- 综合评估报告 (Markdown)
- 多因子对比表 (CSV)
- 稳健性测试结果 (CSV)

[POS]:
脚本层包装器，调用评估层的 ComprehensiveReportGenerator

[PROTOCOL]:
1. 使用评估层的 ComprehensiveReportGenerator 类
2. 一次运行生成完整评估报告
3. 整合多因子对比 + 稳健性测试
"""

import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data import load_clean_data
from evaluation.comprehensive_report import ComprehensiveReportGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("综合评估报告生成")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("加载清洗后的数据...")
    df_clean = load_clean_data()

    # 2. 初始化报告生成器
    generator = ComprehensiveReportGenerator(
        rebalance_freq='2monthly',
        min_holding_periods=12,
        entry_quantile=0.25,
        exit_quantile=0.30,
        cost_bps=20.0
    )

    # 3. 生成综合报告
    output_dir = project_root / 'results'
    output_dir.mkdir(exist_ok=True)

    results = generator.generate_comprehensive_report(
        df_clean=df_clean,
        factor_names=None,  # None = 使用所有因子
        split_date='2020-01-01',
        output_dir=str(output_dir)
    )

    # 4. 显示结果摘要
    print("\n" + "="*80)
    print("综合评估报告已生成")
    print("="*80)

    print(f"\n📊 多因子对比:")
    print(results['comparison'][['factor', 'annual_return', 'sharpe_ratio', 'max_drawdown']].to_string(index=False))

    print(f"\n🏆 最佳因子: {results['best_factor']}")

    print(f"\n📁 输出文件:")
    print(f"  - 综合报告: {output_dir}/COMPREHENSIVE_EVALUATION_REPORT.md")
    print(f"  - 对比表: {output_dir}/multi_factor_comparison.csv")
    print(f"  - 稳健性测试: {output_dir}/robustness_*.csv")

    print("\n" + "="*80)
    logger.info("完成!")


if __name__ == '__main__':
    main()
