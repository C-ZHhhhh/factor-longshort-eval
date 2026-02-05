"""
性能表格生成器

生成统一的性能评估表格，包含：
- performance_table.csv + Markdown
- 毛收益 vs 净收益对比
- 所有因子的完整指标

[INPUT]:
- 回测结果字典 {factor_name: backtest_result}

[OUTPUT]:
- results/performance_table.csv
- results/performance_table.md
- results/drawdown_stats.csv

[POS]:
评估层统一入口，生成标准化性能表格

[PROTOCOL]:
1. 对每个因子分别计算：annual_return_gross, annual_return_net,
   annual_vol, sharpe, max_drawdown, avg_turnover, cost_drag_annual
2. 添加 sanity check 确保数据一致性
3. 输出 CSV + Markdown 格式
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceTableGenerator:
    """
    性能表格生成器

    生成标准化的性能评估表格
    """

    def __init__(self):
        """初始化生成器"""
        pass

    def generate_performance_table(
        self,
        backtest_results: Dict[str, Dict],
        output_dir: str = 'results'
    ) -> pd.DataFrame:
        """
        生成性能表格

        Parameters:
        -----------
        backtest_results : dict
            {factor_name: backtest_result} 字典
            每个 backtest_result 必须包含:
            - nav: 含成本净值
            - nav_no_cost: 无成本净值
            - returns: 含成本收益率
            - returns_no_cost: 无成本收益率
            - turnover: 换手率序列
            - metrics: 含成本指标字典
            - metrics_no_cost: 无成本指标字典
        output_dir : str
            输出目录

        Returns:
        --------
        df_performance : DataFrame
            性能表格
        """
        logger.info("="*80)
        logger.info("开始生成性能表格")
        logger.info("="*80)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 收集所有因子的性能指标
        logger.info("\n[1/4] 收集性能指标...")
        performance_data = []

        for factor_name, result in backtest_results.items():
            logger.info(f"  处理 {factor_name}...")

            # 提取指标
            metrics = result['metrics']
            metrics_no_cost = result['metrics_no_cost']

            # 计算平均换手率
            turnover_series = result['turnover']
            avg_turnover = turnover_series.mean()

            # 计算成本拖累
            annual_return_gross = metrics_no_cost['annual_return']
            annual_return_net = metrics['annual_return']
            cost_drag_annual = annual_return_net - annual_return_gross

            # Sanity Check: 验证指标一致性
            self._sanity_check_metrics(
                factor_name=factor_name,
                nav=result['nav'],
                nav_no_cost=result['nav_no_cost'],
                metrics=metrics,
                metrics_no_cost=metrics_no_cost
            )

            performance_data.append({
                'factor': factor_name,
                'annual_return_gross': annual_return_gross,
                'annual_return_net': annual_return_net,
                'annual_vol': metrics['annual_volatility'],
                'sharpe': metrics['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown'],
                'avg_turnover': avg_turnover,
                'cost_drag_annual': cost_drag_annual,
                # 额外指标
                'calmar_ratio': metrics['calmar_ratio'],
                'win_rate': metrics['win_rate'],
                'sharpe_no_cost': metrics_no_cost['sharpe_ratio']
            })

        df_performance = pd.DataFrame(performance_data)

        # 按 Sharpe 排序
        df_performance = df_performance.sort_values('sharpe', ascending=False)
        df_performance = df_performance.reset_index(drop=True)

        # 2. 生成 drawdown 统计表
        logger.info("\n[2/4] 生成 Drawdown 统计...")
        df_dd_stats = self._generate_drawdown_stats(backtest_results)

        # 3. 保存 CSV
        logger.info("\n[3/4] 保存 CSV...")
        csv_file = output_path / 'performance_table.csv'
        df_performance.to_csv(csv_file, index=False, float_format='%.6f')
        logger.info(f"✅ 性能表格已保存: {csv_file}")

        dd_csv_file = output_path / 'drawdown_stats.csv'
        df_dd_stats.to_csv(dd_csv_file, index=False, float_format='%.6f')
        logger.info(f"✅ Drawdown 统计已保存: {dd_csv_file}")

        # 4. 生成 Markdown
        logger.info("\n[4/4] 生成 Markdown...")
        md_content = self._create_markdown_table(df_performance, df_dd_stats)
        md_file = output_path / 'performance_table.md'
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logger.info(f"✅ Markdown 表格已保存: {md_file}")

        logger.info("\n" + "="*80)
        logger.info("✅ 性能表格生成完成")
        logger.info("="*80)

        return df_performance

    def _sanity_check_metrics(
        self,
        factor_name: str,
        nav: pd.Series,
        nav_no_cost: pd.Series,
        metrics: Dict,
        metrics_no_cost: Dict
    ):
        """
        Sanity Check: 验证指标与 NAV 数据的一致性
        """
        # 1. 验证 max_drawdown
        recalc_dd = self._calculate_max_drawdown(nav)
        recalc_dd_no_cost = self._calculate_max_drawdown(nav_no_cost)

        dd_diff = abs(metrics['max_drawdown'] - recalc_dd)
        dd_no_cost_diff = abs(metrics_no_cost['max_drawdown'] - recalc_dd_no_cost)

        if dd_diff > 1e-6:
            logger.warning(
                f"⚠️  {factor_name}: max_drawdown 不一致! "
                f"metrics={metrics['max_drawdown']:.6f}, "
                f"recalc={recalc_dd:.6f}, diff={dd_diff:.6e}"
            )

        if dd_no_cost_diff > 1e-6:
            logger.warning(
                f"⚠️  {factor_name} (no_cost): max_drawdown 不一致! "
                f"metrics={metrics_no_cost['max_drawdown']:.6f}, "
                f"recalc={recalc_dd_no_cost:.6f}, diff={dd_no_cost_diff:.6e}"
            )

        # 2. 验证年化收益
        recalc_annual_return = self._calculate_annual_return(nav)
        ar_diff = abs(metrics['annual_return'] - recalc_annual_return)

        if ar_diff > 1e-6:
            logger.warning(
                f"⚠️  {factor_name}: annual_return 不一致! "
                f"metrics={metrics['annual_return']:.6f}, "
                f"recalc={recalc_annual_return:.6f}, diff={ar_diff:.6e}"
            )

    def _calculate_max_drawdown(self, nav: pd.Series) -> float:
        """计算最大回撤"""
        cummax = nav.cummax()
        drawdown = (nav - cummax) / cummax
        return drawdown.min()

    def _calculate_annual_return(self, nav: pd.Series) -> float:
        """计算年化收益"""
        if len(nav) < 2:
            return 0.0

        total_return = nav.iloc[-1] / nav.iloc[0] - 1
        n_years = len(nav) / 12  # 假设月度数据

        if n_years <= 0:
            return 0.0

        annual_return = (1 + total_return) ** (1 / n_years) - 1
        return annual_return

    def _generate_drawdown_stats(
        self,
        backtest_results: Dict[str, Dict]
    ) -> pd.DataFrame:
        """
        生成 drawdown 统计表

        包含：
        - total_underwater_months: 总水下月数
        - max_drawdown_duration_months: 最大回撤持续时长
        - time_to_recovery_months: 恢复时间（若未恢复则为 NA）
        """
        dd_stats_data = []

        for factor_name, result in backtest_results.items():
            nav = result['nav']

            # 计算 drawdown 序列
            running_max = nav.cummax()
            drawdown = (nav - running_max) / running_max

            # 1. 总水下月数
            total_underwater_months = (drawdown < 0).sum()

            # 2. 找出所有回撤期
            underwater = drawdown < 0
            underwater_periods = []
            start = None

            for i in range(len(underwater)):
                if underwater.iloc[i] and start is None:
                    start = i
                elif not underwater.iloc[i] and start is not None:
                    underwater_periods.append((start, i - 1))
                    start = None

            if start is not None:
                underwater_periods.append((start, len(underwater) - 1))

            # 3. 最大回撤持续时长
            if underwater_periods:
                max_duration = max(end - start + 1 for start, end in underwater_periods)
            else:
                max_duration = 0

            # 4. 当前恢复时间（如果当前处于回撤中）
            if underwater.iloc[-1]:
                # 未恢复
                time_to_recovery = np.nan
                current_drawdown_duration = len(underwater) - underwater_periods[-1][0]
            else:
                # 已恢复
                if underwater_periods:
                    # 上一次回撤的恢复时间
                    last_period = underwater_periods[-1]
                    time_to_recovery = last_period[1] - last_period[0] + 1
                else:
                    time_to_recovery = 0

            dd_stats_data.append({
                'factor': factor_name,
                'total_underwater_months': total_underwater_months,
                'max_drawdown_duration_months': max_duration,
                'time_to_recovery_months': time_to_recovery,
                'max_drawdown': drawdown.min(),
                'currently_underwater': underwater.iloc[-1]
            })

        df_dd_stats = pd.DataFrame(dd_stats_data)
        return df_dd_stats

    def _create_markdown_table(
        self,
        df_performance: pd.DataFrame,
        df_dd_stats: pd.DataFrame
    ) -> str:
        """创建 Markdown 格式表格"""

        md = """# 因子回测性能表格

