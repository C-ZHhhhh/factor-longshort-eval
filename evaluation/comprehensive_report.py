"""
综合评估报告生成器

[INPUT]:
- 清洗后的数据 (dict)
- 可选的因子列表

[OUTPUT]:
- 综合评估报告 (Markdown)
- 包含多因子对比 + 稳健性测试 + 关键发现

[POS]:
评估层核心模块，生成完整的因子评估报告

[PROTOCOL]:
1. 整合多因子对比和稳健性测试
2. 自动生成综合报告
3. 包含可视化建议和实盘建议
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

from evaluation.multi_factor_comparison import MultiFactorComparator
from evaluation.robustness import RobustnessTest
from factors.momentum import MomentumFactor
from factors.factor_processor import FactorProcessor
from utils.logger import get_logger

logger = get_logger(__name__)


class ComprehensiveReportGenerator:
    """
    综合评估报告生成器

    整合多因子对比和稳健性测试，生成完整评估报告
    """

    def __init__(
        self,
        rebalance_freq: str = '2monthly',
        min_holding_periods: int = 12,
        entry_quantile: float = 0.25,
        exit_quantile: float = 0.30,
        cost_bps: float = 20.0
    ):
        """
        初始化综合报告生成器

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
        """
        self.rebalance_freq = rebalance_freq
        self.min_holding_periods = min_holding_periods
        self.entry_quantile = entry_quantile
        self.exit_quantile = exit_quantile
        self.cost_bps = cost_bps

        # 初始化子模块
        self.comparator = MultiFactorComparator(
            rebalance_freq=rebalance_freq,
            min_holding_periods=min_holding_periods,
            entry_quantile=entry_quantile,
            exit_quantile=exit_quantile,
            cost_bps=cost_bps
        )

        self.robustness_tester = RobustnessTest()

        logger.info(
            f"初始化综合报告生成器: "
            f"调仓={rebalance_freq}, 持有期={min_holding_periods}月, "
            f"阈值={entry_quantile}/{exit_quantile}, 成本={cost_bps}bps"
        )

    def generate_comprehensive_report(
        self,
        df_clean: dict,
        factor_names: Optional[List[str]] = None,
        split_date: str = '2020-01-01',
        output_dir: Optional[str] = None
    ) -> Dict:
        """
        生成综合评估报告

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
        logger.info("开始生成综合评估报告")
        logger.info("="*80)

        # 1. 多因子对比
        logger.info("\n[1/3] 运行多因子对比...")
        df_comparison = self.comparator.compare(
            df_clean=df_clean,
            factor_names=factor_names,
            include_composite=True
        )

        # 2. 稳健性测试 (使用最佳因子)
        best_factor_name = df_comparison.iloc[0]['factor']
        logger.info(f"\n[2/3] 对最佳因子 {best_factor_name} 进行稳健性测试...")

        # 计算最佳因子
        if best_factor_name == 'Composite':
            # 如果最佳是合成因子，暂时跳过稳健性测试
            logger.warning("最佳因子是合成因子，稳健性测试使用Momentum因子")
            best_factor_name = 'Momentum'

        df_best_factor = self._calculate_factor(best_factor_name, df_clean)

        # 运行稳健性测试
        robustness_results = self.robustness_tester.analyze_robustness(
            df_factor=df_best_factor,
            df_return=df_clean['monthly_return'],
            split_date=split_date
        )

        # 3. 生成综合报告
        logger.info("\n[3/3] 生成综合报告...")
        report = self._create_comprehensive_report(
            df_comparison=df_comparison,
            robustness_results=robustness_results,
            best_factor_name=best_factor_name,
            split_date=split_date
        )

        # 4. 保存报告和数据
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)

            # 保存报告
            report_file = output_path / 'COMPREHENSIVE_EVALUATION_REPORT.md'
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"综合报告已保存: {report_file}")

            # 保存多因子对比表
            comparison_file = output_path / 'multi_factor_comparison.csv'
            df_comparison.to_csv(comparison_file, index=False)
            logger.info(f"对比表已保存: {comparison_file}")

            # 保存稳健性测试结果
            self._save_robustness_results(robustness_results, output_path)

        logger.info("="*80)
        logger.info("综合评估报告生成完成")
        logger.info("="*80)

        return {
            'comparison': df_comparison,
            'robustness': robustness_results,
            'report': report,
            'best_factor': best_factor_name
        }

    def _calculate_factor(self, factor_name: str, df_clean: dict) -> pd.DataFrame:
        """计算因子并标准化"""
        factor_class = self.comparator.FACTOR_MAP.get(factor_name)
        if not factor_class:
            raise ValueError(f"未知因子: {factor_name}")

        factor = factor_class()

        # 根据因子类型传入不同参数
        if factor_name == 'Liquidity':
            if 'volume' not in df_clean or df_clean['volume'] is None:
                raise ValueError("Liquidity因子需要volume数据")
            df_factor = factor.calculate(
                df_price=df_clean['price'],
                df_volume=df_clean['volume']
            )
        else:
            df_factor = factor.calculate(
                df_price=df_clean['price'],
                df_return_daily=df_clean.get('daily_return')
            )

        # 标准化
        processor = FactorProcessor()
        df_factor = processor.winsorize(df_factor)
        df_factor = processor.zscore_standardize(df_factor)

        return df_factor

    def _save_robustness_results(self, results: Dict, output_path: Path):
        """保存稳健性测试结果"""
        # 子样本测试
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
        df_sub_sample.to_csv(output_path / 'robustness_sub_sample.csv', index=False)

        # 成本敏感性
        results['cost_sensitivity'].to_csv(
            output_path / 'robustness_cost_sensitivity.csv',
            index=False
        )

        # 分位数敏感性
        results['quantile_sensitivity'].to_csv(
            output_path / 'robustness_quantile_sensitivity.csv',
            index=False
        )

        logger.info(f"稳健性测试结果已保存至: {output_path}")

    def _create_comprehensive_report(
        self,
        df_comparison: pd.DataFrame,
        robustness_results: Dict,
        best_factor_name: str,
        split_date: str
    ) -> str:
        """创建综合报告"""

        # 提取关键数据
        best_factor = df_comparison.iloc[0]

        # 子样本数据
        sub_sample_data = []
        for period_name, result in robustness_results['sub_sample'].items():
            metrics = result['metrics']
            sub_sample_data.append({
                'period': period_name,
                'annual_return': metrics['annual_return'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown']
            })
        df_sub_sample = pd.DataFrame(sub_sample_data)

        # 成本敏感性数据
        df_cost = robustness_results['cost_sensitivity']

        report = f"""# 因子回测系统 - 综合评估报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

**回测配置**:
- 调仓频率: {self.rebalance_freq}
- 最小持有期: {self.min_holding_periods}月
- 进出阈值: {self.entry_quantile:.0%} / {self.exit_quantile:.0%}
- 交易成本: {self.cost_bps:.0f} bps
- 权重方式: Market-neutral (多头=+1, 空头=-1)

---

## 📊 第一部分: 多因子对比

### 完整对比表 (按Sharpe排序)

| 因子 | 年化收益 | Sharpe | 最大回撤 | 波动率 | Calmar | 胜率 | 换手率 |
|------|----------|--------|----------|--------|--------|------|--------|
"""

        for _, row in df_comparison.iterrows():
            report += (
                f"| {row['factor']} | {row['annual_return']:.2%} | "
                f"{row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} | "
                f"{row['annual_volatility']:.2%} | {row['calmar_ratio']:.4f} | "
                f"{row['win_rate']:.2%} | {row['avg_turnover']:.2%} |\n"
            )

        report += f"""

### 🏆 最佳因子: {best_factor['factor']}

- **年化收益**: {best_factor['annual_return']:.2%}
- **Sharpe比率**: {best_factor['sharpe_ratio']:.4f}
- **最大回撤**: {best_factor['max_drawdown']:.2%}
- **年化波动**: {best_factor['annual_volatility']:.2%}
- **Calmar比率**: {best_factor['calmar_ratio']:.4f}
- **胜率**: {best_factor['win_rate']:.2%}
- **平均换手率**: {best_factor['avg_turnover']:.2%}
- **调仓次数**: {int(best_factor['rebalance_count'])}
- **总成本**: {best_factor['total_cost']:.2%}

### 成本影响分析

"""

        for _, row in df_comparison.iterrows():
            cost_impact = row['annual_return_no_cost'] - row['annual_return']
            report += f"- **{row['factor']}**: 成本拖累 {cost_impact:.2%} (无成本: {row['annual_return_no_cost']:.2%}, 含成本: {row['annual_return']:.2%})\n"

        report += f"""

平均成本拖累: **{df_comparison['total_cost'].mean():.2%}**

### 合成因子表现
"""

        if 'Composite' in df_comparison['factor'].values:
            composite_row = df_comparison[df_comparison['factor'] == 'Composite'].iloc[0]
            composite_rank = df_comparison.index[df_comparison['factor'] == 'Composite'].tolist()[0] + 1
            report += f"""
合成因子排名: **{composite_rank}/{len(df_comparison)}**

- 年化收益: {composite_row['annual_return']:.2%}
- Sharpe比率: {composite_row['sharpe_ratio']:.4f}
- 最大回撤: {composite_row['max_drawdown']:.2%}
- 平均换手率: {composite_row['avg_turnover']:.2%}
"""
        else:
            report += "\n未包含合成因子\n"

        report += f"""

---

## 🔍 第二部分: 稳健性测试 (基于{best_factor_name}因子)

### 子样本测试 (分割日期: {split_date})

| 时间段 | 年化收益 | Sharpe | 最大回撤 |
|--------|----------|--------|----------|
"""

        for _, row in df_sub_sample.iterrows():
            report += f"| {row['period']} | {row['annual_return']:.2%} | {row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} |\n"

        # 计算稳健性指标
        if len(df_sub_sample) >= 2:
            sharpe_diff = abs(df_sub_sample.iloc[0]['sharpe_ratio'] - df_sub_sample.iloc[1]['sharpe_ratio'])
            return_diff = abs(df_sub_sample.iloc[0]['annual_return'] - df_sub_sample.iloc[1]['annual_return'])

            report += f"""

**稳健性分析**:
- Sharpe差异: {sharpe_diff:.4f}
- 收益差异: {return_diff:.2%}
- 稳健性评价: {'✅ 较稳健' if sharpe_diff < 0.3 and return_diff < 0.05 else '⚠️ 波动较大'}
"""

        report += """

### 成本敏感性测试

| 成本(bps) | 年化收益 | Sharpe | 最大回撤 | 变化 |
|-----------|----------|--------|----------|------|
"""

        base_return = df_cost.iloc[0]['annual_return']
        for idx, row in df_cost.iterrows():
            change = row['annual_return'] - base_return if idx > 0 else 0
            change_str = f"{change:+.2%}" if idx > 0 else "基准"
            report += (
                f"| {row['cost_bps']:.0f} | {row['annual_return']:.2%} | "
                f"{row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} | {change_str} |\n"
            )

        # 计算成本敏感性
        if len(df_cost) >= 2:
            cost_sensitivity = (df_cost.iloc[-1]['annual_return'] - df_cost.iloc[0]['annual_return']) / (df_cost.iloc[-1]['cost_bps'] - df_cost.iloc[0]['cost_bps'])

            report += f"""

**成本影响**:
- 每增加10bps成本，年化收益下降约 **{abs(cost_sensitivity * 10):.2%}**
- 成本敏感性: {'🔴 高' if abs(cost_sensitivity) > 0.015 else '🟡 中' if abs(cost_sensitivity) > 0.008 else '🟢 低'}
- 结论: {'必须严格控制交易成本' if abs(cost_sensitivity) > 0.015 else '成本影响可控'}
"""

        report += """

---

## 💡 第三部分: 关键发现与建议

### 关键发现

"""

        # 动态生成关键发现
        findings = []

        # 1. 最佳因子
        findings.append(f"1. **{best_factor['factor']}因子表现最佳**，年化收益{best_factor['annual_return']:.2%}，Sharpe {best_factor['sharpe_ratio']:.4f}")

        # 2. 合成因子表现
        if 'Composite' in df_comparison['factor'].values:
            composite_row = df_comparison[df_comparison['factor'] == 'Composite'].iloc[0]
            if composite_row['sharpe_ratio'] < best_factor['sharpe_ratio']:
                findings.append(f"2. **合成因子未能提升表现**，可能因为纳入了表现较差的因子，建议只合成表现较好的因子")
            else:
                findings.append(f"2. **合成因子表现优异**，成功通过分散化提升了风险调整后收益")

        # 3. 成本影响
        avg_cost = df_comparison['total_cost'].mean()
        if avg_cost > 0.05:
            findings.append(f"3. **交易成本影响显著**，平均累计成本{avg_cost:.2%}，降低换手率是关键优化方向")

        # 4. 稳健性
        if len(df_sub_sample) >= 2:
            if sharpe_diff < 0.3:
                findings.append(f"4. **策略具有较好的稳健性**，子样本Sharpe差异仅{sharpe_diff:.4f}")
            else:
                findings.append(f"4. **策略稳健性有待提升**，子样本表现差异较大({sharpe_diff:.4f})")

        for finding in findings:
            report += f"{finding}\n\n"

        report += f"""

### 🎯 实盘建议

#### 推荐策略

**{best_factor['factor']}因子策略 (Market-neutral)**

配置参数:
- 因子: {best_factor['factor']}
- 调仓频率: {self.rebalance_freq}
- 最小持有期: {self.min_holding_periods}月
- 进出阈值: {self.entry_quantile:.0%} / {self.exit_quantile:.0%}
- 权重方式: Market-neutral (多头=+1, 空头=-1)
- 预期成本: {self.cost_bps:.0f} bps

预期表现:
- 年化收益: ~{best_factor['annual_return']:.2%}
- Sharpe比率: ~{best_factor['sharpe_ratio']:.2f}
- 最大回撤: ~{best_factor['max_drawdown']:.1%}
- 平均换手率: ~{best_factor['avg_turnover']:.1%}

#### 优化方向

"""

        # 动态生成优化建议
        suggestions = []

        # 1. 降低成本
        if abs(cost_sensitivity) > 0.015:
            suggestions.append("""1. **降低交易成本** (成本敏感性高)
   - 考虑降低调仓频率 (如改为季度调仓)
   - 增加最小持有期到18月
   - 扩大进出阈值差距""")

        # 2. 改进合成
        if 'Composite' in df_comparison['factor'].values:
            composite_row = df_comparison[df_comparison['factor'] == 'Composite'].iloc[0]
            if composite_row['sharpe_ratio'] < best_factor['sharpe_ratio']:
                suggestions.append("""2. **优化因子合成方法**
   - 仅合成Sharpe>0的因子
   - 使用Sharpe加权而非等权
   - 动态调整因子权重""")

        # 3. 换手率优化
        if best_factor['avg_turnover'] > 0.3:
            suggestions.append("""3. **降低换手率**
   - 增加最小持有期限制
   - 扩大进出阈值差
   - 考虑添加交易摩擦约束""")

        # 4. 因子探索
        suggestions.append("""4. **探索其他因子**
   - 当前测试缺Liquidity因子 (需成交量数据)
   - 可尝试价值、质量等基本面因子
   - 考虑机器学习预测因子""")

        for idx, suggestion in enumerate(suggestions, 1):
            if idx <= len(suggestions):
                report += f"{suggestion}\n\n"

        report += """

---

## 📈 第四部分: 后续工作

### 建议的下一步

1. **添加可视化**
   - 净值曲线对比图
   - IC时间序列图
   - 回撤曲线图
   - 因子相关性热图

2. **深入分析**
   - IC/IR分析
   - 因子暴露分析
   - 归因分析 (多头/空头收益拆解)
   - 行业/板块暴露分析

3. **策略优化**
   - 参数网格搜索
   - 动态权重分配
   - 风险预算优化
   - 组合优化 (最大化Sharpe)

4. **实盘准备**
   - 实时数据接口
   - 自动化交易执行
   - 风险监控系统
   - 绩效归因系统

---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**系统版本**: v1.0 (重构后)
**数据来源**: yfinance + Alpaca (交叉验证)
**样本池**: S&P 500

---

*本报告由因子回测系统自动生成 | 评估层已完全重构为自包含模块*
"""

        return report
