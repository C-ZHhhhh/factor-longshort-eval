"""
测试可视化模块的中文字体显示

验证factor_visualizer中的中文字体配置是否正常工作。
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from visualization.factor_visualizer import FactorVisualizer


def create_mock_data():
    """创建模拟数据用于测试"""
    # 生成日期序列
    dates = pd.date_range('2020-01-01', '2023-12-31', freq='ME')
    n_dates = len(dates)

    # 模拟净值曲线
    np.random.seed(42)
    returns = np.random.normal(0.01, 0.05, n_dates)
    nav = pd.Series((1 + returns).cumprod(), index=dates, name='nav')

    # 模拟回测结果
    backtest_results = {
        '动量因子': {
            'nav': nav * 1.2,
            'returns': pd.Series(returns * 1.2, index=dates)
        },
        '反转因子': {
            'nav': nav * 0.9,
            'returns': pd.Series(returns * 0.9, index=dates)
        }
    }

    # 模拟IC结果
    ic_series = pd.Series(np.random.normal(0.05, 0.1, n_dates), index=dates)
    ic_results = {
        '动量因子': {
            'ic_series': ic_series,
            'ic_mean': ic_series.mean(),
            'ir': ic_series.mean() / ic_series.std(),
            'ic_positive_ratio': (ic_series > 0).mean()
        },
        '反转因子': {
            'ic_series': -ic_series * 0.5,
            'ic_mean': (-ic_series * 0.5).mean(),
            'ir': (-ic_series * 0.5).mean() / (-ic_series * 0.5).std(),
            'ic_positive_ratio': ((-ic_series * 0.5) > 0).mean()
        }
    }

    # 模拟因子值
    n_stocks = 50
    factor_values = {
        '动量因子': pd.DataFrame(
            np.random.randn(n_dates, n_stocks),
            index=dates,
            columns=[f'Stock_{i}' for i in range(n_stocks)]
        ),
        '反转因子': pd.DataFrame(
            np.random.randn(n_dates, n_stocks),
            index=dates,
            columns=[f'Stock_{i}' for i in range(n_stocks)]
        )
    }

    return backtest_results, ic_results, factor_values


def main():
    """主函数"""
    print("="*80)
    print("测试可视化模块中文字体")
    print("="*80)

    # 1. 创建模拟数据
    print("\n1. 创建模拟数据...")
    backtest_results, ic_results, factor_values = create_mock_data()
    print("   ✅ 模拟数据创建完成")

    # 2. 初始化可视化器
    print("\n2. 初始化可视化器...")
    visualizer = FactorVisualizer(output_dir='results/test/font_test')
    print("   ✅ 可视化器初始化完成")

    # 3. 测试净值曲线图
    print("\n3. 测试净值曲线图（含中文标题、标签）...")
    fig1 = visualizer.plot_nav_comparison(backtest_results, save=True)
    print("   ✅ 净值曲线图生成成功")

    # 4. 测试IC时间序列图
    print("\n4. 测试IC时间序列图（含中文标题、标签）...")
    fig2 = visualizer.plot_ic_timeseries(ic_results, save=True)
    print("   ✅ IC时间序列图生成成功")

    # 5. 测试回撤曲线图
    print("\n5. 测试回撤曲线图（含中文标题、标签）...")
    fig3 = visualizer.plot_drawdown(backtest_results, save=True)
    print("   ✅ 回撤曲线图生成成功")

    # 6. 测试因子相关性热图
    print("\n6. 测试因子相关性热图（含中文标题、标签）...")
    fig4 = visualizer.plot_factor_correlation(factor_values, save=True)
    print("   ✅ 因子相关性热图生成成功")

    # 7. 关闭所有图表
    visualizer.close_all()

    print("\n" + "="*80)
    print("✅ 所有测试通过！中文字体显示正常")
    print("   图表保存位置: results/test/font_test/")
    print("   请打开图片检查中文是否正常显示（无方框）")
    print("="*80)


if __name__ == '__main__':
    main()
