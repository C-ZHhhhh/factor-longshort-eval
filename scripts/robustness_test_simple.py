"""
简化的稳健性测试脚本

[INPUT]:
- 无需手动输入，自动加载清洗后的数据

[OUTPUT]:
- 子样本对比表 (CSV)
- 成本敏感性表 (CSV)
- 稳健性测试报告 (Markdown)

[POS]:
脚本层包装器，调用评估层的 RobustnessTest

[PROTOCOL]:
1. 使用评估层的 RobustnessTest 类
2. 所有逻辑封装在评估层，脚本层仅负责调用和输出
"""

import sys
from pathlib import Path
import pandas as pd

# 添加项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data.data_loader import load_clean_data
from factors.momentum import MomentumFactor
from factors.factor_processor import FactorProcessor
from evaluation.robustness import RobustnessTest
from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("稳健性测试 (使用评估层)")
    logger.info("="*80)

    # 1. 加载数据
    logger.info("加载清洗后的数据...")
    df_clean = load_clean_data()

    # 2. 计算因子 (以Momentum为例)
    logger.info("计算Momentum因子...")
    factor = MomentumFactor()
    df_factor = factor.calculate(
        df_price=df_clean['price'],
        df_return_daily=df_clean.get('daily_return')
    )

    # 3. 标准化
    processor = FactorProcessor()
    df_factor = processor.winsorize(df_factor)
    df_factor = processor.zscore_standardize(df_factor)

    # 4. 初始化稳健性测试器
    tester = RobustnessTest()

    # 5. 运行完整的稳健性分析
    logger.info("开始稳健性分析...")
    results = tester.analyze_robustness(
        df_factor=df_factor,
        df_return=df_clean['monthly_return'],
        split_date='2020-01-01'
    )

    # 6. 保存结果
    output_dir = project_root / 'results'
    output_dir.mkdir(exist_ok=True)

    # 子样本测试结果
    logger.info("\n子样本测试结果:")
    sub_sample_data = []
    for period_name, result in results['sub_sample'].items():
        metrics = result['metrics']
        sub_sample_data.append({
            'period': period_name,
            'annual_return': metrics['annual_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'annual_volatility': metrics['annual_volatility'],
            'win_rate': metrics['win_rate']
        })

    df_sub_sample = pd.DataFrame(sub_sample_data)
    sub_sample_path = output_dir / 'robustness_sub_sample_refactored.csv'
    df_sub_sample.to_csv(sub_sample_path, index=False)
    logger.info(f"子样本结果已保存: {sub_sample_path}")
    print("\n" + df_sub_sample.to_string(index=False))

    # 成本敏感性结果
    logger.info("\n成本敏感性测试结果:")
    df_cost = results['cost_sensitivity']
    cost_path = output_dir / 'robustness_cost_sensitivity_refactored.csv'
    df_cost.to_csv(cost_path, index=False)
    logger.info(f"成本敏感性结果已保存: {cost_path}")
    print("\n" + df_cost.to_string(index=False))

    # 分位数敏感性结果
    logger.info("\n分位数敏感性测试结果:")
    df_quantile = results['quantile_sensitivity']
    quantile_path = output_dir / 'robustness_quantile_sensitivity_refactored.csv'
    df_quantile.to_csv(quantile_path, index=False)
    logger.info(f"分位数敏感性结果已保存: {quantile_path}")
    print("\n" + df_quantile.to_string(index=False))

    # 7. 生成报告
    report_path = output_dir / 'ROBUSTNESS_TEST_REFACTORED.md'
    report = f"""# 稳健性测试报告 (重构后)

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试因子**: Momentum
**子样本分割**: 2020-01-01

---

## 子样本测试

{df_sub_sample.to_markdown(index=False)}

---

## 成本敏感性测试

{df_cost.to_markdown(index=False)}

---

## 分位数敏感性测试

{df_quantile.to_markdown(index=False)}

---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"报告已保存: {report_path}")

    logger.info("\n" + "="*80)
    logger.info("稳健性测试完成！")
    logger.info("="*80)


if __name__ == '__main__':
    main()
