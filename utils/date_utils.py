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
from typing import Optional, Union, List


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


def is_month_complete(
    last_data_date: Union[str, datetime, pd.Timestamp],
    requested_end: Optional[Union[str, datetime, pd.Timestamp]] = None
) -> bool:
    """
    判断最后一条数据所在的月份是否已经走完

    用途: 月中下载数据时, 最后一个月只有几个交易日, 不能当成完整的一个月来算月收益。

    判定为完整的条件(满足其一):
    1. 请求的结束日期(不含)已经到了下个月 —— 说明这个月的交易日都请求过了
    2. 最后一条数据之后, 本月已没有工作日(周一到周五) —— 剩下的只有周末

    不考虑节假日, 所以判断是保守的: 只会把"其实完整的月"误判为不完整
    (例如月末最后一个工作日恰好休市), 不会把不完整的月当成完整。

    Args:
        last_data_date: 最后一条数据的日期
        requested_end: 下载时请求的结束日期(不含当天, 与yfinance的end语义一致), 可选

    Returns:
        该月是否完整
    """
    last_data_date = pd.Timestamp(last_data_date).normalize()
    month_end = last_data_date + pd.offsets.MonthEnd(0)

    if requested_end is not None and pd.Timestamp(requested_end).normalize() > month_end:
        return True

    remaining_business_days = pd.bdate_range(
        last_data_date + pd.Timedelta(days=1), month_end
    )
    return len(remaining_business_days) == 0
