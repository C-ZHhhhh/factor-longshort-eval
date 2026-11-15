"""
[INPUT]: None
[OUTPUT]: pytest公共配置 (项目根目录加入sys.path, 关闭loguru刷屏)
[POS]: tests/ 的公共入口, 所有测试文件自动加载

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from loguru import logger

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 业务代码每一步都打INFO日志, 测试时只保留警告以上
logger.remove()
logger.add(sys.stderr, level="WARNING")


@pytest.fixture
def daily_prices() -> pd.DataFrame:
    """30个月的日频价格, 8只股票, 各自有不同的固定日涨幅(可精确推算)"""
    dates = pd.bdate_range("2020-01-01", "2022-06-30")
    daily_growth = np.linspace(-0.0015, 0.0020, 8)  # S0跌得最多, S7涨得最多
    steps = np.arange(len(dates))[:, None]
    prices = 100.0 * (1.0 + daily_growth[None, :]) ** steps
    columns = [f"S{i}" for i in range(8)]
    return pd.DataFrame(prices, index=dates, columns=columns)