生成时间: {}

---

## 主要性能指标

| 因子 | 年化收益(毛) | 年化收益(净) | 年化波动 | Sharpe | 最大回撤 | 平均换手率 | 成本拖累 |
|------|-------------|-------------|---------|--------|----------|-----------|---------|
""".format(pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))

        for _, row in df_performance.iterrows():
            md += (
                f"| {row['factor']} "
                f"| {row['annual_return_gross']:.4f} "
                f"| {row['annual_return_net']:.4f} "
                f"| {row['annual_vol']:.4f} "
                f"| {row['sharpe']:.4f} "
                f"| {row['max_drawdown']:.4f} "
                f"| {row['avg_turnover']:.4f} "
                f"| {row['cost_drag_annual']:.4f} |\n"
            )

        md += """
---

## Drawdown 统计

| 因子 | 最大回撤 | 总水下月数 | 最大回撤持续(月) | 恢复时间(月) | 当前是否水下 |
|------|---------|-----------|----------------|-------------|-------------|
"""

        for _, row in df_dd_stats.iterrows():
            recovery_str = f"{row['time_to_recovery_months']:.0f}" if not np.isnan(row['time_to_recovery_months']) else "NA"
            underwater_str = "是" if row['currently_underwater'] else "否"

            md += (
                f"| {row['factor']} "
                f"| {row['max_drawdown']:.4f} "
                f"| {row['total_underwater_months']:.0f} "
                f"| {row['max_drawdown_duration_months']:.0f} "
                f"| {recovery_str} "
                f"| {underwater_str} |\n"
            )

        md += """
---

## 指标说明

### 主要指标
- **年化收益(毛)**: 不考虑交易成本的年化收益率
- **年化收益(净)**: 扣除交易成本后的年化收益率
- **年化波动**: 收益率的年化标准差
- **Sharpe**: Sharpe比率 = 年化收益 / 年化波动
- **最大回撤**: 从历史最高点到最低点的最大跌幅
- **平均换手率**: 每期调仓的平均换手率
- **成本拖累**: 净收益 - 毛收益 (负值表示成本影响)

### Drawdown 统计
- **总水下月数**: 净值低于历史最高点的月份总数
- **最大回撤持续(月)**: 最长连续回撤期的月数
- **恢复时间(月)**: 从回撤低点到恢复至历史最高的月数(若未恢复则为NA)
- **当前是否水下**: 当前净值是否低于历史最高点

---

*本报告由性能表格生成器自动生成*
"""

        return md


if __name__ == '__main__':
    """测试代码"""
    logger.info("性能表格生成器模块")
    logger.info("请使用 scripts/run_evaluation.py 运行评估")
