"""
增强版综合评估报告生成器

在原有基础上增加：
1. IC/IR分析
2. 因子暴露分析
3. 归因分析（多头/空头收益拆解）
4. 行业/板块暴露分析

[INPUT]:
- 清洗后的数据 (dict)
- 可选的因子列表

[OUTPUT]:
- 增强版综合评估报告 (包含IC/IR、暴露、归因等深度分析)

[POS]:
评估层增强模块，生成完整的深度因子评估报告

[PROTOCOL]:
1. 继承原有的多因子对比和稳健性测试
2. 新增IC/IR分析、暴露检查、归因分析
3. 生成更详细的评估报告
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import sys

# 添加项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from evaluation.comprehensive_report import ComprehensiveReportGenerator
from evaluation.ic_analysis import ICAnalyzer
from evaluation.exposure_check import ExposureChecker
from evaluation.attribution import AttributionAnalyzer
from portfolio.portfolio_builder import PortfolioBuilder
from utils.logger import get_logger

logger = get_logger(__name__)


class EnhancedReportGenerator(ComprehensiveReportGenerator):
    """
    增强版综合评估报告生成器

    在基础报告之上增加：
    - IC/IR分析
    - 因子暴露分析
    - 归因分析（多头/空头收益拆解）
    - 行业/板块暴露分析（如果有行业数据）
    """

    def __init__(
        self,
        rebalance_freq: str = '2monthly',
        min_holding_periods: int = 12,
        entry_quantile: float = 0.25,
        exit_quantile: float = 0.30,
        cost_bps: float = 20.0
    ):
        """初始化增强版报告生成器"""
        super().__init__(
            rebalance_freq=rebalance_freq,
            min_holding_periods=min_holding_periods,
            entry_quantile=entry_quantile,
            exit_quantile=exit_quantile,
            cost_bps=cost_bps
        )

        # 初始化深度分析模块
        self.ic_analyzer = ICAnalyzer()
        self.exposure_checker = ExposureChecker()
        self.attribution_analyzer = AttributionAnalyzer()

        logger.info("增强版报告生成器已初始化 (包含IC/IR、暴露、归因分析)")

    def generate_enhanced_report(
        self,
        df_clean: dict,
        factor_names: Optional[List[str]] = None,
        split_date: str = '2020-01-01',
        output_dir: Optional[str] = None
    ) -> Dict:
        """
        生成增强版综合评估报告

        Parameters:
        -----------
        df_clean : dict
            清洗后的数据
        factor_names : list, optional
            要对比的因子名称列表
        split_date : str
            子样本分割日期
        output_dir : str, optional
            输出目录

        Returns:
        --------
        result : dict
            包含所有评估结果和报告路径
        """
        logger.info("="*80)
        logger.info("开始生成增强版综合评估报告")
        logger.info("="*80)

        # 1. 调用父类方法生成基础报告
        logger.info("\n[1/5] 生成基础评估报告...")
        base_results = super().generate_comprehensive_report(
            df_clean=df_clean,
            factor_names=factor_names,
            split_date=split_date,
            output_dir=None  # 暂不保存，等所有分析完成
        )

        # 2. IC/IR分析（针对每个因子）
        logger.info("\n[2/5] 运行IC/IR分析...")
        ic_results = self._run_ic_analysis(
            df_clean=df_clean,
            factor_names=factor_names or list(self.comparator.FACTOR_MAP.keys())
        )

        # 3. 暴露分析（针对最佳因子）
        logger.info("\n[3/5] 运行暴露分析...")
        best_factor_name = base_results['best_factor']
        exposure_results = self._run_exposure_analysis(
            df_clean=df_clean,
            factor_name=best_factor_name
        )

        # 4. 归因分析（针对最佳因子）
        logger.info("\n[4/5] 运行归因分析...")
        attribution_results = self._run_attribution_analysis(
            df_clean=df_clean,
            factor_name=best_factor_name
        )

        # 5. 生成增强版报告
        logger.info("\n[5/5] 生成增强版报告...")
        enhanced_report = self._create_enhanced_report(
            base_results=base_results,
            ic_results=ic_results,
            exposure_results=exposure_results,
            attribution_results=attribution_results,
            best_factor_name=best_factor_name
        )

        # 6. 保存所有结果
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)

            # 保存增强版报告
            report_file = output_path / 'ENHANCED_EVALUATION_REPORT.md'
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(enhanced_report)
            logger.info(f"增强版报告已保存: {report_file}")

            # 保存基础结果（对比表、稳健性测试）
            base_results['comparison'].to_csv(
                output_path / 'multi_factor_comparison.csv',
                index=False
            )
            self._save_robustness_results(base_results['robustness'], output_path)

            # 保存深度分析结果
            self._save_ic_results(ic_results, output_path)
            self._save_exposure_results(exposure_results, output_path)
            self._save_attribution_results(attribution_results, output_path)

        logger.info("="*80)
        logger.info("增强版综合评估报告生成完成")
        logger.info("="*80)

        return {
            **base_results,
            'ic_analysis': ic_results,
            'exposure': exposure_results,
            'attribution': attribution_results,
            'enhanced_report': enhanced_report
        }

    def _run_ic_analysis(
        self,
        df_clean: dict,
        factor_names: List[str]
    ) -> Dict:
        """运行IC/IR分析"""
        ic_results = {}

        for factor_name in factor_names:
            if factor_name == 'Composite':
                continue  # 跳过合成因子

            logger.info(f"  分析 {factor_name} 的IC/IR...")

            try:
                # 计算因子
                df_factor = self._calculate_factor(factor_name, df_clean)

                # IC分析
                # factor_t 预测 return_t+1 (lag=1), 不能用同期收益算IC
                ic_result = self.ic_analyzer.analyze_with_lag(
                    df_factor=df_factor,
                    df_return=df_clean['monthly_return'],
                    lag=1
                )

                ic_results[factor_name] = ic_result

            except Exception as e:
                logger.error(f"  {factor_name} IC分析失败: {e}")
                ic_results[factor_name] = None

        return ic_results

    def _run_exposure_analysis(
        self,
        df_clean: dict,
        factor_name: str
    ) -> Dict:
        """运行暴露分析"""
        # 计算因子
        df_factor = self._calculate_factor(factor_name, df_clean)

        # 构建组合
        builder = PortfolioBuilder(
            entry_quantile=self.entry_quantile,
            exit_quantile=self.exit_quantile,
            min_holding_periods=self.min_holding_periods,
            long_top=True
        )
        df_weights = builder.build(df_factor, neutralize=True)

        # 暴露检查
        neutrality = self.exposure_checker.check_weight_neutrality(df_weights)
        balance = self.exposure_checker.check_long_short_balance(df_weights)

        return {
            'neutrality': neutrality,
            'balance': balance
        }

    def _run_attribution_analysis(
        self,
        df_clean: dict,
        factor_name: str
    ) -> Dict:
        """运行归因分析"""
        # 计算因子
        df_factor = self._calculate_factor(factor_name, df_clean)

        # 构建组合
        builder = PortfolioBuilder(
            entry_quantile=self.entry_quantile,
            exit_quantile=self.exit_quantile,
            min_holding_periods=self.min_holding_periods,
            long_top=True
        )
        df_weights = builder.build(df_factor, neutralize=True)

        # 归因分析
        attribution = self.attribution_analyzer.analyze(
            df_weights=df_weights,
            df_stock_return=df_clean['monthly_return']
        )

        return attribution

    def _save_ic_results(self, ic_results: Dict, output_path: Path):
        """保存IC分析结果"""
        # IC汇总表
        ic_summary = []
        for factor_name, result in ic_results.items():
            if result is None:
                continue
            ic_summary.append({
                'factor': factor_name,
                'ic_mean': result['ic_mean'],
                'ic_median': result['ic_median'],
                'ic_std': result['ic_std'],
                'ir': result['ir'],
                'ic_positive_ratio': result['ic_positive_ratio'],
                't_statistic': result['t_statistic'],
                'n_periods': result['n_periods']
            })

        df_ic_summary = pd.DataFrame(ic_summary)
        df_ic_summary.to_csv(output_path / 'ic_summary.csv', index=False)

        # 每个因子的IC序列
        for factor_name, result in ic_results.items():
            if result is None:
                continue
            result['ic_series'].to_csv(
                output_path / f'ic_series_{factor_name.lower()}.csv'
            )

        logger.info(f"IC分析结果已保存至: {output_path}")

    def _save_exposure_results(self, exposure_results: Dict, output_path: Path):
        """保存暴露分析结果"""
        exposure_data = {
            'neutrality': exposure_results['neutrality'],
            'balance': exposure_results['balance']
        }

        # 转换为DataFrame格式
        neutrality_df = pd.DataFrame([exposure_results['neutrality']])
        balance_df = pd.DataFrame([exposure_results['balance']])

        neutrality_df.to_csv(output_path / 'exposure_neutrality.csv', index=False)
        balance_df.to_csv(output_path / 'exposure_balance.csv', index=False)

        logger.info(f"暴露分析结果已保存至: {output_path}")

    def _save_attribution_results(self, attribution_results: Dict, output_path: Path):
        """保存归因分析结果"""
        # 多空分解
        ls_decomp = pd.DataFrame([attribution_results['long_short_decomposition']])
        ls_decomp.to_csv(output_path / 'attribution_long_short.csv', index=False)

        # 选股收益
        selection = pd.DataFrame([attribution_results['stock_selection']])
        selection.to_csv(output_path / 'attribution_selection.csv', index=False)

        # Top贡献者
        top_contrib_data = []
        for ticker, contrib in attribution_results['top_contributors']['top_contributors'].items():
            top_contrib_data.append({'ticker': ticker, 'contribution': contrib, 'type': 'top'})
        for ticker, contrib in attribution_results['top_contributors']['bottom_contributors'].items():
            top_contrib_data.append({'ticker': ticker, 'contribution': contrib, 'type': 'bottom'})

        df_top_contrib = pd.DataFrame(top_contrib_data)
        df_top_contrib.to_csv(output_path / 'attribution_top_contributors.csv', index=False)

        logger.info(f"归因分析结果已保存至: {output_path}")

    def _create_enhanced_report(
        self,
        base_results: Dict,
        ic_results: Dict,
        exposure_results: Dict,
        attribution_results: Dict,
        best_factor_name: str
    ) -> str:
        """创建增强版报告"""

        # 获取基础报告
        base_report = base_results['report']

        # 在基础报告中插入深度分析部分
        # 找到"第二部分"的位置，在其之前插入深度分析
        insert_position = base_report.find("## 🔍 第二部分: 稳健性测试")

        if insert_position == -1:
            # 如果找不到，直接追加
            enhanced_report = base_report + self._create_deep_analysis_section(
                ic_results, exposure_results, attribution_results, best_factor_name
            )
        else:
            # 插入深度分析
            enhanced_report = (
                base_report[:insert_position] +
                self._create_deep_analysis_section(
                    ic_results, exposure_results, attribution_results, best_factor_name
                ) +
                "\n\n" +
                base_report[insert_position:].replace(
                    "## 🔍 第二部分: 稳健性测试",
                    "## 🧪 第三部分: 稳健性测试"
                ).replace(
                    "## 💡 第三部分: 关键发现与建议",
                    "## 💡 第四部分: 关键发现与建议"
                ).replace(
                    "## 📈 第四部分: 后续工作",
                    "## 📈 第五部分: 后续工作"
                )
            )

        # 更新标题
        enhanced_report = enhanced_report.replace(
            "# 因子回测系统 - 综合评估报告",
            "# 因子回测系统 - 增强版综合评估报告"
        )

        # 移除"建议的下一步"中的已完成项
        enhanced_report = enhanced_report.replace(
            """2. **深入分析**
   - IC/IR分析
   - 因子暴露分析
   - 归因分析 (多头/空头收益拆解)
   - 行业/板块暴露分析

