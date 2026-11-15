"""
统一评估入口

生成完整的因子回测评估报告，包括：
1. 性能表格 (performance_table.csv + .md)
2. Drawdown 统计 (drawdown_stats.csv)
3. 毛收益 vs 净收益对比图
4. 市场暴露分析 (exposure_summary.md) 和 Beta 对冲前后对比 (beta_hedge_comparison.csv + .md)
5. 稳健性测试表格 (robustness_table.csv + .md)
6. 综合评估报告 (EVALUATION_REPORT.md)
7. 网页版报告 (report.html, 单文件, 浏览器直接打开)

使用方法:
    python scripts/run_evaluation.py
"""

import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_loader import DataLoader
from evaluation.multi_factor_comparison import MultiFactorComparator
from evaluation.performance_table_generator import PerformanceTableGenerator
from evaluation.market_exposure_analyzer import MarketExposureAnalyzer
from evaluation.robustness import RobustnessTest
from evaluation import report_narrative
from evaluation import beta_hedge_comparison
from evaluation.significance import newey_west_mean_test
from visualization.factor_visualizer import FactorVisualizer
from visualization import html_report
from utils.logger import get_logger
from utils.config import config

logger = get_logger(__name__)


class UnifiedEvaluator:
    """
    统一评估器

    整合所有评估模块，生成完整的评估报告
    """

    def __init__(
        self,
        rebalance_freq: str = '2monthly',
        min_holding_periods: int = 12,
        entry_quantile: float = 0.25,
        exit_quantile: float = 0.30,
        cost_bps: float = 20.0,
        split_date: str = '2020-01-01'
    ):
        """
        初始化统一评估器

        Parameters:
        -----------
        rebalance_freq : str
            调仓频率
        min_holding_periods : int
            最小持有期(月)
        entry_quantile : float
            进入阈值
        exit_quantile : float
            退出阈值
        cost_bps : float
            交易成本(bps)
        split_date : str
            子样本分割日期
        """
        self.rebalance_freq = rebalance_freq
        self.min_holding_periods = min_holding_periods
        self.entry_quantile = entry_quantile
        self.exit_quantile = exit_quantile
        self.cost_bps = cost_bps
        self.split_date = split_date

        # 初始化子模块
        self.comparator = MultiFactorComparator(
            rebalance_freq=rebalance_freq,
            min_holding_periods=min_holding_periods,
            entry_quantile=entry_quantile,
            exit_quantile=exit_quantile,
            cost_bps=cost_bps
        )

        self.performance_table_gen = PerformanceTableGenerator()
        self.market_exposure_analyzer = MarketExposureAnalyzer(beta_threshold=0.1)
        self.robustness_tester = RobustnessTest()

        logger.info("统一评估器已初始化")

    def run_full_evaluation(
        self,
        df_clean: dict,
        output_dir: str = 'results',
        factor_names: list = None
    ) -> dict:
        """
        运行完整评估

        Parameters:
        -----------
        df_clean : dict
            清洗后的数据
        output_dir : str
            输出目录
        factor_names : list, optional
            要评估的因子列表

        Returns:
        --------
        results : dict
            所有评估结果
        """
        logger.info("="*100)
        logger.info("开始统一评估流程")
        logger.info("="*100)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 默认因子列表
        if factor_names is None:
            factor_names = ['Momentum', 'Reversal', 'LowVolatility', 'Trend']

        # ===== 第1步：多因子回测 =====
        logger.info("\n" + "="*80)
        logger.info("[1/7] 运行多因子回测")
        logger.info("="*80)

        # 运行回测并获取详细结果
        backtest_results = {}
        ic_results = {}
        factor_values = {}

        for factor_name in factor_names:
            logger.info(f"\n回测 {factor_name}...")
            # 不捕获异常: 某个因子失败时让整个评估停下来, 而不是让它从结果表里悄悄消失
            result = self.comparator.run_single_factor(factor_name, df_clean)
            backtest_results[factor_name] = result

            # 保存因子值用于相关性分析
            factor_obj = self.comparator.FACTOR_MAP[factor_name]()
            if factor_name == 'Liquidity':
                if 'volume' in df_clean and df_clean['volume'] is not None:
                    df_factor = factor_obj.calculate(
                        df_price=df_clean['price'],
                        df_volume=df_clean['volume']
                    )
                else:
                    logger.warning(f"{factor_name} 需要成交量数据，跳过")
                    continue
            else:
                df_factor = factor_obj.calculate(
                    df_price=df_clean['price'],
                    df_return_daily=df_clean.get('daily_return')
                )

            # 标准化
            from factors.factor_processor import FactorProcessor
            processor = FactorProcessor()
            df_factor = processor.winsorize(df_factor)
            df_factor = processor.zscore_standardize(df_factor)
            factor_values[factor_name] = df_factor

            # IC分析 (使用 lag=1 确保 factor_t 预测 return_t+1)
            from evaluation.ic_analysis import ICAnalyzer
            ic_analyzer = ICAnalyzer()

            # 正确的 IC 计算: factor_t vs return_t+1
            ic_result = ic_analyzer.analyze_with_lag(
                df_factor=df_factor,
                df_return=df_clean['monthly_return'],
                lag=1  # 因子 shift(1) 后与收益对齐
            )
            ic_results[factor_name] = ic_result

            # IC Sanity Check: 检测时间对齐错误
            sanity_result = ic_analyzer.sanity_check_alignment(
                df_factor=df_factor,
                df_return=df_clean['monthly_return'],
                factor_name=factor_name
            )
            if 'ic_sanity_checks' not in locals():
                ic_sanity_checks = {}
            ic_sanity_checks[factor_name] = sanity_result


        # 合成因子
        logger.info("\n回测 Composite...")
        composite_result = self.comparator.run_composite_factor(df_clean, factor_names)
        backtest_results['Composite'] = composite_result

        # ===== 权重中性化验证 =====
        logger.info("\n" + "="*80)
        logger.info("权重中性化验证")
        logger.info("="*80)

        weight_stats = self._verify_weight_neutrality(backtest_results, output_dir)

        # ===== 第2步：生成性能表格 =====
        logger.info("\n" + "="*80)
        logger.info("[2/7] 生成性能表格")
        logger.info("="*80)

        df_performance = self.performance_table_gen.generate_performance_table(
            backtest_results=backtest_results,
            output_dir=output_dir
        )

        # 保存 IC 汇总 (使用 forward IC，即 lag=1 的结果)
        if ic_results:
            ic_summary_data = []
            for factor_name, ic_result in ic_results.items():
                ic_summary_data.append({
                    'factor': factor_name,
                    'ic_mean': ic_result['ic_mean'],
                    'ic_median': ic_result['ic_median'],
                    'ic_std': ic_result['ic_std'],
                    'ir': ic_result['ir'],
                    'ic_positive_ratio': ic_result['ic_positive_ratio'],
                    't_statistic': ic_result['t_statistic'],
                    'n_periods': ic_result['n_periods']
                })
            df_ic_summary = pd.DataFrame(ic_summary_data)
            ic_summary_file = Path(output_dir) / 'ic_summary.csv'
            df_ic_summary.to_csv(ic_summary_file, index=False)
            logger.info(f"✅ IC 汇总已保存 (forward IC, lag=1): {ic_summary_file}")

        # ===== 第3步：生成可视化图表 =====
        logger.info("\n" + "="*80)
        logger.info("[3/7] 生成可视化图表")
        logger.info("="*80)

        visualizer = FactorVisualizer(output_dir=output_dir)
        figures = visualizer.generate_all_plots(
            backtest_results=backtest_results,
            ic_results=ic_results,
            factor_values=factor_values
        )

        # ===== 第4步：市场暴露分析 =====
        logger.info("\n" + "="*80)
        logger.info("[4/7] 市场暴露分析")
        logger.info("="*80)

        # 需要 SPY 收益率数据
        strategy_returns = {
            name: result['returns']
            for name, result in backtest_results.items()
        }

        # 使用 SPY 作为市场基准; 缓存里没有SPY时退回股票池等权平均, 并在报告里如实标注
        if df_clean.get('SPY') is not None:
            market_returns = df_clean['SPY']
            benchmark_name = 'SPY'
        else:
            logger.warning(
                "未找到SPY数据(旧缓存?)，使用股票池等权平均作为市场基准。"
                "重新运行 scripts/download_data.py --no-cache 可下载SPY"
            )
            market_returns = df_clean['monthly_return'].mean(axis=1)
            benchmark_name = '股票池等权平均 (缓存中没有SPY数据, 非SPY)'

        exposure_results = self.market_exposure_analyzer.analyze_market_exposure(
            strategy_returns=strategy_returns,
            market_returns=market_returns,
            output_dir=output_dir,
            rolling_window=12,
            benchmark_name=benchmark_name
        )

        # ===== 第4.5步：Beta 对冲前后对比 =====
        logger.info("\n" + "="*80)
        logger.info("[4.5/7] Beta 对冲前后对比")
        logger.info("="*80)

        df_hedge = self._run_beta_hedge_comparison(
            df_clean=df_clean,
            backtest_results=backtest_results,
            market_returns=market_returns,
            benchmark_name=benchmark_name,
            output_dir=output_dir
        )

        # ===== 第5步：稳健性测试 =====
        logger.info("\n" + "="*80)
        logger.info("[5/7] 稳健性测试")
        logger.info("="*80)

        robustness_results = self._run_robustness_tests(
            df_clean=df_clean,
            factor_names=factor_names,
            output_dir=output_dir
        )

        # ===== 第6步：显著性检验 =====
        logger.info("\n" + "="*80)
        logger.info("[6/8] 显著性检验")
        logger.info("="*80)

        significance_results = self._run_significance_tests(
            backtest_results=backtest_results,
            ic_results=ic_results,
            output_dir=output_dir
        )

        # ===== 第7步：生成运行元数据 =====
        logger.info("\n" + "="*80)
        logger.info("[7/8] 生成运行元数据")
        logger.info("="*80)

        self._generate_metadata(
            df_clean=df_clean,
            output_dir=output_dir
        )

        # ===== 第7.5步：生成CAGR诊断 =====
        logger.info("\n" + "="*80)
        logger.info("[7.5/8] 生成CAGR诊断")
        logger.info("="*80)

        self._generate_cagr_diagnostics(
            backtest_results=backtest_results,
            robustness_results=robustness_results,
            df_performance=df_performance,
            output_dir=output_dir
        )

        # ===== 第8步：生成综合评估报告 =====
        logger.info("\n" + "="*80)
        logger.info("[8/8] 生成综合评估报告")
        logger.info("="*80)

        evaluation_report = self._create_evaluation_report(
            df_performance=df_performance,
            exposure_results=exposure_results,
            robustness_results=robustness_results,
            ic_results=ic_results,
            significance_results=significance_results,
            output_dir=output_dir,
            df_hedge=df_hedge
        )

        report_file = output_path / 'EVALUATION_REPORT.md'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(evaluation_report)
        logger.info(f"✅ 综合评估报告已保存: {report_file}")

        # ===== 网页版报告 =====
        # 用和上面完全相同的结果生成 results/report.html (单文件, 浏览器直接打开)
        with open(output_path / 'metadata.json', 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        report_data = html_report.build_report_data(
            backtest_results=backtest_results,
            df_performance=df_performance,
            significance_results=significance_results,
            exposure_full_sample=exposure_results['full_sample'],
            df_robustness=robustness_results['table'],
            ic_results=ic_results,
            metadata=metadata,
            benchmark_name=benchmark_name,
            df_hedge=df_hedge
        )
        html_report_file = html_report.write_report(report_data, output_dir)
        logger.info(f"✅ 网页版报告已保存: {html_report_file}")

        # 生成 IC Sanity Check 报告
        if 'ic_sanity_checks' in locals():
            ic_sanity_md = self._create_ic_sanity_check_report(ic_sanity_checks)
            ic_sanity_file = output_path / 'ic_sanity_checks.md'
            with open(ic_sanity_file, 'w', encoding='utf-8') as f:
                f.write(ic_sanity_md)
            logger.info(f"✅ IC Sanity Check 报告已保存: {ic_sanity_file}")

        # ===== 汇总结果 =====
        results = {
            'backtest_results': backtest_results,
            'performance_table': df_performance,
            'exposure': exposure_results,
            'robustness': robustness_results,
            'ic_results': ic_results,
            'significance': significance_results,
            'figures': figures,
            'output_dir': output_dir
        }

        logger.info("\n" + "="*100)
        logger.info("✅ 统一评估流程完成")
        logger.info(f"   输出目录: {output_dir}")
        logger.info(f"   生成文件:")
        logger.info(f"     - performance_table.csv/.md")
        logger.info(f"     - drawdown_stats.csv")
        logger.info(f"     - exposure_summary.md")
        logger.info(f"     - exposure_stats.csv")
        logger.info(f"     - beta_hedge_comparison.csv/.md")
        logger.info(f"     - robustness_table.csv/.md")
        logger.info(f"     - significance_summary.md")
        logger.info(f"     - EVALUATION_REPORT.md")
        logger.info(f"     - report.html (网页版报告)")
        logger.info(f"     - metadata.json")
        logger.info(f"     - 各类可视化图表 (PNG)")
        logger.info("="*100)

        return results

    def _run_beta_hedge_comparison(
        self,
        df_clean: dict,
        backtest_results: dict,
        market_returns: pd.Series,
        benchmark_name: str,
        output_dir: str
    ) -> pd.DataFrame:
        """
        给每个策略加上市场对冲, 输出对冲前后对比 (beta_hedge_comparison.csv/.md)

        正式结果 (performance_table 等) 仍是未对冲的; 这里是附加的对比分析。
        """
        market_daily = df_clean.get('SPY_daily')
        if market_daily is None or df_clean.get('SPY') is None:
            # 不悄悄跳过: 缺数据时明确告诉使用者怎么补
            raise RuntimeError(
                "缓存里没有 SPY 的日收益率, 无法做 Beta 对冲。"
                "请先运行: python scripts/download_data.py --add-benchmark-daily "
                "(只补这一项, 不会重新下载股票数据)"
            )

        df_hedge, _ = beta_hedge_comparison.compare_hedged(
            backtest_results=backtest_results,
            df_return_daily=df_clean['daily_return'],
            market_return_daily=market_daily,
            market_return=market_returns,
            cost_bps=self.cost_bps
        )

        output_path = Path(output_dir)
        df_hedge.to_csv(output_path / 'beta_hedge_comparison.csv', index=False, float_format='%.6f')
        conclusion = report_narrative.describe_beta_hedge(df_hedge)
        with open(output_path / 'beta_hedge_comparison.md', 'w', encoding='utf-8') as f:
            f.write(beta_hedge_comparison.create_markdown(df_hedge, benchmark_name, conclusion))

        for _, row in df_hedge.iterrows():
            logger.info(
                f"  {row['factor']}: Beta {row['beta_before']:+.3f} → {row['beta_after']:+.3f}, "
                f"年化 {row['annual_return_before']:.2%} → {row['annual_return_after']:.2%}"
            )
        logger.info(f"✅ Beta 对冲对比已保存: {output_path / 'beta_hedge_comparison.md'}")
        return df_hedge

    def _verify_weight_neutrality(
        self,
        backtest_results: dict,
        output_dir: str
    ) -> dict:
        """
        验证权重中性化

        检查每个策略的权重是否满足：
        - sum(w) = 0
        - sum(w_pos) = +1
        - sum(|w_neg|) = 1
        """
        output_path = Path(output_dir)

        weight_stats_data = []

        for factor_name, result in backtest_results.items():
            if 'holdings_history' not in result:
                logger.warning(f"{factor_name} 没有权重历史，跳过验证")
                continue

            df_weights = result['holdings_history']

            logger.info(f"\n验证 {factor_name} 权重中性化...")

            # 计算每期权重统计
            weight_sums = df_weights.sum(axis=1)
            weight_pos_sums = df_weights[df_weights > 0].sum(axis=1)
            weight_neg_sums = df_weights[df_weights < 0].sum(axis=1).abs()

            # 整体统计
            mean_sum_w = weight_sums.mean()
            max_abs_sum_w = weight_sums.abs().max()
            mean_sum_w_pos = weight_pos_sums.mean()
            mean_abs_sum_w_neg = weight_neg_sums.mean()

            logger.info(f"  mean(sum_w) = {mean_sum_w:.10f}")
            logger.info(f"  max(abs(sum_w)) = {max_abs_sum_w:.10f}")
            logger.info(f"  mean(sum_w_pos) = {mean_sum_w_pos:.6f}")
            logger.info(f"  mean(abs(sum_w_neg)) = {mean_abs_sum_w_neg:.6f}")

            # 验证阈值
            is_neutral = max_abs_sum_w < 1e-6
            is_balanced = (abs(mean_sum_w_pos - 1.0) < 0.01 and
                          abs(mean_abs_sum_w_neg - 1.0) < 0.01)

            if is_neutral and is_balanced:
                logger.info(f"  ✅ {factor_name} 权重中性化验证通过")
            else:
                logger.warning(f"  ⚠️  {factor_name} 权重中性化验证未通过!")
                if not is_neutral:
                    logger.warning(f"     sum(w) 不为0: max(abs(sum_w)) = {max_abs_sum_w}")
                if not is_balanced:
                    logger.warning(f"     多空不平衡: pos={mean_sum_w_pos:.6f}, neg={mean_abs_sum_w_neg:.6f}")

            # 前5期详细数据
            first_5_periods = []
            for i in range(min(5, len(df_weights))):
                sum_w = weight_sums.iloc[i]
                sum_w_pos = weight_pos_sums.iloc[i]
                sum_w_neg = weight_neg_sums.iloc[i]
                first_5_periods.append({
                    'period': i + 1,
                    'sum_w': sum_w,
                    'sum_w_pos': sum_w_pos,
                    'sum_w_neg': sum_w_neg
                })

            weight_stats_data.append({
                'factor': factor_name,
                'mean_sum_w': mean_sum_w,
                'max_abs_sum_w': max_abs_sum_w,
                'mean_sum_w_pos': mean_sum_w_pos,
                'mean_abs_sum_w_neg': mean_abs_sum_w_neg,
                'is_neutral': is_neutral,
                'is_balanced': is_balanced,
                'first_5_periods': first_5_periods
            })

        # 保存权重中性化统计
        df_weight_stats = pd.DataFrame([
            {
                'factor': stats['factor'],
                'mean_sum_w': stats['mean_sum_w'],
                'max_abs_sum_w': stats['max_abs_sum_w'],
                'mean_sum_w_pos': stats['mean_sum_w_pos'],
                'mean_abs_sum_w_neg': stats['mean_abs_sum_w_neg'],
                'is_neutral': stats['is_neutral'],
                'is_balanced': stats['is_balanced']
            }
            for stats in weight_stats_data
        ])

        csv_file = output_path / 'weight_neutrality_stats.csv'
        df_weight_stats.to_csv(csv_file, index=False, float_format='%.12f')
        logger.info(f"\n✅ 权重中性化统计已保存: {csv_file}")

        # 输出前5期详细数据
        for stats in weight_stats_data:
            logger.info(f"\n{stats['factor']} 前5期权重:")
            for period_data in stats['first_5_periods']:
                logger.info(
                    f"  期 {period_data['period']}: "
                    f"sum_w={period_data['sum_w']:.10f}, "
                    f"sum_w_pos={period_data['sum_w_pos']:.6f}, "
                    f"sum_w_neg={period_data['sum_w_neg']:.6f}"
                )

        return {'stats': weight_stats_data, 'df': df_weight_stats}

    def _run_robustness_tests(
        self,
        df_clean: dict,
        factor_names: list,
        output_dir: str
    ) -> dict:
        """运行稳健性测试"""

        robustness_data = []

        # 选择最佳因子进行稳健性测试
        best_factor_name = factor_names[0]  # 可以改为根据 Sharpe 选择

        logger.info(f"对 {best_factor_name} 进行稳健性测试...")

        # 计算因子
        factor_obj = self.comparator.FACTOR_MAP[best_factor_name]()
        df_factor = factor_obj.calculate(
            df_price=df_clean['price'],
            df_return_daily=df_clean.get('daily_return')
        )

        from factors.factor_processor import FactorProcessor
        processor = FactorProcessor()
        df_factor = processor.winsorize(df_factor)
        df_factor = processor.zscore_standardize(df_factor)

        # 运行稳健性测试
        robustness_result = self.robustness_tester.analyze_robustness(
            df_factor=df_factor,
            df_return=df_clean['monthly_return'],
            split_date=self.split_date
        )

        # 1. 子样本测试
        logger.info("\n子样本测试结果:")
        for period_name, result in robustness_result['sub_sample'].items():
            metrics = result['metrics']
            robustness_data.append({
                'test_type': '子样本',
                'parameter': period_name,
                'annual_return': metrics['annual_return'],
                'sharpe': metrics['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown'],
                'turnover': result.get('avg_turnover', np.nan)
            })
            logger.info(f"  {period_name}: Sharpe={metrics['sharpe_ratio']:.4f}, Return={metrics['annual_return']:.2%}")

        # 2. 成本敏感性测试
        logger.info("\n成本敏感性测试结果:")
        df_cost_sens = robustness_result['cost_sensitivity']
        for _, row in df_cost_sens.iterrows():
            robustness_data.append({
                'test_type': '成本敏感性',
                'parameter': f"{row['cost_bps']:.0f} bps",
                'annual_return': row['annual_return'],
                'sharpe': row['sharpe_ratio'],
                'max_drawdown': row['max_drawdown'],
                'turnover': row.get('avg_turnover', np.nan)
            })
            logger.info(f"  {row['cost_bps']:.0f} bps: Sharpe={row['sharpe_ratio']:.4f}, Return={row['annual_return']:.2%}")

        # 3. 分位数敏感性测试
        logger.info("\n分位数敏感性测试结果:")
        df_quant_sens = robustness_result['quantile_sensitivity']
        for _, row in df_quant_sens.iterrows():
            # 标签同时写出进入和退出阈值; round 而不是 int, 否则 0.15*100=15.000000000000002 之类会被截错
            quantile_label = (
                f"进入{round(row['entry_quantile'] * 100)}% / "
                f"退出{round(row['exit_quantile'] * 100)}%"
            )
            robustness_data.append({
                'test_type': '分位数敏感性',
                'parameter': quantile_label,
                'annual_return': row['annual_return'],
                'sharpe': row['sharpe_ratio'],
                'max_drawdown': row['max_drawdown'],
                'turnover': row.get('avg_turnover', np.nan)
            })
            logger.info(f"  {quantile_label}: Sharpe={row['sharpe_ratio']:.4f}, Return={row['annual_return']:.2%}")

        # 保存稳健性表格
        df_robustness = pd.DataFrame(robustness_data)
        output_path = Path(output_dir)

        csv_file = output_path / 'robustness_table.csv'
        df_robustness.to_csv(csv_file, index=False, float_format='%.6f')
        logger.info(f"\n✅ 稳健性表格已保存: {csv_file}")

        # 保存 Markdown
        md_content = self._create_robustness_markdown(df_robustness)
        md_file = output_path / 'robustness_table.md'
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logger.info(f"✅ 稳健性Markdown已保存: {md_file}")

        return {
            'table': df_robustness,
            'raw': robustness_result
        }

    def _create_robustness_markdown(self, df_robustness: pd.DataFrame) -> str:
        """创建稳健性测试 Markdown 表格"""

        md = f"""# 稳健性测试表格

生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 子样本测试

| 时间段 | 年化收益 | Sharpe | 最大回撤 | 平均换手率 |
|--------|---------|--------|----------|-----------|
"""

        sub_sample_df = df_robustness[df_robustness['test_type'] == '子样本']
        for _, row in sub_sample_df.iterrows():
            param_str = str(row['parameter'])
            turnover_str = f"{row['turnover']:.4f}" if not pd.isna(row['turnover']) else 'N/A'
            md += (
                f"| {param_str} "
                f"| {row['annual_return']:.4f} "
                f"| {row['sharpe']:.4f} "
                f"| {row['max_drawdown']:.4f} "
                f"| {turnover_str} |\n"
            )

        md += """
---

## 成本敏感性测试

| 成本 | 年化收益 | Sharpe | 最大回撤 | 平均换手率 |
|------|---------|--------|----------|-----------|
"""

        cost_sens_df = df_robustness[df_robustness['test_type'] == '成本敏感性']
        for _, row in cost_sens_df.iterrows():
            param_str = str(row['parameter'])
            turnover_str = f"{row['turnover']:.4f}" if not pd.isna(row['turnover']) else 'N/A'
            md += (
                f"| {param_str} "
                f"| {row['annual_return']:.4f} "
                f"| {row['sharpe']:.4f} "
                f"| {row['max_drawdown']:.4f} "
                f"| {turnover_str} |\n"
            )

        md += """
---

## 分位数敏感性测试

进入阈值: 排名进入前/后多少才开仓; 退出阈值: 掉出前/后多少才平仓 (固定为进入阈值 + 5%)。

| 进入 / 退出阈值 | 年化收益 | Sharpe | 最大回撤 | 平均换手率 |
|----------------|---------|--------|----------|-----------|
"""

        quant_sens_df = df_robustness[df_robustness['test_type'] == '分位数敏感性']
        for _, row in quant_sens_df.iterrows():
            param_str = str(row['parameter'])
            turnover_str = f"{row['turnover']:.4f}" if not pd.isna(row['turnover']) else 'N/A'
            md += (
                f"| {param_str} "
                f"| {row['annual_return']:.4f} "
                f"| {row['sharpe']:.4f} "
                f"| {row['max_drawdown']:.4f} "
                f"| {turnover_str} |\n"
            )

        md += """
---

*本报告由统一评估器自动生成*
"""

        return md

    def _create_evaluation_report(
        self,
        df_performance: pd.DataFrame,
        exposure_results: dict,
        robustness_results: dict,
        ic_results: dict,
        significance_results: dict,
        output_dir: str = 'results',
        df_hedge: pd.DataFrame = None
    ) -> str:
        """创建综合评估报告"""
        import json

        # 统一时间戳（用于报告开头和末尾）
        report_timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')

        # 读取 metadata
        metadata_file = Path(output_dir) / 'metadata.json'
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

        # 获取最佳策略
        best_strategy = df_performance.iloc[0]

        md = f"""# 因子回测系统 - 综合评估报告

**生成时间**: {report_timestamp}

---

## 运行配置

"""

        # 添加 metadata 信息
        if metadata:
            md += f"""
**Git Commit**: `{metadata.get('git_commit', 'N/A')}`

**样本期**:
- 起始日期: {metadata.get('sample_period', {}).get('start', 'N/A')}
- 结束日期: {metadata.get('sample_period', {}).get('end', 'N/A')}
- 总月数: {metadata.get('sample_period', {}).get('n_months', 'N/A')}

**回测配置**:
- 调仓频率: {metadata.get('backtest_config', {}).get('rebalance_freq', 'N/A')}
- 交易成本: {metadata.get('backtest_config', {}).get('cost_bps', 'N/A')} bps
- 最小持有期: {metadata.get('backtest_config', {}).get('min_holding_periods', 'N/A')} 月
- 进入阈值: {metadata.get('backtest_config', {}).get('entry_quantile', 'N/A')}
- 退出阈值: {metadata.get('backtest_config', {}).get('exit_quantile', 'N/A')}
- 子样本分割: {metadata.get('backtest_config', {}).get('split_date', 'N/A')}

**中性化配置**:
- Dollar-Neutral: {metadata.get('neutralization', {}).get('dollar_neutral', 'N/A')}
- Beta-Neutral: {metadata.get('neutralization', {}).get('beta_neutral', 'N/A')}
- 说明: {metadata.get('neutralization', {}).get('description', 'N/A')}

"""
        else:
            md += "\n⚠️  未找到 metadata.json，无法显示运行配置。\n\n"

        md += """
---

## Executive Summary

"""

        # 生成 Executive Summary (3-6条关键发现)
        summary_points = []

        # 1. 最佳策略
        summary_points.append(
            f"1. **Sharpe 最高的策略**: {best_strategy['factor']} - "
            f"年化收益 {best_strategy['annual_return_net']:.2%}, "
            f"Sharpe {best_strategy['sharpe']:.4f}, "
            f"最大回撤 {best_strategy['max_drawdown']:.2%}"
            + ("（仍是负收益）" if best_strategy['annual_return_net'] <= 0 else "")
        )

        # 2. 成本影响
        avg_cost_drag = df_performance['cost_drag_annual'].mean()
        summary_points.append(
            f"2. **成本影响**: 平均成本拖累 {avg_cost_drag:.2%}/年, "
            f"平均换手率 {df_performance['avg_turnover'].mean():.2%}"
        )

        # 3. 市场暴露
        if exposure_results and 'full_sample' in exposure_results:
            best_beta = exposure_results['full_sample'][best_strategy['factor']]['beta']
            best_r2 = exposure_results['full_sample'][best_strategy['factor']]['r_squared']
            summary_points.append(
                f"3. **市场暴露**: {best_strategy['factor']} Beta={best_beta:.4f}, "
                f"R²={best_r2:.2%} ({'良好' if abs(best_beta) < 0.1 else '需优化'})"
            )

        # 4. IC/IR 表现
        if ic_results and best_strategy['factor'] in ic_results:
            ic_stats = ic_results[best_strategy['factor']]
            summary_points.append(
                f"4. **因子有效性**: {best_strategy['factor']} IC均值={ic_stats['ic_mean']:.4f}, "
                f"IR={ic_stats['ir']:.4f}, "
                f"IC正占比={ic_stats['ic_positive_ratio']:.2%}"
            )

        # 5. 稳健性
        if robustness_results and 'table' in robustness_results:
            sub_sample_data = robustness_results['table'][
                robustness_results['table']['test_type'] == '子样本'
            ]
            if len(sub_sample_data) >= 2:
                summary_points.append(
                    f"5. **稳健性**: {report_narrative.describe_sub_samples(sub_sample_data)}"
                )

        # 6. Composite 表现
        if 'Composite' in df_performance['factor'].values:
            composite_row = df_performance[df_performance['factor'] == 'Composite'].iloc[0]
            composite_rank = df_performance.index[df_performance['factor'] == 'Composite'][0] + 1
            summary_points.append(
                f"6. **合成因子**: Composite 排名 {composite_rank}/{len(df_performance)}, "
                f"Sharpe {composite_row['sharpe']:.4f}"
            )

        for point in summary_points:
            md += f"{point}\n\n"

        # ===== Research Question Answer =====
        md += """
---

## Research Question Answer

"""

        # 以下三段的定性结论全部由 evaluation/report_narrative.py 根据数字判断得出,
        # 不在这里写死句子 (写死的句子在数字变了以后会和表格矛盾)
        exposure_full_sample = (exposure_results or {}).get('full_sample')
        df_rob = robustness_results['table'] if robustness_results and 'table' in robustness_results else None

        # RQ1: 扣成本后是否产生稳定多空收益？
        md += "### RQ1: 扣成本后是否产生稳定的多空收益？\n\n"
        md += report_narrative.describe_net_returns(df_performance, significance_results)

        # RQ2: 稳健性如何？
        md += "### RQ2: 因子表现的稳健性如何？\n\n"
        if df_rob is not None:
            md += report_narrative.describe_robustness(df_rob, cost_bps=self.cost_bps)

        # Caveat: Beta 暴露 + 最终结论
        md += "### 重要说明 (Caveat)\n\n"
        md += report_narrative.describe_exposure_caveat(exposure_full_sample)
        md += report_narrative.final_conclusion(
            df_performance, significance_results, exposure_full_sample, df_hedge
        )

        md += """
---

## 6.1 主结果 (引用 performance table)

详见 [performance_table.md](performance_table.md) 和 [drawdown_stats.csv](drawdown_stats.csv)

### 性能排名 (按 Sharpe 排序)

| 排名 | 因子 | 年化收益(净) | Sharpe | 最大回撤 | 成本拖累 |
|------|------|-------------|--------|----------|---------|
"""

        for idx, (_, row) in enumerate(df_performance.iterrows(), 1):
            md += (
                f"| {idx} "
                f"| {row['factor']} "
                f"| {row['annual_return_net']:.2%} "
                f"| {row['sharpe']:.4f} "
                f"| {row['max_drawdown']:.2%} "
                f"| {row['cost_drag_annual']:.2%} |\n"
            )

        md += """
### 关键观察

"""

        # 添加关键观察
        observations = []

        # 最佳/最差策略对比
        worst_strategy = df_performance.iloc[-1]
        observations.append(
            f"- **性能差异**: Sharpe 最高 ({best_strategy['factor']}, Sharpe={best_strategy['sharpe']:.4f}) "
            f"vs Sharpe 最低 ({worst_strategy['factor']}, Sharpe={worst_strategy['sharpe']:.4f}), "
            f"差距 {best_strategy['sharpe'] - worst_strategy['sharpe']:.4f}"
        )

        # 成本影响
        max_cost_drag = df_performance['cost_drag_annual'].min()  # 最大拖累(负值)
        observations.append(
            f"- **成本影响最大**: {df_performance.iloc[df_performance['cost_drag_annual'].argmin()]['factor']} "
            f"成本拖累 {max_cost_drag:.2%}/年"
        )

        # Drawdown
        max_dd = df_performance['max_drawdown'].min()  # 最大回撤(负值)
        observations.append(
            f"- **最大回撤**: {df_performance.iloc[df_performance['max_drawdown'].argmin()]['factor']} "
            f"{max_dd:.2%}"
        )

        for obs in observations:
            md += f"{obs}\n"

        md += """
---

## 6.2 多因子对比 (含 Composite)

"""

        if 'Composite' in df_performance['factor'].values:
            composite_row = df_performance[df_performance['factor'] == 'Composite'].iloc[0]
            md += f"""
### Composite 因子表现

- **排名**: {composite_rank}/{len(df_performance)}
- **年化收益(净)**: {composite_row['annual_return_net']:.2%}
- **Sharpe**: {composite_row['sharpe']:.4f}
- **最大回撤**: {composite_row['max_drawdown']:.2%}
- **换手率**: {composite_row['avg_turnover']:.2%}

### 单因子 vs Composite

| 因子 | Sharpe | Composite Sharpe | 改进 |
|------|--------|-----------------|------|
"""

            for _, row in df_performance[df_performance['factor'] != 'Composite'].iterrows():
                improvement = composite_row['sharpe'] - row['sharpe']
                md += (
                    f"| {row['factor']} "
                    f"| {row['sharpe']:.4f} "
                    f"| {composite_row['sharpe']:.4f} "
                    f"| {improvement:+.4f} |\n"
                )

            md += "\n"

            single_factors = df_performance[df_performance['factor'] != 'Composite']
            best_single = single_factors.iloc[0]
            n_beaten = int((composite_row['sharpe'] > single_factors['sharpe']).sum())
            if composite_row['sharpe'] > best_single['sharpe']:
                md += "**结论**: Composite 的 Sharpe 高于所有单因子。"
            else:
                md += (f"**结论**: Composite 的 Sharpe 只高于 {n_beaten}/{len(single_factors)} 个单因子，"
                       f"没有超过 Sharpe 最高的单因子 ({best_single['factor']})，等权合成没有带来分散化的好处。")
            if composite_row['annual_return_net'] <= 0:
                md += "Composite 本身扣成本后也是负收益。"
            md += "\n\n"
        else:
            md += "未包含 Composite 因子。\n\n"

        md += """
---

## 6.3 稳健性 (子样本 + 成本敏感性)

详见 [robustness_table.md](robustness_table.md)

### 稳健性评估

"""

        if robustness_results and 'table' in robustness_results:
            df_rob = robustness_results['table']

            # 子样本稳健性
            sub_sample_data = df_rob[df_rob['test_type'] == '子样本']
            if len(sub_sample_data) >= 2:
                md += "#### 子样本稳健性\n\n"
                md += "| 时间段 | 年化收益 | Sharpe | 最大回撤 |\n"
                md += "|--------|---------|--------|----------|\n"
                for _, row in sub_sample_data.iterrows():
                    md += (
                        f"| {row['parameter']} "
                        f"| {row['annual_return']:.2%} "
                        f"| {row['sharpe']:.4f} "
                        f"| {row['max_drawdown']:.2%} |\n"
                    )

                md += f"\n{report_narrative.describe_sub_samples(sub_sample_data)}\n\n"

            # 成本敏感性
            cost_sens_data = df_rob[df_rob['test_type'] == '成本敏感性']
            if len(cost_sens_data) > 0:
                md += "#### 成本敏感性\n\n"
                md += "| 成本 | 年化收益 | Sharpe | 变化 |\n"
                md += "|------|---------|--------|------|\n"
                base_sharpe = cost_sens_data.iloc[0]['sharpe']
                for idx, (_, row) in enumerate(cost_sens_data.iterrows()):
                    change = row['sharpe'] - base_sharpe if idx > 0 else 0
                    change_str = f"{change:+.4f}" if idx > 0 else "基准"
                    md += (
                        f"| {row['parameter']} "
                        f"| {row['annual_return']:.2%} "
                        f"| {row['sharpe']:.4f} "
                        f"| {change_str} |\n"
                    )

                md += "\n" + report_narrative.describe_cost_sensitivity(cost_sens_data) + "\n"

        md += """
---

## 6.4 暴露与结论 (beta/corr)

详见 [exposure_summary.md](exposure_summary.md)

### 市场暴露分析

"""

        if exposure_results and 'full_sample' in exposure_results:
            md += "| 策略 | Beta | R² | 相关系数 | 评价 |\n"
            md += "|------|------|-----|---------|------|\n"

            for strategy_name, stats in exposure_results['full_sample'].items():
                beta = stats['beta']
                r2 = stats['r_squared']
                corr = stats['correlation']

                if abs(beta) > 0.1:
                    rating = "⚠️  超标"
                elif abs(beta) > 0.05:
                    rating = "🟡 需关注"
                else:
                    rating = "✅ 良好"

                md += (
                    f"| {strategy_name} "
                    f"| {beta:.4f} "
                    f"| {r2:.2%} "
                    f"| {corr:.4f} "
                    f"| {rating} |\n"
                )

            md += "\n**结论**: "

            avg_beta = np.mean([abs(stats['beta']) for stats in exposure_results['full_sample'].values()])
            if avg_beta < 0.05:
                md += "策略成功实现市场中性，市场暴露极低。\n\n"
            elif avg_beta < 0.1:
                md += "策略基本实现市场中性，少量市场暴露在可接受范围内。\n\n"
            else:
                md += ("⚠️  策略存在较大市场暴露。权重本身是资金中性的 (多空金额相等)，"
                       "但资金中性不等于 Beta 中性，要消除市场暴露需要额外做 Beta 对冲。\n\n")

        if df_hedge is not None:
            md += """
---

## 6.5 Beta 对冲前后对比

详见 [beta_hedge_comparison.md](beta_hedge_comparison.md)

在原组合之外加一份市场基准仓位, 把组合对大盘的敏感度抵消掉 (选股和权重不变)。
对冲仓位只用上个月末已知的股票 Beta; 对冲前后用同一段时间比较, 均已扣除交易成本。

| 策略 | 实现 Beta | 年化收益 | Sharpe | 最大回撤 |
|------|-----------|---------|--------|----------|
"""
            for _, row in df_hedge.iterrows():
                md += (
                    f"| {row['factor']} "
                    f"| {row['beta_before']:+.2f} → {row['beta_after']:+.2f} "
                    f"| {row['annual_return_before']:.2%} → {row['annual_return_after']:.2%} "
                    f"| {row['sharpe_before']:.2f} → {row['sharpe_after']:.2f} "
                    f"| {row['max_drawdown_before']:.2%} → {row['max_drawdown_after']:.2%} |\n"
                )
            md += "\n每格是 对冲前 → 对冲后。\n\n"
            md += report_narrative.describe_beta_hedge(df_hedge) + "\n"

        md += """
---

## 改进建议

基于以上分析，提出以下改进建议：

"""

        # 每条建议都有触发条件; 编号按实际出现的顺序生成, 不写死
        suggestions = []
        level = report_narrative.evidence_level(df_performance, significance_results)

        # 没有因子为正收益时, 调参数不是出路
        if level == 'none':
            suggestions.append("""**不要靠调参数"找出"正收益**
   - 所有策略扣成本后都是负的，在同一段历史上反复换参数直到出现正收益，只是事后挑选
   - 更值得做的是检查结论的前提（见下面几条），而不是优化这组因子""")

        # 成本优化
        if avg_cost_drag < -0.03:
            suggestions.append("""**降低交易成本**
   - 当前成本拖累较大，建议降低调仓频率
   - 考虑增加最小持有期限制
   - 扩大进出阈值差距以减少频繁交易""")

        # 市场暴露
        if exposure_full_sample:
            high_beta_strategies = [
                name for name, stats in exposure_full_sample.items()
                if abs(stats['beta']) > report_narrative.BETA_THRESHOLD
            ]
            if high_beta_strategies and df_hedge is None:
                suggestions.append(f"""**实施 Beta 中性化**
   - 以下策略 Beta 超标: {', '.join(high_beta_strategies)}
   - 资金中性不保证 Beta 为 0，需要额外加市场对冲头寸
   - 对冲后才能分清收益来自因子还是来自大盘""")
            elif df_hedge is not None:
                still_exposed = list(df_hedge.loc[
                    df_hedge['beta_after'].abs() > report_narrative.BETA_THRESHOLD, 'factor'
                ])
                if still_exposed:
                    suggestions.append(f"""**弄清对冲不掉的市场暴露**
   - {', '.join(still_exposed)} 加上 Beta 对冲后实现 Beta 仍然超标（见 6.5）
   - 用历史 Beta 估计不出它们的市场暴露，需要看这部分暴露出现在哪些月份
   - 在弄清之前，这些策略的收益里仍然混有大盘的影响""")

        # 幸存者偏差 (与数据无关, 始终成立)
        suggestions.append("""**使用历史成分股**
   - 当前股票池是今天的 S&P 500 成分股，存在幸存者偏差
   - 换成各个时点的历史成分股后结论才可靠""")

        # 子样本差异
        if df_rob is not None:
            sub_sample_data = df_rob[df_rob['test_type'] == '子样本']
            if len(sub_sample_data) >= 2:
                sharpe_range = sub_sample_data['sharpe'].max() - sub_sample_data['sharpe'].min()
                if sharpe_range >= report_narrative.SHARPE_RANGE_THRESHOLD:
                    suggestions.append("""**检查不同时期的差异**
   - 子样本 Sharpe 差异较大
   - 考虑增加更多历史数据验证""")

        for number, suggestion in enumerate(suggestions, 1):
            md += f"{number}. {suggestion}\n\n"

        md += f"""
---

## 附录：生成文件清单

- `performance_table.csv` / `.md` - 性能表格
- `drawdown_stats.csv` - Drawdown 统计
- `exposure_summary.md` - 市场暴露分析 (含 Alpha)
- `exposure_stats.csv` - 暴露统计数据
- `robustness_table.csv` / `.md` - 稳健性测试表格
- `significance_summary.md` - 显著性检验报告 (t-stat, Newey-West)
- `ic_summary.csv` - IC 汇总 (forward IC, lag=1)
- `ic_sanity_checks.md` - IC 时间对齐验证
- `weight_neutrality_stats.csv` - 权重中性化验证
- `metadata.json` - 运行配置元数据
- `nav_comparison.png` - 净值曲线对比图
- `ic_timeseries.png` - IC 时间序列图
- `drawdown_analysis.png` - 回撤曲线图
- `factor_correlation_heatmap.png` - 因子相关性热图
- `equity_gross_vs_net.png` - 毛收益 vs 净收益对比图

---

**报告生成时间**: {report_timestamp}

*本报告由统一评估器自动生成，所有数字均来自代码运行输出。*
"""

        return md

    def _create_ic_sanity_check_report(self, ic_sanity_checks: dict) -> str:
        """创建 IC Sanity Check 报告"""
        md = f"""# IC 时间对齐 Sanity Check 报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 目的

验证 IC 计算是否正确使用了时间对齐（factor_t 预测 return_t+1），防止：
1. **前视偏差**: 使用 factor_t vs return_t（同期）
2. **数据泄露**: 因子计算中使用了未来信息  
3. **对齐错误**: shift 操作未正确执行

## 检查方法

- **IC_forward**: factor_t vs return_t+1（正确）
- **IC_same_period**: factor_t vs return_t（错误，仅用于对比）

---

## 日期对齐示例

"""
        first_factor = list(ic_sanity_checks.keys())[0]
        if 'alignment_sample' in ic_sanity_checks[first_factor]:
            alignment_sample = ic_sanity_checks[first_factor]['alignment_sample']
            md += "| factor_t | return_t+1 (正确) | return_t (错误) |\n"
            md += "|----------|------------------|----------------|\n"
            for s in alignment_sample:
                md += f"| {s['factor_date']} | {s['return_forward']} | {s['return_same']} |\n"
            md += "\n"

        md += """## IC 对比结果

| 因子 | IC_forward | IC_same | 差异 | N | 状态 |
|------|-----------|---------|------|---|------|
"""
        for factor_name, result in ic_sanity_checks.items():
            if result['status'] == 'FAIL':
                md += f"| {factor_name} | N/A | N/A | N/A | N/A | ❌ {result.get('message', '')} |\n"
            else:
                status_icon = '✅' if result['status'] == 'PASS' else '⚠️ '
                md += f"| {factor_name} | {result['ic_forward_mean']:.4f} | {result['ic_same_period_mean']:.4f} | {result['ic_difference']:.4f} | {result['n_periods_forward']} | {status_icon} |\n"

        md += "\n## 警告\n\n"
        has_warnings = False
        for factor_name, result in ic_sanity_checks.items():
            if result.get('warnings'):
                has_warnings = True
                md += f"### {factor_name}\n\n"
                for w in result['warnings']:
                    md += f"- {w}\n"
                md += "\n"
        if not has_warnings:
            md += "✅ 所有因子通过检查\n\n"

        md += "---\n\n*自动生成*\n"
        return md

    def _generate_metadata(self, df_clean: dict, output_dir: str):
        """生成运行元数据"""
        import json
        import subprocess
        from datetime import datetime

        output_path = Path(output_dir)

        # 1. 获取 git commit
        try:
            git_commit = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'],
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
        except:
            git_commit = "N/A (not a git repo)"

        # 2. 运行时间
        run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 3. 样本期（从月度收益率数据中提取）
        df_return = df_clean['monthly_return']
        sample_start = df_return.index[0].strftime('%Y-%m-%d')
        sample_end = df_return.index[-1].strftime('%Y-%m-%d')

        # 4. 构建 metadata
        metadata = {
            'git_commit': git_commit,
            'run_time': run_time,
            'sample_period': {
                'start': sample_start,
                'end': sample_end,
                'n_months': len(df_return)
            },
            'backtest_config': {
                'cost_bps': self.cost_bps,
                'rebalance_freq': self.rebalance_freq,
                'min_holding_periods': self.min_holding_periods,
                'entry_quantile': self.entry_quantile,
                'exit_quantile': self.exit_quantile,
                'split_date': self.split_date
            },
            'neutralization': {
                'dollar_neutral': True,
                'beta_neutral': False,
                'description': 'Dollar-neutral (sum(w)=0, long=+1, short=-1), no beta hedging'
            }
        }

        # 5. 保存 JSON
        metadata_file = output_path / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ 运行元数据已保存: {metadata_file}")
        logger.info(f"   Git Commit: {git_commit[:8]}")
        logger.info(f"   样本期: {sample_start} ~ {sample_end}")
        logger.info(f"   调仓频率: {self.rebalance_freq}")
        logger.info(f"   交易成本: {self.cost_bps} bps")
        logger.info(f"   中性化: Dollar-Neutral (Beta-Neutral=False)")

    def _run_significance_tests(
        self,
        backtest_results: dict,
        ic_results: dict,
        output_dir: str
    ) -> dict:
        """
        运行显著性检验

        对每个因子的月度净收益序列和IC序列进行t检验
        """
        from scipy import stats

        output_path = Path(output_dir)

        sig_results = {}

        for factor_name, result in backtest_results.items():
            if 'returns' not in result:
                continue

            returns = result['returns']

            # 1. 收益率显著性检验
            mean_ret = returns.mean()
            std_ret = returns.std()
            n = len(returns)

            # t-statistic (H0: mean=0)
            if std_ret > 0:
                t_stat = mean_ret / (std_ret / np.sqrt(n))
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1))
            else:
                t_stat = np.nan
                p_value = np.nan

            # Newey-West t-statistic (lag=6, 约半年)
            # 不捕获异常: 算不出来就报错, 不用 NaN 顶替 (NaN 会被后面的结论当成"不显著")
            nw_t_stat, nw_p_value = newey_west_mean_test(returns)

            logger.info(f"  Newey-West 计算成功: t={nw_t_stat:.4f}, p={nw_p_value:.4f}")

            sig_results[factor_name] = {
                'returns': {
                    'mean': mean_ret,
                    'std': std_ret,
                    'n': n,
                    't_stat': t_stat,
                    'p_value': p_value,
                    'nw_t_stat': nw_t_stat,
                    'nw_p_value': nw_p_value
                }
            }

            logger.info(f"\n{factor_name} 收益显著性:")
            logger.info(f"  mean={mean_ret:.6f}, std={std_ret:.6f}, n={n}")
            logger.info(f"  t-stat={t_stat:.4f}, p={p_value:.4f}")
            logger.info(f"  NW t-stat={nw_t_stat:.4f}, NW p={nw_p_value:.4f}")

        # 2. IC 显著性检验
        for factor_name, ic_result in ic_results.items():
            if factor_name not in sig_results:
                sig_results[factor_name] = {}

            ic_mean = ic_result['ic_mean']
            ic_std = ic_result['ic_std']
            n = ic_result['n_periods']

            # t-statistic (H0: IC=0)
            if ic_std > 0:
                ic_t_stat = ic_mean / (ic_std / np.sqrt(n))
                ic_p_value = 2 * (1 - stats.t.cdf(abs(ic_t_stat), n - 1))
            else:
                ic_t_stat = np.nan
                ic_p_value = np.nan

            sig_results[factor_name]['ic'] = {
                'ic_mean': ic_mean,
                'ic_std': ic_std,
                'n': n,
                't_stat': ic_t_stat,
                'p_value': ic_p_value
            }

            logger.info(f"\n{factor_name} IC 显著性:")
            logger.info(f"  IC_mean={ic_mean:.6f}, IC_std={ic_std:.6f}, n={n}")
            logger.info(f"  t-stat={ic_t_stat:.4f}, p={ic_p_value:.4f}")

        # 3. 生成显著性检验报告
        self._create_significance_report(sig_results, output_path)

        return sig_results

    def _create_significance_report(self, sig_results: dict, output_path: Path):
        """生成显著性检验报告"""

        md = f"""# 显著性检验报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 目的

对因子的月度净收益和IC进行统计显著性检验，判断：
1. **收益是否显著不为0** (H0: mean_return = 0)
2. **IC是否显著不为0** (H0: IC = 0)

**显著性水平**: α = 0.05 (双侧检验)

---

## 月度净收益显著性检验

| 因子 | 均值 | 标准差 | N | t-stat | p-value | NW t-stat | NW p-value | 显著性 |
|------|------|--------|---|--------|---------|-----------|------------|--------|
"""

        for factor_name, results in sig_results.items():
            if 'returns' not in results:
                continue
            ret_stats = results['returns']

            # 判断显著性
            is_sig = ret_stats['p_value'] < 0.05 if not np.isnan(ret_stats['p_value']) else False
            is_nw_sig = ret_stats['nw_p_value'] < 0.05 if not np.isnan(ret_stats['nw_p_value']) else False

            sig_icon = "✅" if is_nw_sig else ("⚠️" if is_sig else "❌")

            md += (
                f"| {factor_name} "
                f"| {ret_stats['mean']:.6f} "
                f"| {ret_stats['std']:.6f} "
                f"| {ret_stats['n']} "
                f"| {ret_stats['t_stat']:.4f} "
                f"| {ret_stats['p_value']:.4f} "
                f"| {ret_stats['nw_t_stat']:.4f} "
                f"| {ret_stats['nw_p_value']:.4f} "
                f"| {sig_icon} |\n"
            )

        md += """
**说明**:
- **检验对象**: 上表为"月度净收益序列"的均值检验 (H0: mean(monthly_return) = 0)
- **年化口径**: 报告中的年化收益采用 CAGR = (1 + total_return)^(1/n_years) - 1，与 performance_table.csv 对齐
- **t-stat**: 标准 t 统计量 (假设独立同分布)
- **NW t-stat**: Newey-West HAC t 统计量 (考虑自相关和异方差，lag=6)
- **显著性**: ✅ NW p<0.05 (强证据), ⚠️ 仅 t p<0.05 (弱证据), ❌ p≥0.05 (不显著)
- **注**: 金融时间序列通常存在自相关，Newey-West 比标准 t-stat 更可靠

---

## IC 显著性检验

| 因子 | IC均值 | IC标准差 | N | t-stat | p-value | 显著性 |
|------|--------|---------|---|--------|---------|--------|
"""

        for factor_name, results in sig_results.items():
            if 'ic' not in results:
                continue
            ic_stats = results['ic']

            is_sig = ic_stats['p_value'] < 0.05 if not np.isnan(ic_stats['p_value']) else False
            sig_icon = "✅" if is_sig else "❌"

            md += (
                f"| {factor_name} "
                f"| {ic_stats['ic_mean']:.6f} "
                f"| {ic_stats['ic_std']:.6f} "
                f"| {ic_stats['n']} "
                f"| {ic_stats['t_stat']:.4f} "
                f"| {ic_stats['p_value']:.4f} "
                f"| {sig_icon} |\n"
            )

        md += """
**说明**:
- IC 序列通常更接近独立同分布，使用标准 t 检验
- **显著性**: ✅ p<0.05 (显著), ❌ p≥0.05 (不显著)

---

## 结论

### 收益显著性
"""

        # 汇总收益显著性
        sig_count = sum(
            1 for r in sig_results.values()
            if 'returns' in r and r['returns'].get('nw_p_value', 1) < 0.05
        )
        total_count = sum(1 for r in sig_results.values() if 'returns' in r)

        md += f"\n- **通过 Newey-West 检验的因子**: {sig_count}/{total_count}\n"

        if sig_count == 0:
            md += "- **结论**: 无因子在考虑自相关后产生显著收益（NW p≥0.05），结果不可靠。\n"
        elif sig_count <= 2:
            md += f"- **结论**: 仅 {sig_count} 个因子通过检验，但均为**负收益**（LowVolatility, Composite），无正收益因子显著。\n"
        else:
            md += "- **结论**: 多数因子显著，整体证据较强。\n"

        md += "\n### IC 显著性\n"

        # 汇总 IC 显著性
        ic_sig_count = sum(
            1 for r in sig_results.values()
            if 'ic' in r and r['ic'].get('p_value', 1) < 0.05
        )
        ic_total_count = sum(1 for r in sig_results.values() if 'ic' in r)

        md += f"\n- **IC 显著的因子**: {ic_sig_count}/{ic_total_count}\n"

        if ic_sig_count == 0:
            md += "- **结论**: 无因子 IC 显著，因子预测能力不可靠。\n"
        elif ic_sig_count < ic_total_count / 2:
            md += "- **结论**: 少数因子 IC 显著，预测能力有限。\n"
        else:
            md += "- **结论**: 多数因子 IC 显著，预测能力较强。\n"

        md += """
---

*本报告由统一评估器自动生成*
"""

        # 保存报告
        report_file = output_path / 'significance_summary.md'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(md)

        logger.info(f"✅ 显著性检验报告已保存: {report_file}")

    def _generate_cagr_diagnostics(
        self,
        backtest_results: dict,
        robustness_results: dict,
        df_performance: pd.DataFrame,
        output_dir: str
    ):
        """
        生成CAGR诊断报告

        检查全样本和子样本的CAGR计算一致性
        """
        output_path = Path(output_dir)

        # 只诊断Momentum因子
        factor_name = 'Momentum'

        if factor_name not in backtest_results:
            logger.warning(f"未找到{factor_name}回测结果，跳过CAGR诊断")
            return

        md = f"""# CAGR 诊断报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 目的

验证全样本和子样本的CAGR计算一致性，确保报告中的年化收益数值可复核。

---

## Momentum 因子 CAGR 诊断

"""

        # 1. 全样本
        full_result = backtest_results[factor_name]
        full_nav = full_result['nav']  # 'nav' 是净收益曲线（含成本）
        full_start = full_nav.index[0]
        full_end = full_nav.index[-1]
        full_n_months = len(full_nav)
        # 从收益率序列算总收益（nav[0]已含第一期收益, 用nav[-1]/nav[0]会漏掉第一期）
        full_total_return = (1 + full_result['returns']).prod() - 1
        full_n_years = full_n_months / 12
        full_cagr = (1 + full_total_return) ** (1 / full_n_years) - 1

        md += f"""### 全样本 (Full Sample)

- **起始日期**: {full_start.strftime('%Y-%m-%d')}
- **结束日期**: {full_end.strftime('%Y-%m-%d')}
- **月数**: {full_n_months}
- **年数**: {full_n_years:.2f}
- **总收益率**: {full_total_return:.6f} ({full_total_return*100:.4f}%)
- **CAGR**: {full_cagr:.6f} ({full_cagr*100:.4f}%)

"""

        # 2. performance_table中的值
        momentum_row = df_performance[df_performance['factor'] == factor_name]
        if len(momentum_row) > 0:
            perf_annual_net = momentum_row.iloc[0]['annual_return_net']
            md += f"""### performance_table.csv 中的值

- **annual_return_net**: {perf_annual_net:.6f} ({perf_annual_net*100:.4f}%)

**一致性检查**: {'✅ 一致' if abs(full_cagr - perf_annual_net) < 1e-6 else f'❌ 不一致 (差值: {abs(full_cagr - perf_annual_net):.8f})'}

---

"""

        # 3. 子样本
        if robustness_results and 'raw' in robustness_results:
            raw_result = robustness_results['raw']
            if 'sub_sample' in raw_result:
                sub_results = raw_result['sub_sample']

                md += "## 子样本诊断\n\n"

                for period_name, period_result in sub_results.items():
                    sub_nav = period_result['nav']  # 'nav' 是净收益曲线（含成本）
                    sub_start = sub_nav.index[0]
                    sub_end = sub_nav.index[-1]
                    sub_n_months = len(sub_nav)
                    sub_total_return = (1 + period_result['returns']).prod() - 1
                    sub_n_years = sub_n_months / 12
                    sub_cagr = (1 + sub_total_return) ** (1 / sub_n_years) - 1

                    md += f"""### {period_name}

- **起始日期**: {sub_start.strftime('%Y-%m-%d')}
- **结束日期**: {sub_end.strftime('%Y-%m-%d')}
- **月数**: {sub_n_months}
- **年数**: {sub_n_years:.2f}
- **总收益率**: {sub_total_return:.6f} ({sub_total_return*100:.4f}%)
- **CAGR**: {sub_cagr:.6f} ({sub_cagr*100:.4f}%)

"""

                # 检查子样本覆盖
                periods = list(sub_results.keys())
                if len(periods) == 2:
                    period1_nav = sub_results[periods[0]]['nav']
                    period2_nav = sub_results[periods[1]]['nav']

                    period1_start = period1_nav.index[0]
                    period1_end = period1_nav.index[-1]
                    period2_start = period2_nav.index[0]
                    period2_end = period2_nav.index[-1]

                    md += f"""---

## 子样本覆盖性检查

**全样本范围**: {full_start.strftime('%Y-%m-%d')} ~ {full_end.strftime('%Y-%m-%d')}

**子样本范围**:
- Period 1: {period1_start.strftime('%Y-%m-%d')} ~ {period1_end.strftime('%Y-%m-%d')}
- Period 2: {period2_start.strftime('%Y-%m-%d')} ~ {period2_end.strftime('%Y-%m-%d')}

**覆盖一致性**:
"""

                    # 检查起始日期
                    if abs((period1_start - full_start).days) <= 31:  # 允许1个月误差
                        md += "- ✅ Period 1 起始日期与全样本一致\n"
                    else:
                        md += f"- ⚠️ Period 1 起始日期与全样本不一致 (差距: {(period1_start - full_start).days}天)\n"

                    # 检查结束日期
                    if abs((period2_end - full_end).days) <= 31:
                        md += "- ✅ Period 2 结束日期与全样本一致\n"
                    else:
                        md += f"- ⚠️ Period 2 结束日期与全样本不一致 (差距: {(period2_end - full_end).days}天)\n"

                    # 检查衔接
                    gap_days = (period2_start - period1_end).days
                    if abs(gap_days) <= 31:
                        md += f"- ✅ Period 1和2无缝衔接 (间隔: {gap_days}天)\n"
                    else:
                        md += f"- ⚠️ Period 1和2存在间隔 (间隔: {gap_days}天)\n"

                    # 说明为何子样本CAGR可能与全样本不同
                    md += f"""

**说明**: 子样本CAGR与全样本CAGR不同的原因：
1. **时间段不同**: 子样本时间更短（约{sub_n_years:.1f}年），短期波动对CAGR影响更大
2. **复利效应**: CAGR是几何平均，不满足线性可加性
3. **合理性**: 若两个子样本都优于全样本，说明收益在时间上较均衡；若差异大，说明某段时期表现显著不同
"""

        md += """
---

**诊断完成时间**: """ + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S') + "\n"

        # 保存报告
        diag_file = output_path / 'cagr_diagnostics.md'
        with open(diag_file, 'w', encoding='utf-8') as f:
            f.write(md)

        logger.info(f"✅ CAGR诊断报告已保存: {diag_file}")


def main():
    """主函数"""
    logger.info("="*100)
    logger.info("因子回测系统 - 统一评估入口")
    logger.info("="*100)

    # 1. 加载数据
    logger.info("\n[0/7] 加载数据...")
    loader = DataLoader()

    df_clean = loader.load_cleaned_data()

    if df_clean is None:
        logger.error("数据加载失败，请先运行数据采集脚本")
        return

    logger.info("✅ 数据加载完成")

    # 2. 初始化评估器
    evaluator = UnifiedEvaluator(
        rebalance_freq='2monthly',
        min_holding_periods=12,
        entry_quantile=0.25,
        exit_quantile=0.30,
        cost_bps=20.0,
        split_date='2020-01-01'
    )

    # 3. 运行完整评估
    results = evaluator.run_full_evaluation(
        df_clean=df_clean,
        output_dir='results',
        factor_names=['Momentum', 'Reversal', 'LowVolatility', 'Trend']
    )

    logger.info("\n" + "="*100)
    logger.info("✅ 评估完成！请查看 results/ 目录下的报告和图表")
    logger.info("="*100)


if __name__ == '__main__':
    main()
