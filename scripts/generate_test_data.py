"""
生成测试数据

用于验证评估系统功能
"""

import pandas as pd
import numpy as np
from pathlib import Path


def generate_test_data():
    """生成小型测试数据集"""

    np.random.seed(42)

    # 时间范围: 2020-01-01 to 2023-12-31 (月末)
    dates = pd.date_range('2020-01-31', '2023-12-31', freq='ME')
    n_dates = len(dates)

    # 股票池: 50只股票
    tickers = [f'STOCK_{i:02d}' for i in range(50)]
    n_stocks = len(tickers)

    print(f"生成测试数据: {n_dates} 个月 × {n_stocks} 只股票")

    # 1. 生成价格数据
    # 初始价格
    initial_prices = np.random.uniform(50, 200, n_stocks)

    # 每月收益率（正态分布）
    monthly_returns = np.random.normal(0.01, 0.05, (n_dates, n_stocks))

    # 计算价格
    prices = np.zeros((n_dates, n_stocks))
    prices[0] = initial_prices
    for i in range(1, n_dates):
        prices[i] = prices[i-1] * (1 + monthly_returns[i])

    df_price = pd.DataFrame(prices, index=dates, columns=tickers)

    # 2. 生成月度收益率
    df_monthly_return = pd.DataFrame(monthly_returns, index=dates, columns=tickers)

    # 3. 生成日度收益率（简化版，每月20个交易日）
    daily_dates = []
    for month_end in dates:
        # 每月20个交易日
        month_start = month_end - pd.Timedelta(days=28)
        daily_dates.extend(pd.date_range(month_start, month_end, periods=20).tolist())

    n_daily = len(daily_dates)
    daily_returns = np.random.normal(0.0005, 0.02, (n_daily, n_stocks))
    df_daily_return = pd.DataFrame(daily_returns, index=daily_dates, columns=tickers)

    # 4. 生成成交量数据（可选）
    volumes = np.random.uniform(1e6, 1e8, (n_dates, n_stocks))
    df_volume = pd.DataFrame(volumes, index=dates, columns=tickers)

    # 5. 生成 SPY 市场指数（用于 beta 计算）
    spy_returns = np.random.normal(0.008, 0.04, n_dates)
    df_spy = pd.Series(spy_returns, index=dates, name='SPY')

    # 保存数据
    data_dir = Path('data/clean')
    data_dir.mkdir(parents=True, exist_ok=True)

    df_price.to_csv(data_dir / 'price.csv')
    df_monthly_return.to_csv(data_dir / 'monthly_return.csv')
    df_daily_return.to_csv(data_dir / 'daily_return.csv')
    df_volume.to_csv(data_dir / 'volume.csv')
    df_spy.to_csv(data_dir / 'spy_returns.csv')

    print(f"✅ 测试数据已保存到: {data_dir}")
    print(f"   - price.csv: {df_price.shape}")
    print(f"   - monthly_return.csv: {df_monthly_return.shape}")
    print(f"   - daily_return.csv: {df_daily_return.shape}")
    print(f"   - volume.csv: {df_volume.shape}")
    print(f"   - spy_returns.csv: {df_spy.shape}")


if __name__ == '__main__':
    generate_test_data()