3. """,
            "2. "
        )

        return enhanced_report

    def _create_deep_analysis_section(
        self,
        ic_results: Dict,
        exposure_results: Dict,
        attribution_results: Dict,
        best_factor_name: str
    ) -> str:
        """创建深度分析部分"""

        section = """
---

## 🔬 第二部分: 深度分析

### 2.1 IC/IR分析（因子有效性）

**信息系数(IC)**衡量因子对未来收益的预测能力。IC均值>0.03为有效因子，IR>0.5为优秀因子。

| 因子 | IC均值 | IC中位数 | IC标准差 | IR | IC正占比 | t统计量 | 样本数 | 评价 |
|------|--------|----------|----------|-----|----------|---------|--------|------|
"""

        for factor_name, result in ic_results.items():
            if result is None:
                continue

            # 评价标准
            if result['ir'] > 0.5:
                rating = "🟢 优秀"
            elif result['ir'] > 0.3:
                rating = "🟡 良好"
            elif result['ir'] > 0.1:
                rating = "🟠 一般"
            else:
                rating = "🔴 较弱"

            section += (
                f"| {factor_name} | {result['ic_mean']:.4f} | "
                f"{result['ic_median']:.4f} | {result['ic_std']:.4f} | "
                f"{result['ir']:.4f} | {result['ic_positive_ratio']:.2%} | "
                f"{result['t_statistic']:.2f} | {result['n_periods']} | {rating} |\n"
            )

        section += f"""

