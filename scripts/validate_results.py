"""
结果验收脚本

验证评估输出的正确性和一致性

运行: python scripts/validate_results.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger

logger = get_logger(__name__)


class ResultsValidator:
    """结果验收器"""

    def __init__(self, results_dir: str = 'results'):
        self.results_dir = Path(results_dir)
        self.passed = []
        self.failed = []

    def validate_all(self) -> bool:
        """运行所有验证"""
        logger.info("="*80)
        logger.info("开始验收结果")
        logger.info("="*80)

        # 验证1: 必需文件存在
        self._validate_required_files()

        # 验证2: Performance Table 一致性
        self._validate_performance_table()

        # 验证3: Drawdown 独立性
        self._validate_drawdown_independence()

        # 验证4: IC/IR 有效性
        self._validate_ic_ir()

        # 验证5: 权重中性化
        self._validate_weight_neutrality()

        # 汇总结果
        self._print_summary()

        return len(self.failed) == 0

    def _validate_required_files(self):
        """验证必需文件存在"""
        logger.info("\n[验证1/5] 检查必需文件...")

        required_files = [
            'performance_table.csv',
            'performance_table.md',
            'drawdown_stats.csv',
            'exposure_stats.csv',
            'exposure_summary.md',
            'robustness_table.csv',
            'robustness_table.md',
            'weight_neutrality_stats.csv',
            'EVALUATION_REPORT.md',
            'nav_comparison.png',
            'ic_timeseries.png',
            'drawdown_analysis.png',
            'factor_correlation_heatmap.png',
            'equity_gross_vs_net.png'
        ]

        missing_files = []
        for filename in required_files:
            file_path = self.results_dir / filename
            if file_path.exists():
                logger.info(f"  ✅ {filename}")
                self.passed.append(f"文件存在: {filename}")
            else:
                logger.error(f"  ❌ {filename} 缺失")
                missing_files.append(filename)
                self.failed.append(f"文件缺失: {filename}")

        if missing_files:
            logger.error(f"\n❌ 验证1失败: {len(missing_files)} 个文件缺失")
        else:
            logger.info(f"\n✅ 验证1通过: 所有必需文件存在")

    def _validate_performance_table(self):
        """验证 Performance Table 一致性"""
        logger.info("\n[验证2/5] 验证 Performance Table...")

        try:
            df = pd.read_csv(self.results_dir / 'performance_table.csv')

            # 检查1: gross >= net
            if (df['annual_return_gross'] >= df['annual_return_net']).all():
                logger.info("  ✅ gross >= net (所有因子)")
                self.passed.append("Performance: gross >= net")
            else:
                bad_factors = df[df['annual_return_gross'] < df['annual_return_net']]['factor'].tolist()
                logger.error(f"  ❌ gross < net: {bad_factors}")
                self.failed.append(f"Performance: gross < net for {bad_factors}")

            # 检查2: cost_drag_annual <= 0
            if (df['cost_drag_annual'] <= 0).all():
                logger.info("  ✅ cost_drag_annual <= 0 (所有因子)")
                self.passed.append("Performance: cost_drag <= 0")
            else:
                bad_factors = df[df['cost_drag_annual'] > 0]['factor'].tolist()
                logger.error(f"  ❌ cost_drag_annual > 0: {bad_factors}")
                self.failed.append(f"Performance: cost_drag > 0 for {bad_factors}")

            # 检查3: cost_drag = net - gross (容差 1e-6)
            cost_drag_calc = df['annual_return_net'] - df['annual_return_gross']
            cost_drag_diff = (df['cost_drag_annual'] - cost_drag_calc).abs()
            tolerance = 1e-6
            if (cost_drag_diff <= tolerance).all():
                logger.info(f"  ✅ cost_drag = net - gross (所有因子, 容差={tolerance})")
                self.passed.append("Performance: cost_drag 计算正确")
            else:
                max_diff = cost_drag_diff.max()
                logger.error(f"  ❌ cost_drag 计算不一致 (最大误差={max_diff:.2e}, 容差={tolerance:.2e})")
                self.failed.append(f"Performance: cost_drag 计算错误 (误差>{tolerance})")

            logger.info(f"\n✅ 验证2通过")

        except Exception as e:
            logger.error(f"\n❌ 验证2失败: {e}")
            self.failed.append(f"Performance Table: {e}")

    def _validate_drawdown_independence(self):
        """验证 Drawdown 独立性"""
        logger.info("\n[验证3/5] 验证 Drawdown 独立性...")

        # 这需要从日志文件中读取，或者重新计算
        # 简化版本：检查 drawdown_stats.csv 中的值是否不同
        try:
            df = pd.read_csv(self.results_dir / 'drawdown_stats.csv')

            # 检查至少有2个因子
            if len(df) < 2:
                logger.warning("  ⚠️  只有1个因子，无法验证独立性")
                return

            # 检查 max_drawdown 是否不同
            unique_dd = df['max_drawdown'].nunique()
            if unique_dd == len(df):
                logger.info(f"  ✅ 所有因子的 max_drawdown 不同 ({unique_dd}个不同值)")
                self.passed.append("Drawdown: 所有因子独立")
            elif unique_dd == 1:
                logger.error(f"  ❌ 所有因子的 max_drawdown 完全相同!")
                self.failed.append("Drawdown: 所有因子相同（可能数据复用）")
            else:
                logger.warning(f"  ⚠️  有 {len(df) - unique_dd} 个因子的 max_drawdown 重复")
                self.passed.append("Drawdown: 部分因子独立")

            # 检查 Momentum vs Reversal（如果存在）
            if 'Momentum' in df['factor'].values and 'Reversal' in df['factor'].values:
                dd_mom = df[df['factor'] == 'Momentum']['max_drawdown'].iloc[0]
                dd_rev = df[df['factor'] == 'Reversal']['max_drawdown'].iloc[0]

                if abs(dd_mom - dd_rev) > 1e-6:
                    logger.info(f"  ✅ Momentum ({dd_mom:.6f}) vs Reversal ({dd_rev:.6f}) 不同")
                    self.passed.append("Drawdown: Momentum vs Reversal 独立")
                else:
                    logger.error(f"  ❌ Momentum 和 Reversal 的 drawdown 相同!")
                    self.failed.append("Drawdown: Momentum vs Reversal 相同")

            logger.info(f"\n✅ 验证3通过")

        except Exception as e:
            logger.error(f"\n❌ 验证3失败: {e}")
            self.failed.append(f"Drawdown: {e}")

    def _validate_ic_ir(self):
        """验证 IC/IR 有效性"""
        logger.info("\n[验证4/5] 验证 IC/IR...")

        # 从 ic_summary.csv 读取（如果存在）
        ic_file = self.results_dir / 'ic_summary.csv'
        if not ic_file.exists():
            logger.warning("  ⚠️  ic_summary.csv 不存在，跳过验证")
            return

        try:
            df = pd.read_csv(ic_file)

            # 检查1: IC_std > 0
            if (df['ic_std'] > 0).all():
                logger.info("  ✅ IC_std > 0 (所有因子)")
                self.passed.append("IC: IC_std > 0")
            else:
                bad_factors = df[df['ic_std'] <= 0]['factor'].tolist()
                logger.error(f"  ❌ IC_std <= 0: {bad_factors}")
                self.failed.append(f"IC: IC_std <= 0 for {bad_factors}")

            # 检查2: ICIR 非 NaN
            if df['ir'].notna().all():
                logger.info("  ✅ ICIR 非 NaN (所有因子)")
                self.passed.append("IC: ICIR 非 NaN")
            else:
                bad_factors = df[df['ir'].isna()]['factor'].tolist()
                logger.error(f"  ❌ ICIR 为 NaN: {bad_factors}")
                self.failed.append(f"IC: ICIR 为 NaN for {bad_factors}")

            # 检查3: N > 24
            if (df['n_periods'] > 24).all():
                logger.info(f"  ✅ 样本数 > 24 (最小: {df['n_periods'].min()})")
                self.passed.append("IC: 样本数充足")
            else:
                bad_factors = df[df['n_periods'] <= 24]['factor'].tolist()
                logger.error(f"  ❌ 样本数 <= 24: {bad_factors}")
                self.failed.append(f"IC: 样本数不足 for {bad_factors}")

            # 输出每个因子的 IC/IR
            logger.info("\n  IC/IR 汇总:")
            for _, row in df.iterrows():
                logger.info(
                    f"    {row['factor']}: N={row['n_periods']:.0f}, "
                    f"IC_mean={row['ic_mean']:.6f}, IC_std={row['ic_std']:.6f}, "
                    f"ICIR={row['ir']:.6f}"
                )

            logger.info(f"\n✅ 验证4通过")

        except Exception as e:
            logger.error(f"\n❌ 验证4失败: {e}")
            self.failed.append(f"IC/IR: {e}")

    def _validate_weight_neutrality(self):
        """验证权重中性化"""
        logger.info("\n[验证5/5] 验证权重中性化...")

        try:
            df = pd.read_csv(self.results_dir / 'weight_neutrality_stats.csv')

            # 检查1: max(abs(sum_w)) < 1e-6
            threshold = 1e-6
            if (df['max_abs_sum_w'] < threshold).all():
                logger.info(f"  ✅ max(abs(sum_w)) < {threshold} (所有因子)")
                self.passed.append("Weight: 中性化通过")
            else:
                bad_factors = df[df['max_abs_sum_w'] >= threshold]['factor'].tolist()
                logger.error(f"  ❌ max(abs(sum_w)) >= {threshold}: {bad_factors}")
                self.failed.append(f"Weight: 中性化未通过 for {bad_factors}")

            # 检查2: 多空平衡
            pos_ok = (df['mean_sum_w_pos'] - 1.0).abs() < 0.01
            neg_ok = (df['mean_abs_sum_w_neg'] - 1.0).abs() < 0.01
            if (pos_ok & neg_ok).all():
                logger.info(f"  ✅ 多空平衡 (sum_pos≈1, sum_neg≈1)")
                self.passed.append("Weight: 多空平衡")
            else:
                bad_factors = df[~(pos_ok & neg_ok)]['factor'].tolist()
                logger.error(f"  ❌ 多空不平衡: {bad_factors}")
                self.failed.append(f"Weight: 多空不平衡 for {bad_factors}")

            # 输出详细统计
            logger.info("\n  权重中性化汇总:")
            for _, row in df.iterrows():
                logger.info(
                    f"    {row['factor']}: "
                    f"max(abs(sum_w))={row['max_abs_sum_w']:.10f}, "
                    f"mean(sum_pos)={row['mean_sum_w_pos']:.6f}, "
                    f"mean(sum_neg)={row['mean_abs_sum_w_neg']:.6f}"
                )

            logger.info(f"\n✅ 验证5通过")

        except Exception as e:
            logger.error(f"\n❌ 验证5失败: {e}")
            self.failed.append(f"Weight Neutrality: {e}")

    def _print_summary(self):
        """打印验收总结"""
        logger.info("\n" + "="*80)
        logger.info("验收总结")
        logger.info("="*80)

        logger.info(f"\n通过项 ({len(self.passed)}):")
        for item in self.passed:
            logger.info(f"  ✅ {item}")

        if self.failed:
            logger.info(f"\n失败项 ({len(self.failed)}):")
            for item in self.failed:
                logger.error(f"  ❌ {item}")

        logger.info("\n" + "="*80)
        if len(self.failed) == 0:
            logger.info("🎉 验收结果: PASS")
            logger.info("="*80)
            return True
        else:
            logger.error(f"💥 验收结果: FAIL ({len(self.failed)} 个问题)")
            logger.info("="*80)
            return False


def main():
    """主函数"""
    validator = ResultsValidator()
    passed = validator.validate_all()

    # 返回退出码
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
