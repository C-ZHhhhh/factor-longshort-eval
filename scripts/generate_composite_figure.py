"""
生成 Composite 因子的 gross vs net equity curve
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from data.data_loader import DataLoader
from factors.momentum import MomentumFactor
from factors.reversal import ReversalFactor
from factors.low_volatility import LowVolatilityFactor
from factors.trend import TrendFactor
from factors.factor_processor import FactorProcessor
from portfolio.portfolio_builder import PortfolioBuilder
from backtest.engine import BacktestEngine

logger = get_logger(__name__)

# 设置中文字体和样式
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")


def generate_composite_figure():
    """生成Composite因子的gross vs net曲线"""

    logger.info("开始生成 Composite 因子图表...")

    # 加载数据
    loader = DataLoader()
    df_clean = loader.load_cleaned_data()

    # 计算各因子
    factors = {
        'Momentum': MomentumFactor(),
        'Reversal': ReversalFactor(),
        'LowVolatility': LowVolatilityFactor(),
        'Trend': TrendFactor()
    }

    factor_dfs = {}
    processor = FactorProcessor()

    for name, factor_obj in factors.items():
        logger.info(f"计算 {name} 因子...")
        df_factor = factor_obj.calculate(
            df_price=df_clean['price'],
            df_return_daily=df_clean.get('daily_return')
        )
        df_factor = processor.winsorize(df_factor)
        df_factor = processor.zscore_standardize(df_factor)
        factor_dfs[name] = df_factor

    # 合成因子（等权平均）
    logger.info("合成Composite因子...")
    df_composite = sum(factor_dfs.values()) / len(factor_dfs)

    # 构建组合
    builder = PortfolioBuilder(
        entry_quantile=0.25,
        exit_quantile=0.30,
        min_holding_periods=12,
        long_top=True
    )
    df_weights = builder.build(df_composite)

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
    ax.set_title('Composite Factor: Gross vs Net Equity Curve', fontsize=14, fontweight='bold')
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

    output_file = Path('results/figures/fig_07_equity_gross_vs_net_composite.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✅ 已保存: {output_file}")


if __name__ == "__main__":
    generate_composite_figure()
