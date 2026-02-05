"""
[INPUT]: 日期字符串或日期对象
[OUTPUT]: 标准化的日期对象和日期序列
[POS]: 日期处理工具集,提供日期转换、序列生成等功能

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
from datetime import datetime
from typing import Union, List


def parse_date(date: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
    """
    解析日期为pd.Timestamp

    Args:
        date: 日期字符串、datetime对象或Timestamp对象

    Returns:
        pd.Timestamp对象
    """
    if isinstance(date, pd.Timestamp):
        return date
    elif isinstance(date, datetime):
        return pd.Timestamp(date)
    elif isinstance(date, str):
        return pd.to_datetime(date)
    else:
        raise ValueError(f"无法解析日期: {date}")


def get_month_end_dates(start_date: str, end_date: str) -> List[pd.Timestamp]:
    """
    获取指定区间的月末日期序列

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        月末日期列表
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    # 生成月度频率的日期序列
    dates = pd.date_range(start=start, end=end, freq='ME')  # ME = Month End

    return dates.tolist()


def get_trading_days(start_date: str, end_date: str) -> List[pd.Timestamp]:
    """
    获取指定区间的交易日序列(使用美国市场日历)

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        交易日列表
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    # 生成工作日序列(排除周末)
    dates = pd.bdate_range(start=start, end=end, freq='B')

    # TODO: 可以进一步集成pandas_market_calendars来排除美国假期
    return dates.tolist()


def shift_month(date: Union[str, pd.Timestamp], months: int) -> pd.Timestamp:
    """
    将日期向前或向后移动N个月

    Args:
        date: 基准日期
        months: 移动月数(正数向后,负数向前)

    Returns:
        移动后的日期
    """
    date = parse_date(date)
    return date + pd.DateOffset(months=months)


def get_month_start_end(date: Union[str, pd.Timestamp]) -> tuple:
    """
    获取指定日期所在月的起始和结束日期

    Args:
        date: 日期

    Returns:
        (month_start, month_end) 元组
    """
    date = parse_date(date)
    month_start = date.replace(day=1)
    month_end = (month_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)

    return month_start, month_end
