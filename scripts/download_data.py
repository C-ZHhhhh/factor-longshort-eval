"""
下载完整S&P 500历史数据的脚本

使用方法:
    python scripts/download_data.py [--start START_DATE] [--end END_DATE] [--no-cache]

示例:
    python scripts/download_data.py --start 2015-01-01
    python scripts/download_data.py --start 2015-01-01 --end 2023-12-31 --no-cache
    python scripts/download_data.py --add-benchmark-daily   # 只给已有缓存补上SPY日收益率

[INPUT]: yfinance (联网)
[OUTPUT]: data/cache/ 下的缓存文件
[POS]: 数据下载入口

[PROTOCOL]:
1. --add-benchmark-daily 只往最新的缓存里新增 'SPY_daily' 一个键, 不重新下载股票。
   Beta对冲需要它; 新下载的缓存自带, 只有旧缓存需要补。
2. 逻辑变更时同步更新此头部
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_cleaner import add_benchmark_daily_to_cache, get_clean_data
from data.data_loader import DataLoader
from data.universe import get_sp500_tickers
from utils.logger import get_logger
from utils.config import config
import pandas as pd

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='下载完整S&P 500历史数据')
    parser.add_argument(
        '--start',
        type=str,
        default='2015-01-01',
        help='开始日期 (默认: 2015-01-01)'
    )
    parser.add_argument(
        '--end',
        type=str,
        default=None,
        help='结束日期 (默认: 今天)'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='禁用缓存,强制重新下载'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='测试模式,仅下载10只股票'
    )

    parser.add_argument(
        '--add-benchmark-daily',
        action='store_true',
        help='只给最新的缓存补上SPY日收益率(Beta对冲需要), 不重新下载股票数据'
    )

    args = parser.parse_args()

    if args.add_benchmark_daily:
        cache_file = DataLoader().latest_cache_file()
        logger.info(f"给缓存补上SPY日收益率: {cache_file}")
        daily = add_benchmark_daily_to_cache(cache_file)
        logger.info(f"完成: {len(daily)} 个交易日 ({daily.index[0].date()} ~ {daily.index[-1].date()})")
        return

    logger.info("="*60)
    logger.info("开始下载S&P 500历史数据")
    logger.info("="*60)

    # 设置参数
    if args.test:
        tickers = get_sp500_tickers()[:10]
        logger.info(f"测试模式: 下载 {len(tickers)} 只股票")
        deduplicate = False  # 测试模式不去重
    else:
        tickers = None  # 让get_clean_data内部处理S&P 500
        logger.info(f"完整模式: 下载完整S&P 500 (将自动去重)")
        deduplicate = True

    logger.info(f"日期区间: {args.start} ~ {args.end or '今天'}")
    logger.info(f"缓存: {'禁用' if args.no_cache else '启用'}")
    logger.info(f"去重: {'启用' if deduplicate else '禁用'}")

    # 下载数据
    try:
        df_price, df_volume, df_return_daily, df_return_monthly = get_clean_data(
            tickers=tickers,
            start_date=args.start,
            end_date=args.end,
            use_cache=not args.no_cache,
            deduplicate=deduplicate
        )

        # 显示统计信息
        logger.info("="*60)
        logger.info("下载完成!")
        logger.info("="*60)
        logger.info(f"价格数据: {df_price.shape[0]} 日 × {df_price.shape[1]} 股票")
        logger.info(f"成交量数据: {df_volume.shape[0]} 日 × {df_volume.shape[1]} 股票")
        logger.info(f"日收益率: {df_return_daily.shape[0]} 日")
        logger.info(f"月收益率: {df_return_monthly.shape[0]} 月")

        # 数据质量报告
        logger.info("\n数据质量报告:")
        price_missing = df_price.isna().sum().sum()
        price_total = df_price.size
        logger.info(f"  价格数据缺失率: {price_missing/price_total:.2%}")

        return_missing = df_return_monthly.isna().sum().sum()
        return_total = df_return_monthly.size
        logger.info(f"  月收益率缺失率: {return_missing/return_total:.2%}")

        # 显示日期范围
        logger.info(f"\n日期范围:")
        logger.info(f"  价格数据: {df_price.index[0]} ~ {df_price.index[-1]}")
        logger.info(f"  月收益率: {df_return_monthly.index[0]} ~ {df_return_monthly.index[-1]}")

        # 显示样本股票统计
        logger.info(f"\n样本统计 (前5只股票):")
        for ticker in df_price.columns[:5]:
            valid_days = df_price[ticker].notna().sum()
            logger.info(f"  {ticker}: {valid_days}/{len(df_price)} 天有数据")

        logger.info("="*60)
        logger.info("数据已保存到缓存,后续可直接加载")
        logger.info("="*60)

        return 0

    except KeyboardInterrupt:
        logger.warning("\n下载被用户中断")
        return 1

    except Exception as e:
        logger.error(f"下载失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
