"""
回测引擎模块

提供时间对齐、回测循环、交易成本和绩效指标计算功能
"""

from backtest.time_aligner import TimeAligner
from backtest.transaction import TransactionCostModel
from backtest.engine import BacktestEngine
from backtest.metrics import PerformanceMetrics

__all__ = [
    'TimeAligner',
    'TransactionCostModel',
    'BacktestEngine',
    'PerformanceMetrics',
]
