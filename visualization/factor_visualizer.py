"""
因子回测可视化模块

提供4种核心图表：
1. 净值曲线对比图 - 多因子净值曲线对比
2. IC时间序列图 - 因子IC随时间变化
3. 回撤曲线图 - 回撤分析
4. 因子相关性热图 - 因子间相关性分析

[INPUT]:
- 回测结果、IC序列、因子值

[OUTPUT]:
- PNG静态图（matplotlib）
- HTML交互图（plotly，可选）

[POS]:
可视化层核心模块

[PROTOCOL]:
1. 支持中文显示
2. 统一配色方案
3. 自动保存到指定目录
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import warnings
import platform

from backtest.metrics import drawdown_series

warnings.filterwarnings('ignore')

# 设置seaborn样式
sns.set_style("whitegrid")
sns.set_palette("husl")


class FactorVisualizer:
    """
    因子回测可视化器

    提供4种核心图表的生成功能
    """

    def __init__(self, output_dir: str = 'results/figures'):
        """
        初始化可视化器

        Parameters:
        -----------
        output_dir : str
            图表输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 配置中文字体
        self._configure_chinese_font()

        # 配色方案
        self.colors = {
            'Momentum': '#1f77b4',
            'Reversal': '#ff7f0e',
            'LowVolatility': '#2ca02c',
            'Trend': '#d62728',
            'Liquidity': '#9467bd',
            'Composite': '#8c564b',
            'Benchmark': '#7f7f7f'
        }

    def _configure_chinese_font(self):
        """配置中文字体"""
        system = platform.system()

        # 根据操作系统选择字体
        if system == 'Darwin':  # macOS
            fonts = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS', 'Songti SC']
        elif system == 'Windows':
            fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
        elif system == 'Linux':
            fonts = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Droid Sans Fallback']
        else:
            fonts = []

        # 配置matplotlib
        if fonts:
            mpl.rcParams['font.sans-serif'] = fonts + ['DejaVu Sans', 'Arial']
            mpl.rcParams['axes.unicode_minus'] = False
            mpl.rcParams['font.family'] = 'sans-serif'

    def plot_nav_comparison(
        self,
        backtest_results: Dict[str, Dict],
        figsize: Tuple[int, int] = (14, 8),
        save: bool = True
    ) -> plt.Figure:
        """
        绘制净值曲线对比图

        Parameters:
        -----------
        backtest_results : dict
            {factor_name: backtest_result} 字典
        figsize : tuple
            图表尺寸
        save : bool
            是否保存图表

        Returns:
        --------
        fig : Figure
            matplotlib图表对象
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, height_ratios=[3, 1])

        # 子图1: 净值曲线
        for factor_name, result in backtest_results.items():
            nav = result['nav']
            color = self.colors.get(factor_name, None)
            ax1.plot(
                nav.index,
                nav.values,
                label=factor_name,
                linewidth=2,
                color=color,
                alpha=0.8
            )

        ax1.set_title('多因子净值曲线对比', fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('净值', fontsize=12)
        ax1.legend(loc='upper left', fontsize=10, framealpha=0.9)
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5)

        # 子图2: 月收益率柱状图（以第一个因子为例）
        first_factor = list(backtest_results.keys())[0]
        returns = backtest_results[first_factor]['returns']
        colors_bar = ['green' if r > 0 else 'red' for r in returns.values]
        ax2.bar(
            returns.index,
            returns.values,
            color=colors_bar,
            alpha=0.6,
            width=20
        )
        ax2.set_title(f'{first_factor} 月度收益率', fontsize=12, pad=10)
        ax2.set_ylabel('月收益率', fontsize=10)
        ax2.axhline(y=0, color='black', linewidth=1)
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save:
            save_path = self.output_dir / 'nav_comparison.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ 净值曲线对比图已保存: {save_path}")

        return fig

    def plot_ic_timeseries(
        self,
        ic_results: Dict[str, Dict],
        figsize: Tuple[int, int] = (14, 10),
        save: bool = True
    ) -> plt.Figure:
        """
        绘制IC时间序列图

        Parameters:
        -----------
        ic_results : dict
            {factor_name: ic_result} 字典
        figsize : tuple
            图表尺寸
        save : bool
            是否保存图表

        Returns:
        --------
        fig : Figure
            matplotlib图表对象
        """
        n_factors = len(ic_results)
        fig, axes = plt.subplots(n_factors, 1, figsize=figsize)

        if n_factors == 1:
            axes = [axes]

        for idx, (factor_name, ic_result) in enumerate(ic_results.items()):
            ax = axes[idx]
            ic_series = ic_result['ic_series']

            # IC时间序列
            color = self.colors.get(factor_name, 'blue')
            ax.plot(
                ic_series.index,
                ic_series.values,
                color=color,
                linewidth=1.5,
                alpha=0.7,
                label='IC'
            )

            # 12个月移动平均
            ic_ma = ic_series.rolling(12).mean()
            ax.plot(
                ic_ma.index,
                ic_ma.values,
                color=color,
                linewidth=2.5,
                alpha=1.0,
                label='IC (12月MA)'
            )

            # 零线
            ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)

            # IC均值线
            ic_mean = ic_result['ic_mean']
            ax.axhline(
                y=ic_mean,
                color='red',
                linestyle=':',
                linewidth=2,
                alpha=0.7,
                label=f'IC均值 = {ic_mean:.4f}'
            )

            # 填充正负区域
            ax.fill_between(
                ic_series.index,
                0,
                ic_series.values,
                where=(ic_series.values > 0),
                color='green',
                alpha=0.2
            )
            ax.fill_between(
                ic_series.index,
                0,
                ic_series.values,
                where=(ic_series.values <= 0),
                color='red',
                alpha=0.2
            )

            # 标题和标签
            ir = ic_result['ir']
            ic_pos_ratio = ic_result['ic_positive_ratio']
            ax.set_title(
                f'{factor_name} | IR={ir:.4f} | IC均值={ic_mean:.4f} | IC正占比={ic_pos_ratio:.2%}',
                fontsize=11,
                fontweight='bold'
            )
            ax.set_ylabel('IC', fontsize=10)
            ax.legend(loc='upper left', fontsize=9)
            ax.grid(True, alpha=0.3)

        axes[-1].set_xlabel('日期', fontsize=11)
        fig.suptitle('因子IC时间序列分析', fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()

        if save:
            save_path = self.output_dir / 'ic_timeseries.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ IC时间序列图已保存: {save_path}")

        return fig

    def plot_drawdown(
        self,
        backtest_results: Dict[str, Dict],
        figsize: Tuple[int, int] = (14, 8),
        save: bool = True
    ) -> plt.Figure:
        """
        绘制回撤曲线图

        Parameters:
        -----------
        backtest_results : dict
            {factor_name: backtest_result} 字典
        figsize : tuple
            图表尺寸
        save : bool
            是否保存图表

        Returns:
        --------
        fig : Figure
            matplotlib图表对象
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, height_ratios=[3, 2])

        # 缓存 drawdown 计算结果，避免重复计算
        drawdown_cache = {}

        print("\n" + "="*80)
        print("Drawdown 计算与独立性验证")
        print("="*80)

        # 子图1: 回撤曲线
        for factor_name, result in backtest_results.items():
            nav = result['nav'].copy()  # 复制以确保不影响原数据

            # 计算回撤（历史高点包含初始净值）
            drawdown = drawdown_series(nav)

            # 缓存结果
            drawdown_cache[factor_name] = drawdown.copy()

            print(f"\n{factor_name}:")
            print(f"  NAV 样本数: {len(nav)}")
            print(f"  Drawdown 范围: [{drawdown.min():.6f}, {drawdown.max():.6f}]")
            print(f"  最大回撤: {drawdown.min():.4%}")

            color = self.colors.get(factor_name, None)
            ax1.plot(
                drawdown.index,
                drawdown.values * 100,  # 转换为百分比
                label=f"{factor_name} (最大: {drawdown.min():.2%})",
                linewidth=2,
                color=color,
                alpha=0.8
            )

            # 填充回撤区域
            ax1.fill_between(
                drawdown.index,
                0,
                drawdown.values * 100,
                color=color,
                alpha=0.2
            )

        # Sanity Check: 检查不同因子的 drawdown 是否被复用
        if len(drawdown_cache) >= 2:
            print("\n" + "-"*80)
            print("Sanity Check: Drawdown 独立性验证")
            print("-"*80)

            factor_names = list(drawdown_cache.keys())
            for i in range(len(factor_names)):
                for j in range(i+1, len(factor_names)):
                    name1, name2 = factor_names[i], factor_names[j]
                    dd1, dd2 = drawdown_cache[name1], drawdown_cache[name2]

                    # 对齐时间索引
                    common_idx = dd1.index.intersection(dd2.index)
                    if len(common_idx) == 0:
                        print(f"\n{name1} vs {name2}: 无共同时间索引，跳过对比")
                        continue

                    dd1_aligned = dd1.loc[common_idx]
                    dd2_aligned = dd2.loc[common_idx]

                    # 计算相关性
                    correlation = dd1_aligned.corr(dd2_aligned)

                    # 检查是否几乎相同
                    is_close = np.allclose(dd1_aligned.values, dd2_aligned.values, rtol=1e-5, atol=1e-8)

                    # 统计信息
                    dd1_min, dd1_max = dd1_aligned.min(), dd1_aligned.max()
                    dd2_min, dd2_max = dd2_aligned.min(), dd2_aligned.max()

                    print(f"\n{name1} vs {name2}:")
                    print(f"  相关系数: {correlation:.6f}")
                    print(f"  是否几乎相同 (np.allclose): {is_close}")
                    print(f"  {name1} 范围: [{dd1_min:.6f}, {dd1_max:.6f}]")
                    print(f"  {name2} 范围: [{dd2_min:.6f}, {dd2_max:.6f}]")

                    # 如果几乎相同，发出警告
                    if is_close:
                        print(f"  ⚠️  警告: {name1} 和 {name2} 的 drawdown 序列几乎相同!")
                        print(f"     这可能表示数据复用错误，请检查回测逻辑!")
                    elif correlation > 0.99:
                        print(f"  ⚠️  警告: {name1} 和 {name2} 的 drawdown 高度相关 (r={correlation:.6f})!")
                        print(f"     这可能表示策略高度相似或数据问题!")
                    else:
                        print(f"  ✅ 通过: 两个因子的 drawdown 序列独立")

        print("="*80 + "\n")

        ax1.set_title('回撤曲线对比', fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('回撤 (%)', fontsize=12)
        ax1.legend(loc='lower left', fontsize=10, framealpha=0.9)
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=1)

        # 子图2: 水下时间分析（以最佳因子为例，复用缓存的 drawdown）
        best_factor = list(backtest_results.keys())[0]
        drawdown = drawdown_cache[best_factor]  # 从缓存读取，避免重复计算

        # 找出所有回撤期
        underwater = drawdown < 0
        underwater_periods = []
        start = None
        for i, is_underwater in enumerate(underwater):
            if is_underwater and start is None:
                start = i
            elif not is_underwater and start is not None:
                underwater_periods.append((start, i - 1))
                start = None
        if start is not None:
            underwater_periods.append((start, len(underwater) - 1))

        # 绘制水下时间
        colors_uw = []
        for start, end in underwater_periods:
            duration = end - start + 1
            depth = drawdown.iloc[start:end+1].min()
            color = 'red' if depth < -0.2 else 'orange' if depth < -0.1 else 'yellow'
            colors_uw.append(color)

        if underwater_periods:
            durations = [end - start + 1 for start, end in underwater_periods]
            ax2.bar(
                range(len(underwater_periods)),
                durations,
                color=colors_uw,
                alpha=0.7
            )
            ax2.set_title(f'{best_factor} 水下时间分析', fontsize=12, pad=10)
            ax2.set_xlabel('回撤期次', fontsize=10)
            ax2.set_ylabel('水下月数', fontsize=10)
            ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save:
            save_path = self.output_dir / 'drawdown_analysis.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ 回撤曲线图已保存: {save_path}")

        return fig

    def plot_factor_correlation(
        self,
        factor_values: Dict[str, pd.DataFrame],
        method: str = 'spearman',
        figsize: Tuple[int, int] = (10, 8),
        save: bool = True
    ) -> plt.Figure:
        """
        绘制因子相关性热图

        Parameters:
        -----------
        factor_values : dict
            {factor_name: factor_df} 字典
        method : str
            相关性计算方法 ('spearman' 或 'pearson')
        figsize : tuple
            图表尺寸
        save : bool
            是否保存图表

        Returns:
        --------
        fig : Figure
            matplotlib图表对象
        """
        # 对齐所有因子到相同的时间索引
        all_dates = None
        aligned_factors = {}

        for factor_name, factor_df in factor_values.items():
            if all_dates is None:
                all_dates = factor_df.index
            else:
                all_dates = all_dates.intersection(factor_df.index)

        for factor_name, factor_df in factor_values.items():
            aligned_factors[factor_name] = factor_df.loc[all_dates].mean(axis=1)

        # 构建因子矩阵
        factor_matrix = pd.DataFrame(aligned_factors)

        # 计算相关系数矩阵
        if method == 'spearman':
            corr_matrix = factor_matrix.corr(method='spearman')
        else:
            corr_matrix = factor_matrix.corr(method='pearson')

        # 绘制热图
        fig, ax = plt.subplots(figsize=figsize)

        # 使用seaborn绘制热图
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.3f',
            cmap='RdBu_r',
            center=0,
            square=True,
            linewidths=1,
            cbar_kws={"shrink": 0.8},
            vmin=-1,
            vmax=1,
            ax=ax
        )

        ax.set_title(
            f'因子相关性热图 ({method.capitalize()})',
            fontsize=16,
            fontweight='bold',
            pad=20
        )

        # 旋转标签
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)

        plt.tight_layout()

        if save:
            save_path = self.output_dir / 'factor_correlation_heatmap.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ 因子相关性热图已保存: {save_path}")

        return fig

    def plot_gross_vs_net_nav(
        self,
        backtest_results: Dict[str, Dict],
        figsize: Tuple[int, int] = (14, 10),
        save: bool = True
    ) -> plt.Figure:
        """
        绘制毛收益 vs 净收益对比图

        Parameters:
        -----------
        backtest_results : dict
            {factor_name: backtest_result} 字典
            每个 result 必须包含 'nav' 和 'nav_no_cost'
        figsize : tuple
            图表尺寸
        save : bool
            是否保存图表

        Returns:
        --------
        fig : Figure
            matplotlib图表对象
        """
        n_factors = len(backtest_results)
        fig, axes = plt.subplots(n_factors, 1, figsize=figsize)

        if n_factors == 1:
            axes = [axes]

        for idx, (factor_name, result) in enumerate(backtest_results.items()):
            ax = axes[idx]

            nav_net = result['nav']
            nav_gross = result['nav_no_cost']

            # 绘制净值曲线
            color = self.colors.get(factor_name, 'blue')

            ax.plot(
                nav_gross.index,
                nav_gross.values,
                label='毛收益 (Gross)',
                linewidth=2,
                color=color,
                linestyle='--',
                alpha=0.8
            )

            ax.plot(
                nav_net.index,
                nav_net.values,
                label='净收益 (Net)',
                linewidth=2,
                color=color,
                linestyle='-',
                alpha=1.0
            )

            # 计算成本拖累
            final_return_gross = nav_gross.iloc[-1] - 1
            final_return_net = nav_net.iloc[-1] - 1
            cost_drag = final_return_net - final_return_gross

            # 填充成本拖累区域
            ax.fill_between(
                nav_gross.index,
                nav_net.values,
                nav_gross.values,
                color='red',
                alpha=0.2,
                label=f'成本拖累 ({cost_drag:.2%})'
            )

            # 设置标题和标签
            ax.set_title(
                f'{factor_name} | 毛收益: {final_return_gross:.2%}, '
                f'净收益: {final_return_net:.2%}, 成本拖累: {cost_drag:.2%}',
                fontsize=11,
                fontweight='bold'
            )
            ax.set_ylabel('净值', fontsize=10)
            ax.legend(loc='upper left', fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5)

        axes[-1].set_xlabel('日期', fontsize=11)
        fig.suptitle('毛收益 vs 净收益对比', fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()

        if save:
            save_path = self.output_dir / 'equity_gross_vs_net.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ 毛收益vs净收益对比图已保存: {save_path}")

        return fig

    def generate_all_plots(
        self,
        backtest_results: Dict[str, Dict],
        ic_results: Dict[str, Dict],
        factor_values: Dict[str, pd.DataFrame]
    ) -> Dict[str, plt.Figure]:
        """
        一次性生成所有图表

        Parameters:
        -----------
        backtest_results : dict
            回测结果字典
        ic_results : dict
            IC分析结果字典
        factor_values : dict
            因子值字典

        Returns:
        --------
        figures : dict
            {plot_name: figure} 字典
        """
        print("\n" + "="*60)
        print("开始生成可视化图表...")
        print("="*60)

        figures = {}

        # 1. 净值曲线对比图
        print("\n[1/5] 生成净值曲线对比图...")
        figures['nav_comparison'] = self.plot_nav_comparison(backtest_results)

        # 2. IC时间序列图
        print("\n[2/5] 生成IC时间序列图...")
        figures['ic_timeseries'] = self.plot_ic_timeseries(ic_results)

        # 3. 回撤曲线图
        print("\n[3/5] 生成回撤曲线图...")
        figures['drawdown'] = self.plot_drawdown(backtest_results)

        # 4. 因子相关性热图
        print("\n[4/5] 生成因子相关性热图...")
        figures['correlation'] = self.plot_factor_correlation(factor_values)

        # 5. 毛收益 vs 净收益对比图
        print("\n[5/5] 生成毛收益vs净收益对比图...")
        figures['gross_vs_net'] = self.plot_gross_vs_net_nav(backtest_results)

        print("\n" + "="*60)
        print(f"✅ 所有图表已生成! 保存位置: {self.output_dir}")
        print("="*60)

        return figures

    def close_all(self):
        """关闭所有图表"""
        plt.close('all')


if __name__ == '__main__':
    """测试代码"""
    print("因子可视化模块")
    print("请使用 generate_visualizations.py 脚本生成图表")
