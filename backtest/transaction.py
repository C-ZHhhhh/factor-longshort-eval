"""
[INPUT]: 换手率
[OUTPUT]: 交易成本
[POS]: 交易成本模型

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)


class TransactionCostModel:
    """交易成本模型

    根据换手率和成本参数计算交易成本
    """

    def __init__(self, cost_bps: float = 20.0):
        """
        初始化

        Args:
            cost_bps: 交易成本（基点, 1 bps = 0.01%）
                     - 单边成本
                     - 包含滑点、佣金、冲击成本等
                     - 常见取值：10-30 bps
        """
        self.cost_bps = cost_bps
        self.cost_rate = cost_bps / 10000.0  # 转换为小数
        logger.info(f"初始化交易成本模型: {cost_bps} bps = {self.cost_rate:.4%}")

    def calculate_cost(self, turnover: float) -> float:
        """
        计算单期交易成本

        成本 = 换手率 × 成本率

        Args:
            turnover: 换手率（0-2之间，0.5表示50%换手）

        Returns:
            交易成本（以收益率形式，负值）
        """
        cost = turnover * self.cost_rate
        return -cost  # 负值表示成本

    def calculate_cost_series(
        self,
        turnover_series: pd.Series
    ) -> pd.Series:
        """
        计算成本序列

        Args:
            turnover_series: 换手率序列

        Returns:
            成本序列（负值）
        """
        cost_series = turnover_series * self.cost_rate * -1
        logger.info(f"计算交易成本序列:")
        logger.info(f"  平均成本: {-cost_series.mean():.4%}")
        logger.info(f"  累计成本: {-cost_series.sum():.4%}")

        return cost_series

    def estimate_annual_cost(
        self,
        avg_monthly_turnover: float,
        periods_per_year: int = 12
    ) -> float:
        """
        估算年化交易成本

        Args:
            avg_monthly_turnover: 平均月换手率
            periods_per_year: 每年调仓次数

        Returns:
            年化交易成本
        """
        annual_cost = avg_monthly_turnover * self.cost_rate * periods_per_year
        logger.info(f"年化成本估算:")
        logger.info(f"  平均月换手率: {avg_monthly_turnover:.2%}")
        logger.info(f"  年化成本: {annual_cost:.2%}")

        return annual_cost

    def get_cost_breakdown(
        self,
        turnover: float,
        decomposition: dict = None
    ) -> dict:
        """
        成本分解

        Args:
            turnover: 总换手率
            decomposition: 换手率分解字典（可选）
                          {'entry': x, 'exit': y, 'adjust': z}

        Returns:
            成本分解字典
        """
        total_cost = self.calculate_cost(turnover)

        breakdown = {
            'total_cost': total_cost,
            'turnover': turnover,
            'cost_rate': self.cost_rate,
        }

        if decomposition:
            breakdown['entry_cost'] = self.calculate_cost(decomposition.get('entry', 0))
            breakdown['exit_cost'] = self.calculate_cost(decomposition.get('exit', 0))
            breakdown['adjust_cost'] = self.calculate_cost(decomposition.get('adjust', 0))

        return breakdown