**IC解读**:
- **IR (信息比率)**: IC均值/IC标准差，衡量因子预测的稳定性
- **IC正占比**: 正IC期数占比，>55%表示因子稳定
- **t统计量**: 绝对值>2表示IC显著不为0

"""

        # 最佳因子的IC详细分析
        if best_factor_name in ic_results and ic_results[best_factor_name]:
            best_ic = ic_results[best_factor_name]
            section += f"""
**{best_factor_name}因子IC特征**:
- IC均值: {best_ic['ic_mean']:.4f} ({'正相关' if best_ic['ic_mean'] > 0 else '负相关'})
- IR: {best_ic['ir']:.4f} ({'优秀' if best_ic['ir'] > 0.5 else '良好' if best_ic['ir'] > 0.3 else '一般' if best_ic['ir'] > 0.1 else '较弱'})
- IC稳定性: {best_ic['ic_positive_ratio']:.2%} ({'稳定' if best_ic['ic_positive_ratio'] > 0.55 else '不稳定'})
- 统计显著性: t={best_ic['t_statistic']:.2f} ({'显著' if abs(best_ic['t_statistic']) > 2 else '不显著'})

"""

        section += f"""
---

### 2.2 暴露分析（市场中性化检验）

**权重中性化检验** (基于{best_factor_name}因子):

