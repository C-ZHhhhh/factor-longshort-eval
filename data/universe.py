"""
[INPUT]: None
[OUTPUT]: S&P 500成分股ticker列表
[POS]: 数据层入口,提供股票池管理

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
from typing import List, Tuple, Dict, Union
from utils.logger import get_logger

logger = get_logger(__name__)


def get_sp500_tickers() -> List[str]:
    """
    从Wikipedia获取S&P 500成分股列表

    Returns:
        ticker列表
    """
    try:
        # 从Wikipedia获取S&P 500成分股表
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

        # 添加User-Agent头避免403错误
        import requests
        from io import StringIO

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # 使用pandas读取HTML表格
        tables = pd.read_html(StringIO(response.text))
        df = tables[0]

        # 提取ticker和公司名称
        df['Symbol'] = df['Symbol'].str.replace('.', '-')
        tickers = df['Symbol'].tolist()

        logger.info(f"成功获取 {len(tickers)} 只S&P 500成分股")
        return tickers

    except Exception as e:
        logger.error(f"获取S&P 500成分股失败: {e}")
        # 返回一个小的测试集
        logger.warning("使用默认测试集: 10只股票")
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
                'TSLA', 'NVDA', 'JPM', 'V', 'JNJ']


def get_sp500_ticker_to_company() -> Dict[str, str]:
    """
    获取S&P 500 ticker到公司名的映射

    Returns:
        {ticker: company_name} 字典
    """
    try:
        # 从Wikipedia获取S&P 500成分股表
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

        # 添加User-Agent头避免403错误
        import requests
        from io import StringIO

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # 使用pandas读取HTML表格
        tables = pd.read_html(StringIO(response.text))
        df = tables[0]

        # 提取ticker和公司名称
        df['Symbol'] = df['Symbol'].str.replace('.', '-')
        ticker_to_company = dict(zip(df['Symbol'], df['Security']))

        logger.info(f"成功获取 {len(ticker_to_company)} 只股票的公司名映射")
        return ticker_to_company

    except Exception as e:
        logger.error(f"获取公司名映射失败: {e}")
        return {}


def get_custom_universe(tickers: List[str]) -> List[str]:
    """
    返回自定义股票池

    Args:
        tickers: 自定义ticker列表

    Returns:
        ticker列表
    """
    logger.info(f"使用自定义股票池: {len(tickers)} 只股票")
    return tickers


def deduplicate_tickers_by_volume(
    ticker_to_company: dict,
    df_volume: pd.DataFrame
) -> List[str]:
    """
    根据成交量去重：同一公司只保留成交量最高的ticker

    Args:
        ticker_to_company: {ticker: company_name} 映射
        df_volume: 成交量数据 (日期 × ticker)

    Returns:
        去重后的ticker列表
    """
    logger.info("开始根据成交量去重ticker...")

    # 标准化公司名：去掉 "(Class A/B/C)" 等后缀
    import re
    def normalize_company_name(name: str) -> str:
        # 移除 (Class X), (Series X) 等后缀
        normalized = re.sub(r'\s*\([Cc]lass [A-Z]\)', '', name)
        normalized = re.sub(r'\s*\([Ss]eries [A-Z]\)', '', normalized)
        return normalized.strip()

    # 计算每个ticker的平均成交量
    avg_volumes = df_volume.mean()

    # 按标准化后的公司名分组
    company_to_tickers = {}
    ticker_to_normalized_company = {}  # 记录标准化后的公司名

    for ticker, company in ticker_to_company.items():
        if ticker not in avg_volumes.index:
            continue  # 跳过没有数据的ticker

        normalized_company = normalize_company_name(company)
        ticker_to_normalized_company[ticker] = normalized_company

        if normalized_company not in company_to_tickers:
            company_to_tickers[normalized_company] = []
        company_to_tickers[normalized_company].append((ticker, avg_volumes[ticker]))

    # 对每个公司，选择成交量最高的ticker
    selected_tickers = []
    duplicates_removed = []

    for normalized_company, tickers_with_volume in company_to_tickers.items():
        if len(tickers_with_volume) == 1:
            # 只有一个ticker，直接保留
            selected_tickers.append(tickers_with_volume[0][0])
        else:
            # 多个ticker，选择成交量最高的
            tickers_with_volume.sort(key=lambda x: x[1], reverse=True)
            selected = tickers_with_volume[0][0]
            removed = [t[0] for t in tickers_with_volume[1:]]

            selected_tickers.append(selected)
            duplicates_removed.extend(removed)

            # 显示详细信息
            ticker_info = ", ".join([
                f"{t} ({v:,.0f})" for t, v in tickers_with_volume
            ])
            logger.info(f"公司 '{normalized_company}': "
                       f"保留 {selected}, 移除 {removed} | "
                       f"成交量: [{ticker_info}]")

    logger.info(f"去重完成: 保留 {len(selected_tickers)} 只股票, "
                f"移除 {len(duplicates_removed)} 只重复股票")

    if duplicates_removed:
        logger.info(f"移除的ticker: {duplicates_removed}")

    return selected_tickers


if __name__ == '__main__':
    # 测试
    tickers = get_sp500_tickers()
    print(f"S&P 500成分股数量: {len(tickers)}")
    print(f"前10只: {tickers[:10]}")
