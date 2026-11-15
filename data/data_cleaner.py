"""
[INPUT]: 验证后的数据字典
[OUTPUT]: 清洗后的价格数据、成交量数据、收益率数据
[POS]: 数据清洗模块,处理缺失值、计算收益率

[UPDATE 2026-11-15]:
- 月收益率剔除不完整的最后一个月: 月中下载时最后一个月只有几个交易日,
  原实现把它当成完整月份(标成月末日期)参与回测。
- get_clean_data额外下载市场基准SPY, 以月收益率Series存入缓存的'SPY'键,
  供市场暴露(Beta)分析使用; 之前缓存里没有SPY, 报告里的"对SPY的Beta"
  实际是对股票等权平均算的。
- 缓存里再存一份SPY的日收益率('SPY_daily'键), 供Beta对冲估计每只股票的滚动Beta使用。
  已有的旧缓存用 add_benchmark_daily_to_cache() 补上这一个键, 不用重新下载股票数据
  (重新下载会让股票池变成今天的成分股, 结果就不可比了)。

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

from pathlib import Path

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, Union
from utils.logger import get_logger
from utils.date_utils import is_month_complete

logger = get_logger(__name__)


class DataCleaner:
    """数据清洗器"""

    def __init__(self, missing_threshold: float = 0.3):
        """
        初始化

        Args:
            missing_threshold: 缺失率阈值(超过此比例的股票将被剔除)
        """
        self.missing_threshold = missing_threshold

    def clean(
        self,
        data: Dict[str, pd.DataFrame],
        price_col: str = 'Adj Close',
        ticker_to_company: dict = None,
        requested_end: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        清洗数据并计算收益率

        Args:
            data: {ticker: DataFrame} 字典
            price_col: 价格列名
            ticker_to_company: ticker到公司名的映射（用于去重）
            requested_end: 下载时请求的结束日期(不含当天), 用于判断最后一个月是否完整

        Returns:
            (df_price, df_volume, df_return_daily, df_return_monthly) 元组
            - df_price: 价格面板数据 (日期 × 股票)
            - df_volume: 成交量面板数据 (日期 × 股票)
            - df_return_daily: 日收益率 (日期 × 股票)
            - df_return_monthly: 月收益率 (月末 × 股票)
        """
        logger.info(f"开始清洗 {len(data)} 只股票数据...")

        # 1. 转换为面板数据格式
        price_dict = {}
        volume_dict = {}

        for ticker, df in data.items():
            if price_col in df.columns:
                price_dict[ticker] = df[price_col]
            if 'Volume' in df.columns:
                volume_dict[ticker] = df['Volume']

        df_price = pd.DataFrame(price_dict)
        df_volume = pd.DataFrame(volume_dict)

        logger.info(f"原始数据: {len(df_price)} 日 × {len(df_price.columns)} 股票")

        # 2. 去重：同一公司只保留成交量最高的ticker
        if ticker_to_company:
            from data.universe import deduplicate_tickers_by_volume
            selected_tickers = deduplicate_tickers_by_volume(ticker_to_company, df_volume)
            df_price = df_price[selected_tickers]
            df_volume = df_volume[selected_tickers]
            logger.info(f"去重后: {len(df_price.columns)} 只股票")

        # 3. 剔除缺失率过高的股票
        missing_rate = df_price.isna().sum() / len(df_price)
        valid_tickers = missing_rate[missing_rate <= self.missing_threshold].index.tolist()
        invalid_tickers = missing_rate[missing_rate > self.missing_threshold].index.tolist()

        if invalid_tickers:
            logger.warning(f"剔除 {len(invalid_tickers)} 只缺失率>{self.missing_threshold:.1%}的股票")
            logger.debug(f"剔除列表: {invalid_tickers[:10]}{'...' if len(invalid_tickers) > 10 else ''}")

        df_price = df_price[valid_tickers]
        df_volume = df_volume[valid_tickers]

        # 4. 前向填充缺失值(最多填充5天)
        df_price = df_price.ffill(limit=5)

        # 5. 计算日收益率
        df_return_daily = df_price.pct_change()

        # 6. 重采样到月度并计算月收益率（不含不完整的最后一个月）
        df_return_monthly = self.monthly_return_from_price(df_price, requested_end)

        # 7. 移除全为NaN的行
        df_return_daily = df_return_daily.dropna(how='all')

        logger.info(f"清洗完成:")
        logger.info(f"  价格数据: {len(df_price)} 日 × {len(df_price.columns)} 股票")
        logger.info(f"  成交量数据: {len(df_volume)} 日 × {len(df_volume.columns)} 股票")
        logger.info(f"  日收益率: {len(df_return_daily)} 日")
        logger.info(f"  月收益率: {len(df_return_monthly)} 月")

        return df_price, df_volume, df_return_daily, df_return_monthly


    def monthly_return_from_price(
        self,
        df_price: Union[pd.DataFrame, pd.Series],
        requested_end: Optional[str] = None
    ) -> Union[pd.DataFrame, pd.Series]:
        """
        从日频价格计算月收益率, 并剔除不完整的最后一个月

        Args:
            df_price: 日频价格 (日期 × 股票), 或单只标的的价格Series
            requested_end: 下载时请求的结束日期(不含当天)

        Returns:
            月收益率 (月末 × 股票), 每一行都对应一个走完的月份
        """
        # 月末价格 → 月收益率 = (P_t / P_t-1) - 1
        df_return_monthly = df_price.resample('ME').last().pct_change()
        df_return_monthly = df_return_monthly.dropna(how='all')

        if len(df_return_monthly) > 0:
            last_data_date = df_price.dropna(how='all').index[-1]
            if not is_month_complete(last_data_date, requested_end):
                dropped_month = df_return_monthly.index[-1]
                df_return_monthly = df_return_monthly.iloc[:-1]
                logger.warning(
                    f"最后一个月不完整(数据只到 {last_data_date.date()}), "
                    f"已从月收益率中剔除 {dropped_month.strftime('%Y-%m')}"
                )

        return df_return_monthly


