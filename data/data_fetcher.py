"""
[INPUT]: ticker列表、日期区间
[OUTPUT]: 价格和成交量的DataFrame
[POS]: 双数据源获取器(yfinance + Alpaca),支持并行下载

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from utils.logger import get_logger
from utils.config import config

logger = get_logger(__name__)


class YFinanceFetcher:
    """yfinance数据获取器"""

    def __init__(self, max_workers: int = 10):
        """
        初始化

        Args:
            max_workers: 并行下载线程数
        """
        self.max_workers = max_workers

    def fetch(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str = None
    ) -> Dict[str, pd.DataFrame]:
        """
        批量下载股票数据

        Args:
            tickers: ticker列表
            start_date: 开始日期
            end_date: 结束日期(None表示当前日期)

        Returns:
            {ticker: DataFrame} 字典
        """
        logger.info(f"开始从yfinance下载 {len(tickers)} 只股票数据...")
        logger.info(f"日期区间: {start_date} ~ {end_date or '今天'}")

        results = {}
        failed = []

        # 使用yfinance的批量下载功能
        try:
            # 一次性下载所有ticker
            data = yf.download(
                tickers=tickers,
                start=start_date,
                end=end_date,
                group_by='ticker',
                auto_adjust=False,  # 不自动复权,手动使用Adj Close
                threads=True,
                progress=True
            )

            # 处理下载结果
            if len(tickers) == 1 and not isinstance(data.columns, pd.MultiIndex):
                # 单个ticker且列是扁平的(旧版yfinance): 整张表就是这只股票
                # 新版yfinance即使只有一只也返回(ticker, 字段)两层列, 走下面的通用分支
                ticker = tickers[0]
                if not data.empty:
                    results[ticker] = data
                else:
                    failed.append(ticker)
            else:
                # 多个ticker
                for ticker in tickers:
                    try:
                        df = data[ticker]
                        if not df.empty and not df['Adj Close'].isna().all():
                            results[ticker] = df
                        else:
                            failed.append(ticker)
                    except KeyError:
                        failed.append(ticker)
                        continue

        except Exception as e:
            logger.error(f"批量下载失败: {e}")
            logger.warning("切换到单个下载模式...")

            # 降级到单个下载
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._fetch_single, ticker, start_date, end_date): ticker
                    for ticker in tickers
                }

                for future in tqdm(as_completed(futures), total=len(tickers), desc="下载进度"):
                    ticker = futures[future]
                    try:
                        df = future.result()
                        if df is not None and not df.empty:
                            results[ticker] = df
                        else:
                            failed.append(ticker)
                    except Exception as e:
                        logger.warning(f"{ticker} 下载失败: {e}")
                        failed.append(ticker)

        logger.info(f"下载完成: 成功 {len(results)}, 失败 {len(failed)}")
        if failed:
            logger.warning(f"失败列表: {failed[:10]}{'...' if len(failed) > 10 else ''}")

        return results

    def _fetch_single(
        self,
        ticker: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        下载单个股票数据

        Args:
            ticker: ticker
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame或None
        """
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date, auto_adjust=False)

            if df.empty:
                return None

            # 重命名列(统一格式)
            df.columns = [col.replace(' ', '_') for col in df.columns]

            return df

        except Exception as e:
            logger.debug(f"{ticker} 下载失败: {e}")
            return None


class AlpacaFetcher:
    """Alpaca数据获取器(备用数据源)"""

    def __init__(self):
        """初始化Alpaca客户端"""
        self.api_key = config.get('api.alpaca.api_key')
        self.secret_key = config.get('api.alpaca.secret_key')
        self.base_url = config.get('api.alpaca.base_url', 'https://paper-api.alpaca.markets')
        self.enabled = self.api_key is not None and self.secret_key is not None

        if not self.enabled:
            logger.warning("Alpaca API密钥未配置,将跳过Alpaca数据获取")
            logger.info("配置方法: 在.env文件中添加 ALPACA_API_KEY 和 ALPACA_SECRET_KEY")
            logger.info("注册地址: https://alpaca.markets (免费账户即可)")
            self.client = None
        else:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                from alpaca.data.requests import StockBarsRequest
                from alpaca.data.timeframe import TimeFrame

                self.client = StockHistoricalDataClient(self.api_key, self.secret_key)
                self.StockBarsRequest = StockBarsRequest
                self.TimeFrame = TimeFrame
                logger.info("Alpaca客户端初始化成功")
            except Exception as e:
                logger.error(f"Alpaca客户端初始化失败: {e}")
                self.enabled = False
                self.client = None

    def fetch(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str = None
    ) -> Dict[str, pd.DataFrame]:
        """
        批量下载股票数据

        Args:
            tickers: ticker列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {ticker: DataFrame} 字典
        """
        if not self.enabled or self.client is None:
            return {}

        logger.info(f"开始从Alpaca下载 {len(tickers)} 只股票数据...")
        logger.info(f"日期区间: {start_date} ~ {end_date or '今天'}")

        results = {}
        failed = []

        # Alpaca批量下载限制较多,使用小批次下载
        batch_size = 100  # 每批100只股票

        for i in range(0, len(tickers), batch_size):
            batch_tickers = tickers[i:i + batch_size]
            logger.info(f"下载批次 {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1}")

            try:
                # 创建请求
                request_params = self.StockBarsRequest(
                    symbol_or_symbols=batch_tickers,
                    timeframe=self.TimeFrame.Day,
                    start=start_date,
                    end=end_date
                )

                # 获取数据
                bars = self.client.get_stock_bars(request_params)

                # 转换为DataFrame字典
                for ticker in batch_tickers:
                    try:
                        df = bars.df
                        if isinstance(df.index, pd.MultiIndex):
                            # 多symbol情况
                            ticker_data = df.xs(ticker, level='symbol')
                        else:
                            ticker_data = df

                        if not ticker_data.empty:
                            # 重命名列以匹配yfinance格式
                            ticker_data = ticker_data.rename(columns={
                                'open': 'Open',
                                'high': 'High',
                                'low': 'Low',
                                'close': 'Close',
                                'volume': 'Volume',
                                'trade_count': 'Trade_Count',
                                'vwap': 'VWAP'
                            })

                            # Alpaca没有复权价格,使用Close作为Adj Close
                            ticker_data['Adj Close'] = ticker_data['Close']

                            results[ticker] = ticker_data
                        else:
                            failed.append(ticker)

                    except KeyError:
                        failed.append(ticker)
                        continue

            except Exception as e:
                logger.warning(f"批次 {i//batch_size + 1} 下载失败: {e}")
                failed.extend(batch_tickers)
                continue

        logger.info(f"Alpaca下载完成: 成功 {len(results)}, 失败 {len(failed)}")
        if failed and len(failed) <= 10:
            logger.warning(f"失败列表: {failed}")
        elif failed:
            logger.warning(f"失败数量: {len(failed)}")

        return results


if __name__ == '__main__':
    # 测试
    from data.universe import get_sp500_tickers

    # 测试下载少量数据
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']
    fetcher = YFinanceFetcher(max_workers=5)
    results = fetcher.fetch(test_tickers, '2023-01-01', '2023-12-31')

    for ticker, df in results.items():
        print(f"\n{ticker}: {len(df)} 行")
        print(f"列名: {df.columns.tolist()}")
        print(df.head())
