"""
[INPUT]: 清洗后的价格/成交量数据
[OUTPUT]: 因子值(月度横截面数据)
[POS]: 因子基类,定义统一接口

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseFactor(ABC):
    """因子计算基类

    所有因子必须继承此类并实现calculate()方法
    """

    def __init__(self, name: str):
        """
        初始化因子

        Args:
            name: 因子名称
        """
        self.name = name
        logger.info(f"初始化因子: {name}")

    @abstractmethod
    def calculate(
        self,
        df_price: pd.DataFrame,
        df_volume: Optional[pd.DataFrame] = None,
        df_return_daily: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算因子值

        Args:
            df_price: 价格数据 (日期 × 股票)
            df_volume: 成交量数据 (日期 × 股票), 可选
            df_return_daily: 日收益率数据 (日期 × 股票), 可选

        Returns:
            因子值 (月末日期 × 股票)
            - 行索引: 月末日期 (MonthEnd)
            - 列: 股票ticker
            - 值: 因子值(未标准化)
        """
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"