BENCHMARK_MONTHLY_KEY = 'SPY'
BENCHMARK_DAILY_KEY = 'SPY_daily'


def _fetch_benchmark_price(
    yf_fetcher,
    start_date: str,
    end_date: str,
    symbol: str,
    price_col: str
) -> Optional[pd.Series]:
    """下载市场基准的复权价; 下载失败返回None。"""
    data = yf_fetcher.fetch([symbol], start_date, end_date)
    df = data.get(symbol)
    if df is None or price_col not in df.columns or df[price_col].dropna().empty:
        logger.error(f"市场基准 {symbol} 下载失败")
        return None
    return df[price_col]


def fetch_benchmark_returns(
    yf_fetcher,
    start_date: str,
    end_date: str,
    symbol: str = 'SPY',
    price_col: str = 'Adj Close'
) -> Optional[Tuple[pd.Series, pd.Series]]:
    """
    下载市场基准, 一次得到月收益率和日收益率 (来自同一份价格, 保证两者一致)

    Args:
        yf_fetcher: YFinanceFetcher实例
        start_date: 开始日期
        end_date: 结束日期(不含当天)
        symbol: 基准代码, 默认SPY
        price_col: 价格列名(复权价)

    Returns:
        (月收益率Series, 日收益率Series); 下载失败返回None
        (调用方需要明确处理, 不要悄悄换别的基准)
    """
    price = _fetch_benchmark_price(yf_fetcher, start_date, end_date, symbol, price_col)
    if price is None:
        return None

    monthly = DataCleaner().monthly_return_from_price(price, end_date)
    monthly.name = symbol
    daily = price.pct_change().dropna()
    daily.name = symbol
    logger.info(
        f"市场基准 {symbol}: {len(monthly)} 月 "
        f"({monthly.index[0].date()} ~ {monthly.index[-1].date()}), {len(daily)} 个交易日"
    )
    return monthly, daily