| 指标 | 数值 | 判定 |
|------|------|------|
| 权重和均值 | {exposure_results['neutrality']['weight_sum_mean']:.6f} | {'✅ 通过' if abs(exposure_results['neutrality']['weight_sum_mean']) < 0.01 else '❌ 未通过'} |
| 权重和标准差 | {exposure_results['neutrality']['weight_sum_std']:.6f} | |
| 权重和最大值 | {exposure_results['neutrality']['weight_sum_max']:.6f} | |
| 权重和最小值 | {exposure_results['neutrality']['weight_sum_min']:.6f} | |
| 是否市场中性 | {'是' if exposure_results['neutrality']['is_market_neutral'] else '否'} | {'✅ 通过' if exposure_results['neutrality']['is_market_neutral'] else '❌ 未通过'} |
| 中性化得分 | {exposure_results['neutrality']['neutrality_score']:.4f} | |

**多空平衡检验**:

| 指标 | 数值 | 判定 |
|------|------|------|
| 平均多头数量 | {exposure_results['balance']['avg_n_long']:.1f} | |
| 平均空头数量 | {exposure_results['balance']['avg_n_short']:.1f} | |
| 平均多头权重 | {exposure_results['balance']['avg_long_weight']:.4f} | |
| 平均空头权重 | {exposure_results['balance']['avg_short_weight']:.4f} | |
| 多空权重比 | {exposure_results['balance']['long_short_ratio']:.4f} | {'✅ 平衡' if 0.95 < exposure_results['balance']['long_short_ratio'] < 1.05 else '⚠️  不平衡'} |
| 是否平衡 | {'是' if exposure_results['balance']['is_balanced'] else '否'} | {'✅ 通过' if exposure_results['balance']['is_balanced'] else '❌ 未通过'} |

