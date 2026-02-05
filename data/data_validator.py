"""
[INPUT]: 两个数据源的DataFrame字典
[OUTPUT]: 验证后的合并数据、验证报告
[POS]: 交叉验证模块(⭐ CRITICAL),确保数据质量

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


def validate_and_merge(
    data_yf: Dict[str, pd.DataFrame],
    data_alpaca: Dict[str, pd.DataFrame],
    price_col: str = 'Adj Close',
    diff_threshold: float = 0.01
) -> Tuple[Dict[str, pd.DataFrame], Dict]:
    """
    交叉验证两个数据源并合并

    Args:
        data_yf: yfinance数据 {ticker: DataFrame}
        data_alpaca: Alpaca数据 {ticker: DataFrame}
        price_col: 用于对比的价格列
        diff_threshold: 差异阈值(超过此比例标记为异常)

    Returns:
        (merged_data, report) 元组
        - merged_data: 合并后的数据
        - report: 验证报告
    """
    logger.info("开始交叉验证双数据源...")

    # 如果Alpaca数据为空,直接返回yfinance数据
    if not data_alpaca:
        logger.warning("Alpaca数据为空,直接使用yfinance数据")
        report = {
            'total_tickers': len(data_yf),
            'validated_tickers': 0,
            'yf_only_tickers': len(data_yf),
            'alpaca_only_tickers': 0,
            'conflicts': 0,
            'conflict_rate': 0.0
        }
        return data_yf, report

    # 找到共同的ticker
    common_tickers = set(data_yf.keys()) & set(data_alpaca.keys())
    yf_only = set(data_yf.keys()) - set(data_alpaca.keys())
    alpaca_only = set(data_alpaca.keys()) - set(data_yf.keys())

    logger.info(f"共同ticker: {len(common_tickers)}, "
                f"仅yfinance: {len(yf_only)}, "
                f"仅Alpaca: {len(alpaca_only)}")

    merged_data = {}
    conflicts_count = 0
    total_comparisons = 0

    # 验证共同ticker
    for ticker in common_tickers:
        df_yf = data_yf[ticker]
        df_alpaca = data_alpaca[ticker]

        # 对齐日期索引
        common_dates = df_yf.index.intersection(df_alpaca.index)

        if len(common_dates) == 0:
            logger.warning(f"{ticker}: 无共同日期,使用yfinance数据")
            merged_data[ticker] = df_yf
            continue

        # 提取共同日期的价格
        price_yf = df_yf.loc[common_dates, price_col]
        price_alpaca = df_alpaca.loc[common_dates, price_col]

        # 计算差异百分比
        diff_pct = (price_yf - price_alpaca) / price_yf
        diff_pct = diff_pct.abs()

        # 统计异常
        conflicts = (diff_pct > diff_threshold).sum()
        total_comparisons += len(common_dates)
        conflicts_count += conflicts

        if conflicts > 0:
            conflict_rate = conflicts / len(common_dates)
            logger.warning(f"{ticker}: {conflicts}/{len(common_dates)} "
                          f"({conflict_rate:.2%}) 数据点差异>{diff_threshold:.1%}")

        # 合并策略: 优先yfinance, 用Alpaca填补缺失值
        df_merged = df_yf.copy()

        # 标记差异过大的数据点为NaN
        if conflicts > 0:
            mask = diff_pct > diff_threshold
            df_merged.loc[mask, price_col] = np.nan

        # 用Alpaca填补yfinance的缺失值
        missing_in_yf = df_merged[price_col].isna()
        if missing_in_yf.any():
            # 对齐Alpaca数据到yfinance的索引
            alpaca_aligned = df_alpaca.reindex(df_merged.index)
            df_merged.loc[missing_in_yf, price_col] = alpaca_aligned.loc[missing_in_yf, price_col]

        merged_data[ticker] = df_merged

    # 添加仅存在于yfinance的数据
    for ticker in yf_only:
        merged_data[ticker] = data_yf[ticker]

    # 添加仅存在于Alpaca的数据
    for ticker in alpaca_only:
        merged_data[ticker] = data_alpaca[ticker]

    # 生成报告
    report = {
        'total_tickers': len(merged_data),
        'validated_tickers': len(common_tickers),
        'yf_only_tickers': len(yf_only),
        'alpaca_only_tickers': len(alpaca_only),
        'conflicts': conflicts_count,
        'total_comparisons': total_comparisons,
        'conflict_rate': conflicts_count / total_comparisons if total_comparisons > 0 else 0.0
    }

    logger.info(f"验证完成: 冲突率 {report['conflict_rate']:.4%} "
                f"({conflicts_count}/{total_comparisons})")

    return merged_data, report


if __name__ == '__main__':
    # 测试
    from data.data_fetcher import YFinanceFetcher, AlpacaFetcher

    test_tickers = ['AAPL', 'MSFT']
    yf_fetcher = YFinanceFetcher()
    alpaca_fetcher = AlpacaFetcher()

    data_yf = yf_fetcher.fetch(test_tickers, '2023-01-01', '2023-12-31')
    data_alpaca = alpaca_fetcher.fetch(test_tickers, '2023-01-01', '2023-12-31')

    merged_data, report = validate_and_merge(data_yf, data_alpaca)

    print("\n验证报告:")
    for key, value in report.items():
        print(f"  {key}: {value}")