def fetch_benchmark_monthly_return(
    yf_fetcher,
    start_date: str,
    end_date: str,
    symbol: str = 'SPY',
    price_col: str = 'Adj Close'
) -> Optional[pd.Series]:
    """下载市场基准并计算月收益率; 下载失败返回None。"""
    returns = fetch_benchmark_returns(yf_fetcher, start_date, end_date, symbol, price_col)
    return None if returns is None else returns[0]


def add_benchmark_daily_to_cache(cache_file, yf_fetcher=None, tolerance: float = 1e-4) -> pd.Series:
    """
    给已有的缓存补上市场基准的日收益率 (只新增 'SPY_daily' 一个键, 其他数据不动)

    下载的日期范围取缓存里价格数据自己的范围。写入前会核对: 用新下载的价格算出的月收益率
    必须和缓存里原有的月收益率对得上, 确认是同一份基准。

    Args:
        cache_file: 缓存文件路径
        yf_fetcher: YFinanceFetcher实例 (默认新建一个)
        tolerance: 新旧月收益率允许的最大差异

    Returns:
        写入缓存的日收益率Series (缓存里已经有的话直接返回原有的)
    """
    cache = pd.read_pickle(cache_file)
    if cache.get(BENCHMARK_DAILY_KEY) is not None:
        logger.info(f"缓存里已有 {BENCHMARK_DAILY_KEY}, 不需要补")
        return cache[BENCHMARK_DAILY_KEY]

    if yf_fetcher is None:
        from data.data_fetcher import YFinanceFetcher
        yf_fetcher = YFinanceFetcher(max_workers=1)

    price_index = cache['price'].index
    start_date = price_index[0].strftime('%Y-%m-%d')
    end_date = (price_index[-1] + pd.Timedelta(days=1)).strftime('%Y-%m-%d')  # 结束日期不含当天
    returns = fetch_benchmark_returns(yf_fetcher, start_date, end_date)
    if returns is None:
        raise RuntimeError("市场基准下载失败, 缓存没有改动")
    monthly, daily = returns

    cached_monthly = cache.get(BENCHMARK_MONTHLY_KEY)
    if cached_monthly is not None:
        common = monthly.index.intersection(cached_monthly.index)
        max_diff = float((monthly[common] - cached_monthly[common]).abs().max())
        if len(common) == 0 or max_diff > tolerance:
            raise RuntimeError(
                f"新下载的基准和缓存里的月收益率对不上 (最大差异 {max_diff:.6f}), 缓存没有改动"
            )
        logger.info(f"与缓存里的月收益率核对通过: {len(common)} 个月, 最大差异 {max_diff:.2e}")

    cache[BENCHMARK_DAILY_KEY] = daily
    # 先写到临时文件再替换: 写到一半出错也不会弄坏原来的缓存
    temp_file = Path(str(cache_file) + '.tmp')
    pd.to_pickle(cache, temp_file)
    temp_file.replace(cache_file)
    logger.info(f"已写入 {BENCHMARK_DAILY_KEY}: {len(daily)} 个交易日 → {cache_file}")
    return daily


