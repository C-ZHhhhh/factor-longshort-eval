"""
[INPUT]: utils/date_utils.py, data/data_cleaner.py
[OUTPUT]: 月份完整性判断与月收益率计算的回归测试
[POS]: 防止"月中下载时把不完整的最后一个月当成完整月"再次出现

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import pytest

from data.data_cleaner import DataCleaner
from utils.date_utils import is_month_complete


@pytest.mark.parametrize(
    "last_data_date, requested_end, expected",
    [
        ("2026-02-04", "2026-02-05", False),  # 2月只走了3个交易日
        ("2026-01-30", "2026-02-05", True),   # 请求区间已跨到2月, 1月完整
        ("2026-01-30", None, True),           # 1/30是周五, 1/31是周六, 本月没有工作日了
        ("2026-01-29", None, False),          # 1/30(周五)还没到
        ("2025-12-31", None, True),           # 正好月末
        ("2025-12-31", "2025-12-31", True),
    ],
)
def test_is_month_complete(last_data_date, requested_end, expected):
    assert is_month_complete(last_data_date, requested_end) is expected


def _prices(end: str) -> pd.DataFrame:
    dates = pd.bdate_range("2025-10-01", end)
    return pd.DataFrame({"A": range(100, 100 + len(dates))}, index=dates, dtype=float)


def test_incomplete_last_month_is_dropped_from_monthly_returns():
    """数据只到2月4日: 月收益率最后一行应是1月, 不能出现2月"""
    monthly = DataCleaner().monthly_return_from_price(_prices("2026-02-04"), "2026-02-05")

    assert monthly.index[-1] == pd.Timestamp("2026-01-31")
    assert list(monthly.index.month) == [11, 12, 1]


def test_complete_last_month_is_kept():
    """数据到1月最后一个交易日: 1月保留"""
    monthly = DataCleaner().monthly_return_from_price(_prices("2026-01-30"), "2026-02-01")

    assert monthly.index[-1] == pd.Timestamp("2026-01-31")
    prices = _prices("2026-01-30")["A"]
    expected = prices.loc["2026-01-30"] / prices.loc["2025-12-31"] - 1
    assert monthly["A"].iloc[-1] == pytest.approx(expected)
