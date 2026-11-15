"""
生成交付图表

基于最新results数据生成6张关键图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from backtest.metrics import drawdown_series

logger = get_logger(__name__)

# 设置中文字体和样式
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

class FigureGenerator:
    """交付图表生成器"""

    def __init__(self, results_dir: str = 'results'):
        self.results_dir = Path(results_dir)
        self.figures_dir = self.results_dir / 'figures'
        self.figures_dir.mkdir(exist_ok=True)

        logger.info(f"图表将保存到: {self.figures_dir}")

    def generate_all(self):
        """生成所有6张图表"""

        logger.info("="*80)
        logger.info("开始生成交付图表")
        logger.info("="*80)

        # 1. Momentum gross vs net equity curve
        logger.info("\n[1/6] 生成 Momentum gross vs net equity curve...")
        self.fig_01_equity_gross_vs_net_momentum()

        # 2. Momentum net drawdown curve
        logger.info("[2/6] 生成 Momentum net drawdown curve...")
        self.fig_02_drawdown_momentum()

        # 3. Cost sensitivity
        logger.info("[3/6] 生成 cost sensitivity curve...")
        self.fig_03_cost_sensitivity_momentum()

        # 4. Subsample comparison
        logger.info("[4/6] 生成 subsample comparison bar...")
        self.fig_04_subsample_bar_momentum()

        # 5. Exposure alpha & beta
        logger.info("[5/6] 生成 exposure alpha & beta...")
        self.fig_05_exposure_alpha_beta()

        # 6. Significance t-stats
        logger.info("[6/6] 生成 significance t-stats...")
        self.fig_06_significance_tstats()

        logger.info("\n" + "="*80)
        logger.info("✅ 所有图表生成完成！")
        logger.info("="*80)

    def fig_01_equity_gross_vs_net_momentum(self):
        """图1: Momentum毛收益vs净收益曲线"""

        # 读取Momentum回测数据（从缓存或重新计算）
        # 这里我们从已有的数据重新读取
        from data.data_loader import DataLoader
        from factors.momentum import MomentumFactor
        from factors.factor_processor import FactorProcessor
        from portfolio.portfolio_builder import PortfolioBuilder
        from backtest.engine import BacktestEngine

        loader = DataLoader()
        df_clean = loader.load_cleaned_data()

        # 计算Momentum因子
        momentum = MomentumFactor()
        df_factor = momentum.calculate(
            df_price=df_clean['price'],
            df_return_daily=df_clean.get('daily_return')
        )

        processor = FactorProcessor()
        df_factor = processor.winsorize(df_factor)
        df_factor = processor.zscore_standardize(df_factor)

        # 构建组合
        builder = PortfolioBuilder(
            entry_quantile=0.25,
            exit_quantile=0.30,
            min_holding_periods=12,
            long_top=True
        )
        df_weights = builder.build(df_factor)

        # 回测
        engine = BacktestEngine(cost_bps=20.0, rebalance_freq='2monthly')
        result = engine.run(df_weights, df_clean['monthly_return'])

        # 绘图
        fig, ax = plt.subplots(figsize=(12, 6))

        nav_gross = result['nav_no_cost']
        nav_net = result['nav']

        ax.plot(nav_gross.index, nav_gross.values, label='Gross (Before Cost)',
                linewidth=2, color='#2E86AB', alpha=0.8)
        ax.plot(nav_net.index, nav_net.values, label='Net (After 20bps Cost)',
                linewidth=2, color='#A23B72', alpha=0.9)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Equity Value', fontsize=12)
        ax.set_title('Momentum Factor: Gross vs Net Equity Curve', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)

        # 添加统计信息
        # 回测初始净值为1.0, nav[0]已含第一期收益, 所以总收益 = nav[-1] / 1.0 - 1
        gross_ret = (nav_gross.iloc[-1] - 1) * 100
        net_ret = (nav_net.iloc[-1] - 1) * 100
        cost_drag = gross_ret - net_ret

        textstr = f'Total Return (Gross): {gross_ret:.2f}%\nTotal Return (Net): {net_ret:.2f}%\nCost Drag: {cost_drag:.2f}%'
        ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        output_file = self.figures_dir / 'fig_01_equity_gross_vs_net_momentum.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"  ✅ 已保存: {output_file}")

    def fig_02_drawdown_momentum(self):
        """图2: Momentum净回撤曲线"""

        # 读取回测数据
        from data.data_loader import DataLoader
        from factors.momentum import MomentumFactor
        from factors.factor_processor import FactorProcessor
        from portfolio.portfolio_builder import PortfolioBuilder
        from backtest.engine import BacktestEngine

        loader = DataLoader()
        df_clean = loader.load_cleaned_data()

        momentum = MomentumFactor()
        df_factor = momentum.calculate(
            df_price=df_clean['price'],
            df_return_daily=df_clean.get('daily_return')
        )

        processor = FactorProcessor()
        df_factor = processor.winsorize(df_factor)
        df_factor = processor.zscore_standardize(df_factor)

        builder = PortfolioBuilder(
            entry_quantile=0.25,
            exit_quantile=0.30,
            min_holding_periods=12,
            long_top=True
        )
        df_weights = builder.build(df_factor)

        engine = BacktestEngine(cost_bps=20.0, rebalance_freq='2monthly')
        result = engine.run(df_weights, df_clean['monthly_return'])

        # 计算回撤
        nav_net = result['nav']
        drawdown = drawdown_series(nav_net)

        # 绘图
        fig, ax = plt.subplots(figsize=(12, 6))

        ax.fill_between(drawdown.index, drawdown.values * 100, 0,
                        color='#D62828', alpha=0.6, label='Drawdown')
        ax.plot(drawdown.index, drawdown.values * 100,
               color='#9B2226', linewidth=1.5)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.set_title('Momentum Factor: Net Drawdown Curve (20bps Cost)', fontsize=14, fontweight='bold')
        ax.legend(loc='lower left', fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        # 标注最大回撤
        max_dd = drawdown.min() * 100
        max_dd_date = drawdown.idxmin()
        ax.annotate(f'Max DD: {max_dd:.2f}%',
                   xy=(max_dd_date, max_dd),
                   xytext=(max_dd_date, max_dd - 3),
                   arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                   fontsize=10, color='red', fontweight='bold')

        plt.tight_layout()

        output_file = self.figures_dir / 'fig_02_drawdown_momentum.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"  ✅ 已保存: {output_file}")

    def fig_03_cost_sensitivity_momentum(self):
        """图3: 成本敏感性曲线"""

        # 读取稳健性数据
        robustness_file = self.results_dir / 'robustness_table.csv'
        if not robustness_file.exists():
            logger.error(f"未找到稳健性数据: {robustness_file}")
            return

        df_rob = pd.read_csv(robustness_file)

        # 筛选成本敏感性数据
        cost_data = df_rob[df_rob['test_type'] == '成本敏感性'].copy()

        if len(cost_data) == 0:
            logger.error("未找到成本敏感性数据")
            return

        # 提取成本值
        cost_data['cost_bps'] = cost_data['parameter'].str.extract(r'(\d+)').astype(float)
        cost_data = cost_data.sort_values('cost_bps')

        # 绘图
        fig, ax = plt.subplots(figsize=(10, 6))

        # CAGR曲线
        ax.plot(cost_data['cost_bps'], cost_data['annual_return'] * 100,
               marker='o', linewidth=2.5, markersize=8, color='#2E86AB',
               label='Net CAGR')

        # 添加0线
        ax.axhline(y=0, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Breakeven')

        # 高亮20bps基准点
        baseline_idx = cost_data['cost_bps'] == 20
        if baseline_idx.any():
            baseline_ret = cost_data.loc[baseline_idx, 'annual_return'].values[0] * 100
            ax.plot(20, baseline_ret, 'ro', markersize=12, zorder=5)
            ax.annotate(f'Baseline\n(20bps): {baseline_ret:.2f}%',
                       xy=(20, baseline_ret),
                       xytext=(20, baseline_ret + 0.3),
                       fontsize=10, color='red', fontweight='bold',
                       ha='center')

        ax.set_xlabel('Transaction Cost (bps)', fontsize=12)
        ax.set_ylabel('Net CAGR (%)', fontsize=12)
        ax.set_title('Momentum Factor: Cost Sensitivity Analysis', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)

        # 设置x轴刻度
        ax.set_xticks(cost_data['cost_bps'])

        plt.tight_layout()

        output_file = self.figures_dir / 'fig_03_cost_sensitivity_momentum.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"  ✅ 已保存: {output_file}")

    def fig_04_subsample_bar_momentum(self):
        """图4: 子样本对比条形图"""

        # 读取稳健性数据
        robustness_file = self.results_dir / 'robustness_table.csv'
        if not robustness_file.exists():
            logger.error(f"未找到稳健性数据: {robustness_file}")
            return

        df_rob = pd.read_csv(robustness_file)

        # 筛选子样本数据
        subsample_data = df_rob[df_rob['test_type'] == '子样本'].copy()

        if len(subsample_data) < 2:
            logger.error("子样本数据不足")
            return

        # 绘图
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        periods = subsample_data['parameter'].tolist()
        cagr = (subsample_data['annual_return'] * 100).tolist()
        sharpe = subsample_data['sharpe'].tolist()

        # CAGR条形图
        colors = ['#2E86AB', '#A23B72']
        bars1 = ax1.bar(range(len(periods)), cagr, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax1.set_xlabel('Period', fontsize=12)
        ax1.set_ylabel('Net CAGR (%)', fontsize=12)
        ax1.set_title('Subsample CAGR Comparison', fontsize=13, fontweight='bold')
        ax1.set_xticks(range(len(periods)))
        ax1.set_xticklabels(['Period 1\n(2016-2020)', 'Period 2\n(2020-2026)'], fontsize=10)
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)

        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars1, cagr)):
            ax1.text(bar.get_x() + bar.get_width()/2, val + 0.1,
                    f'{val:.2f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

        # Sharpe条形图
        bars2 = ax2.bar(range(len(periods)), sharpe, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax2.set_xlabel('Period', fontsize=12)
        ax2.set_ylabel('Sharpe Ratio', fontsize=12)
        ax2.set_title('Subsample Sharpe Comparison', fontsize=13, fontweight='bold')
        ax2.set_xticks(range(len(periods)))
        ax2.set_xticklabels(['Period 1\n(2016-2020)', 'Period 2\n(2020-2026)'], fontsize=10)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)

        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars2, sharpe)):
            ax2.text(bar.get_x() + bar.get_width()/2, val + 0.01,
                    f'{val:.4f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        plt.tight_layout()

        output_file = self.figures_dir / 'fig_04_subsample_bar_momentum.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"  ✅ 已保存: {output_file}")

    def fig_05_exposure_alpha_beta(self):
        """图5: Alpha & Beta条形图"""

        # 读取暴露数据
        exposure_file = self.results_dir / 'exposure_stats.csv'
        if not exposure_file.exists():
            logger.error(f"未找到暴露数据: {exposure_file}")
            return

        df_exp = pd.read_csv(exposure_file)

        # 筛选Momentum和Composite
        factors_of_interest = ['Momentum', 'Composite']
        df_plot = df_exp[df_exp['strategy'].isin(factors_of_interest)].copy()

        if len(df_plot) == 0:
            logger.error("未找到Momentum和Composite的暴露数据")
            return

        # 绘图
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        strategies = df_plot['strategy'].tolist()
        alphas = df_plot['alpha'].tolist()
        betas = df_plot['beta'].tolist()

        # Alpha条形图
        colors_alpha = ['#06A77D' if a > 0 else '#D62828' for a in alphas]
        bars1 = ax1.barh(strategies, alphas, color=colors_alpha, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax1.set_xlabel('Alpha (Monthly)', fontsize=12)
        ax1.set_ylabel('Factor', fontsize=12)
        ax1.set_title('Market Exposure: Alpha (OLS Intercept)', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')
        ax1.axvline(x=0, color='black', linestyle='-', linewidth=1)

        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars1, alphas)):
            ax1.text(val + 0.0001 if val > 0 else val - 0.0001, bar.get_y() + bar.get_height()/2,
                    f'{val:.4f}', ha='left' if val > 0 else 'right', va='center',
                    fontsize=11, fontweight='bold')

        # Beta条形图
        colors_beta = ['#2E86AB' if abs(b) < 0.1 else '#F77F00' for b in betas]
        bars2 = ax2.barh(strategies, betas, color=colors_beta, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax2.set_xlabel('Beta (Market Exposure)', fontsize=12)
        ax2.set_ylabel('Factor', fontsize=12)
        ax2.set_title('Market Exposure: Beta (OLS Slope)', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='x')
        ax2.axvline(x=0, color='black', linestyle='-', linewidth=1)

        # 添加阈值线（|beta| < 0.1为市场中性）
        ax2.axvline(x=0.1, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Neutral Threshold (±0.1)')
        ax2.axvline(x=-0.1, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
        ax2.legend(loc='best', fontsize=9)

        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars2, betas)):
            ax2.text(val + 0.005 if val > 0 else val - 0.005, bar.get_y() + bar.get_height()/2,
                    f'{val:.4f}', ha='left' if val > 0 else 'right', va='center',
                    fontsize=11, fontweight='bold')

        plt.tight_layout()

        output_file = self.figures_dir / 'fig_05_exposure_alpha_beta.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"  ✅ 已保存: {output_file}")

    def fig_06_significance_tstats(self):
        """图6: 显著性t统计量对比"""

        # 读取显著性摘要（从significance_summary.md解析，或直接读取中间数据）
        # 这里我们手动构建数据（基于已知结果）
        sig_file = self.results_dir / 'significance_summary.md'
        if not sig_file.exists():
            logger.error(f"未找到显著性摘要: {sig_file}")
            return

        # 解析Markdown表格
        with open(sig_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取表格数据（简单解析）
        import re

        # 查找表格
        table_pattern = r'\| (Momentum|Reversal|LowVolatility|Trend|Composite) \| [\d\.\-]+ \| [\d\.]+ \| \d+ \| ([\d\.\-]+) \| [\d\.]+ \| ([\d\.\-]+) \|'
        matches = re.findall(table_pattern, content)

        if not matches:
            logger.error("无法解析显著性检验表格")
            return

        factors = []
        t_stats = []
        nw_t_stats = []

        for match in matches:
            factor_name, t_stat, nw_t_stat = match
            factors.append(factor_name)
            t_stats.append(float(t_stat))
            nw_t_stats.append(float(nw_t_stat))

        # 绘图
        fig, ax = plt.subplots(figsize=(12, 7))

        x = np.arange(len(factors))
        width = 0.35

        bars1 = ax.bar(x - width/2, t_stats, width, label='Standard t-stat',
                       color='#2E86AB', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, nw_t_stats, width, label='Newey-West t-stat (HAC)',
                       color='#A23B72', alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('Factor', fontsize=12)
        ax.set_ylabel('t-statistic', fontsize=12)
        ax.set_title('Significance Test: Standard vs Newey-West t-statistics', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(factors, fontsize=11, rotation=15, ha='right')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')

        # 添加显著性阈值线（|t| > 1.96 for p < 0.05, two-tailed）
        ax.axhline(y=1.96, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Significance Threshold (|t| > 1.96)')
        ax.axhline(y=-1.96, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)

        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars1, t_stats)):
            ax.text(bar.get_x() + bar.get_width()/2, val + 0.1 if val > 0 else val - 0.1,
                    f'{val:.2f}', ha='center', va='bottom' if val > 0 else 'top',
                    fontsize=9, fontweight='bold')

        for i, (bar, val) in enumerate(zip(bars2, nw_t_stats)):
            ax.text(bar.get_x() + bar.get_width()/2, val + 0.1 if val > 0 else val - 0.1,
                    f'{val:.2f}', ha='center', va='bottom' if val > 0 else 'top',
                    fontsize=9, fontweight='bold')

        plt.tight_layout()

        output_file = self.figures_dir / 'fig_06_significance_tstats.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"  ✅ 已保存: {output_file}")


def main():
    """主函数"""
    logger.info("="*100)
    logger.info("交付图表生成器")
    logger.info("="*100)

    generator = FigureGenerator(results_dir='results')
    generator.generate_all()

    logger.info("\n✅ 所有图表已生成！请查看 results/figures/ 目录")


if __name__ == "__main__":
    main()