def get_clean_data(
    tickers: list = None,
    start_date: str = None,
    end_date: str = None,
    use_cache: bool = True,
    deduplicate: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    便捷函数: 一站式获取清洗后的数据

    Args:
        tickers: ticker列表(None表示使用S&P 500)
        start_date: 开始日期
        end_date: 结束日期
        use_cache: 是否使用缓存
        deduplicate: 是否去重（同一公司只保留成交量最高的ticker）

    Returns:
        (df_price, df_volume, df_return_daily, df_return_monthly) 元组
    """
    from data.universe import get_sp500_tickers
    from data.data_fetcher import YFinanceFetcher, AlpacaFetcher
    from data.data_validator import validate_and_merge
    from utils.config import config
    import os

    # 设置默认参数
    ticker_to_company = None
    if tickers is None:
        from data.universe import get_sp500_tickers, get_sp500_ticker_to_company
        tickers = get_sp500_tickers()
        if deduplicate:
            ticker_to_company = get_sp500_ticker_to_company()
            logger.info(f"获取S&P 500: {len(tickers)} 只ticker，将根据成交量去重")

    if start_date is None:
        start_date = config.get('data.start_date', '2015-01-01')

    if end_date is None:
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')

    # 检查缓存
    cache_dir = config.get('data.data_dir', 'data/cache')
    os.makedirs(cache_dir, exist_ok=True)

    dedup_suffix = '_dedup' if deduplicate else ''
    cache_file = os.path.join(
        cache_dir,
        f'clean_data_{start_date}_{end_date}_{len(tickers)}{dedup_suffix}.pkl'
    )

    if use_cache and os.path.exists(cache_file):
        logger.info(f"从缓存加载数据: {cache_file}")
        cache_data = pd.read_pickle(cache_file)
        # 向后兼容: 旧缓存可能没有volume
        if 'volume' in cache_data:
            return cache_data['price'], cache_data['volume'], cache_data['return_daily'], cache_data['return_monthly']
        else:
            logger.warning("缓存文件缺少volume数据，将返回None作为volume")
            return cache_data['price'], None, cache_data['return_daily'], cache_data['return_monthly']

    # 下载数据
    logger.info("开始下载数据...")
    yf_fetcher = YFinanceFetcher(max_workers=10)
    alpaca_fetcher = AlpacaFetcher()

    data_yf = yf_fetcher.fetch(tickers, start_date, end_date)
    data_alpaca = alpaca_fetcher.fetch(tickers, start_date, end_date)

    # 验证合并
    merged_data, report = validate_and_merge(data_yf, data_alpaca)

    logger.info(f"验证报告: 冲突率 {report['conflict_rate']:.4%}")

    # 清洗数据
    cleaner = DataCleaner(missing_threshold=0.3)
    df_price, df_volume, df_return_daily, df_return_monthly = cleaner.clean(
        merged_data,
        ticker_to_company=ticker_to_company,
        requested_end=end_date
    )

    # 保存缓存
    if use_cache:
        cache_data = {
            'price': df_price,
            'volume': df_volume,
            'return_daily': df_return_daily,
            'return_monthly': df_return_monthly
        }

        # 市场基准(SPY): 月收益率用于Beta/暴露分析, 日收益率用于Beta对冲里估计股票的滚动Beta
        benchmark_returns = fetch_benchmark_returns(yf_fetcher, start_date, end_date)
        if benchmark_returns is not None:
            cache_data[BENCHMARK_MONTHLY_KEY], cache_data[BENCHMARK_DAILY_KEY] = benchmark_returns
        pd.to_pickle(cache_data, cache_file)
        logger.info(f"数据已缓存: {cache_file}")

    return df_price, df_volume, df_return_daily, df_return_monthly


if __name__ == '__main__':
    # 测试: 下载少量数据
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    df_price, df_volume, df_return_daily, df_return_monthly = get_clean_data(
        tickers=test_tickers,
        start_date='2023-01-01',
        end_date='2023-12-31',
        use_cache=False
    )

    print(f"\n价格数据: {df_price.shape}")
    print(df_price.head())

    print(f"\n成交量数据: {df_volume.shape if df_volume is not None else 'None'}")
    if df_volume is not None:
        print(df_volume.head())

    print(f"\n日收益率: {df_return_daily.shape}")
    print(df_return_daily.head())

    print(f"\n月收益率: {df_return_monthly.shape}")
    print(df_return_monthly.head())
