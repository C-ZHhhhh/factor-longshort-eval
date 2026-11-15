"""
简化的多因子对比脚本

[INPUT]:
- 无需手动输入，自动加载清洗后的数据

[OUTPUT]:
- 多因子对比表 (CSV)
- 多因子对比报告 (Markdown)

[POS]:
脚本层包装器，调用评估层的 MultiFactorComparator

[PROTOCOL]:
1. 使用评估层的 MultiFactorComparator 类
2. 所有逻辑封装在评估层，脚本层仅负责调用和输出
"""

import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data import load_clean_data
from evaluation.multi_factor_comparison import MultiFactorComparator
from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("多因子对比 (使用评估层)")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("加载清洗后的数据...")
    df_clean = load_clean_data()

    # 2. 初始化对比器
    comparator = MultiFactorComparator(
        rebalance_freq='2monthly',
        min_holding_periods=12,
        entry_quantile=0.25,
        exit_quantile=0.30,
        cost_bps=20.0
    )

    # 3. 运行对比 (自动运行所有因子 + 合成因子)
    logger.info("开始多因子对比...")
    df_comparison = comparator.compare(
        df_clean=df_clean,
        factor_names=None,  # None = 使用所有因子
        include_composite=True
    )

    # 4. 保存结果
    output_dir = project_root / 'results'
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / 'multi_factor_comparison_refactored.csv'
    df_comparison.to_csv(csv_path, index=False)
    logger.info(f"对比表已保存: {csv_path}")

    # 5. 生成报告
    report_path = output_dir / 'MULTI_FACTOR_COMPARISON_REFACTORED.md'
    report = comparator.generate_report(df_comparison, output_path=str(report_path))

    # 6. 显示结果
    print("\n" + "="*80)
    print("对比结果 (按Sharpe排序):")
    print("="*80)
    print(df_comparison.to_string(index=False))
    print("\n" + "="*80)

    logger.info("多因子对比完成！")
    logger.info(f"CSV: {csv_path}")
    logger.info(f"报告: {report_path}")


if __name__ == '__main__':
    main()