**解读**:
- **权重和≈0**: 表示组合对市场整体走势无暴露（市场中性）
- **多空权重比≈1**: 表示多头和空头资金配置均衡
- **中性化得分**: 越接近0越好，<0.01表示中性化效果优秀

"""

        section += f"""
---

### 2.3 归因分析（收益来源拆解）

**多空收益分解** (基于{best_factor_name}因子):

| 指标 | 多头 | 空头 | 解读 |
|------|------|------|------|
| 月均收益 | {attribution_results['long_short_decomposition']['long_contrib_mean']:.4%} | {attribution_results['long_short_decomposition']['short_contrib_mean']:.4%} | {'多头主导' if abs(attribution_results['long_short_decomposition']['long_contrib_mean']) > abs(attribution_results['long_short_decomposition']['short_contrib_mean']) else '空头主导'} |
| 收益标准差 | {attribution_results['long_short_decomposition']['long_contrib_std']:.4%} | {attribution_results['long_short_decomposition']['short_contrib_std']:.4%} | {'多头波动大' if attribution_results['long_short_decomposition']['long_contrib_std'] > attribution_results['long_short_decomposition']['short_contrib_std'] else '空头波动大'} |
| Sharpe比率 | {attribution_results['long_short_decomposition']['long_sharpe']:.4f} | {attribution_results['long_short_decomposition']['short_sharpe']:.4f} | {'多头效率高' if attribution_results['long_short_decomposition']['long_sharpe'] > attribution_results['long_short_decomposition']['short_sharpe'] else '空头效率高'} |
| 贡献占比 | {attribution_results['long_short_decomposition']['long_pct']:.2%} | {attribution_results['long_short_decomposition']['short_pct']:.2%} | 100% |

**选股收益分析**:

| 指标 | 数值 |
|------|------|
| 实际月均收益 | {attribution_results['stock_selection']['actual_return']:.4%} |
| 基准月均收益 | {attribution_results['stock_selection']['benchmark_return']:.4%} |
| 选股月均收益 | {attribution_results['stock_selection']['selection_return_mean']:.4%} |
| 选股Sharpe | {attribution_results['stock_selection']['selection_sharpe']:.4f} |
| 选股贡献占比 | {attribution_results['stock_selection']['selection_contribution']:.2%} |

**Top 10 收益贡献股票**:

"""

        # Top贡献者
        for ticker, contrib in list(attribution_results['top_contributors']['top_contributors'].items())[:10]:
            section += f"- **{ticker}**: {contrib:.2%}\n"

        section += "\n**Bottom 10 收益拖累股票**:\n\n"

        for ticker, contrib in list(attribution_results['top_contributors']['bottom_contributors'].items())[:10]:
            section += f"- **{ticker}**: {contrib:.2%}\n"

        section += f"""

**归因总结**:
- 主要收益来源: {'多头选股' if attribution_results['long_short_decomposition']['long_pct'] > 0.6 else '空头选股' if attribution_results['long_short_decomposition']['short_pct'] > 0.6 else '多空均衡'}
- 选股能力评价: {'优秀' if attribution_results['stock_selection']['selection_sharpe'] > 0.5 else '良好' if attribution_results['stock_selection']['selection_sharpe'] > 0.3 else '一般'}
- 集中度风险: {'需关注' if len(attribution_results['top_contributors']['top_contributors']) < 20 else '分散良好'}

"""

        return section


if __name__ == '__main__':
    """测试增强版报告生成器"""
    from data import load_clean_data

    # 加载数据
    print("加载数据...")
    df_clean = load_clean_data()

    # 生成增强版报告
    generator = EnhancedReportGenerator(
        rebalance_freq='2monthly',
        min_holding_periods=12,
        entry_quantile=0.25,
        exit_quantile=0.30,
        cost_bps=20.0
    )

    results = generator.generate_enhanced_report(
        df_clean=df_clean,
        factor_names=None,
        split_date='2020-01-01',
        output_dir='results'
    )

    print("\n增强版报告已生成!")
    print(f"最佳因子: {results['best_factor']}")
