"""
[INPUT]: 因子值、收益率数据
[OUTPUT]: 时间对齐后的因子值和收益率
[POS]: 时间对齐模块 - 系统生命线，防止look-ahead bias

[UPDATE 2026-11-15]:
- 新增 lag_to_return_dates(): 股票Beta这类"月末才知道"的量也从这里滞后一期,
  保证滞后只在本模块发生。

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class TimeAligner:
    """时间对齐器

    防止look-ahead bias的核心模块
    确保因子在t期计算，用于预测t+1期的收益
    """

    def __init__(self):
        logger.info("初始化时间对齐器")

    def align_factor_and_return(
        self,
        df_factor: pd.DataFrame,
        df_return: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        对齐因子和收益率的时间

        关键逻辑：
        - 因子在t期末计算（基于t期及之前的数据）
        - 因子值用于预测t+1期的收益
        - 实现：将因子shift(1)，使因子t对应收益t+1

        Args:
            df_factor: 因子值 (月末日期 × 股票)
            df_return: 收益率 (月末日期 × 股票)

        Returns:
            (df_factor_aligned, df_return_aligned)
            - df_factor_aligned: 对齐后的因子（第一期为NaN）
            - df_return_aligned: 对齐后的收益率
        """
        logger.info("开始时间对齐...")
        logger.info(f"原始因子: {df_factor.shape}, 日期范围: {df_factor.index[0]} ~ {df_factor.index[-1]}")
        logger.info(f"原始收益: {df_return.shape}, 日期范围: {df_return.index[0]} ~ {df_return.index[-1]}")

        # 关键步骤：将因子shift(1)
        # 这样因子t的值会对应到收益t+1的位置
        df_factor_shifted = df_factor.shift(1)

        # 取两者的交集日期
        common_dates = df_factor_shifted.index.intersection(df_return.index)
        logger.info(f"共同日期数: {len(common_dates)}")

        # 对齐
        df_factor_aligned = df_factor_shifted.loc[common_dates]
        df_return_aligned = df_return.loc[common_dates]

        # 移除第一期（因子为NaN）
        if len(df_factor_aligned) > 0:
            # 检查第一期是否全为NaN
            first_date = df_factor_aligned.index[0]
            if df_factor_aligned.loc[first_date].isna().all():
                df_factor_aligned = df_factor_aligned.iloc[1:]
                df_return_aligned = df_return_aligned.iloc[1:]
                logger.info(f"移除第一期（因子为NaN）")

        # 取股票交集
        common_tickers = df_factor_aligned.columns.intersection(df_return_aligned.columns)
        df_factor_aligned = df_factor_aligned[common_tickers]
        df_return_aligned = df_return_aligned[common_tickers]

        logger.info(f"对齐后: {df_factor_aligned.shape}")
        logger.info(f"  因子日期: {df_factor_aligned.index[0]} ~ {df_factor_aligned.index[-1]}")
        logger.info(f"  收益日期: {df_return_aligned.index[0]} ~ {df_return_aligned.index[-1]}")

        # 验证对齐
        self._verify_alignment(df_factor_aligned, df_return_aligned)

        logger.info("时间对齐完成")
        return df_factor_aligned, df_return_aligned

    def align_weights_and_return(
        self,
        df_weights: pd.DataFrame,
        df_return: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        对齐权重和收益率的时间

        权重在t期末计算（基于t期因子），用于t+1期交易
        因此需要shift(1)

        Args:
            df_weights: 权重 (月末日期 × 股票)
            df_return: 收益率 (月末日期 × 股票)

        Returns:
            (df_weights_aligned, df_return_aligned)
        """
        logger.info("对齐权重和收益...")

        # 权重shift(1)
        df_weights_shifted = df_weights.shift(1)

        # 取交集
        common_dates = df_weights_shifted.index.intersection(df_return.index)
        df_weights_aligned = df_weights_shifted.loc[common_dates]
        df_return_aligned = df_return.loc[common_dates]

        # 移除第一期
        if len(df_weights_aligned) > 0:
            first_date = df_weights_aligned.index[0]
            if df_weights_aligned.loc[first_date].isna().all():
                df_weights_aligned = df_weights_aligned.iloc[1:]
                df_return_aligned = df_return_aligned.iloc[1:]

        # 股票对齐
        common_tickers = df_weights_aligned.columns.intersection(df_return_aligned.columns)
        df_weights_aligned = df_weights_aligned[common_tickers]
        df_return_aligned = df_return_aligned[common_tickers]

        logger.info(f"对齐后: {df_weights_aligned.shape}")
        return df_weights_aligned, df_return_aligned

    def lag_to_return_dates(
        self,
        df_signal: pd.DataFrame,
        return_dates: pd.Index
    ) -> pd.DataFrame:
        """
        把"t月末已知的量"对到"t+1月的收益"上

        因子/权重之外, 其他只在月末才知道的量 (如每只股票的Beta) 也要滞后一期才能用,
        统一从这里走, 不在各模块里各自shift。

        Args:
            df_signal: 月末日期 × 股票, 第t行只用到了t月末及之前的数据
            return_dates: 收益所在的月份 (月末日期)

        Returns:
            与 return_dates 同索引; 第t行是 t-1 月末已知的值
        """
        months = df_signal.index.to_period('M')
        if len(months) > 1 and not ((months[1:] - months[:-1]).map(lambda d: d.n) == 1).all():
            # 中间缺月份时 shift(1) 会滞后不止一个月, 直接报错
            raise ValueError("df_signal 的月份必须连续, 否则shift(1)不等于滞后一个月")
        return df_signal.shift(1).reindex(return_dates)

    def _verify_alignment(
        self,
        df_factor_aligned: pd.DataFrame,
        df_return_aligned: pd.DataFrame
    ):
        """
        验证时间对齐的正确性

        检查：
        1. 日期索引完全一致
        2. 股票列完全一致
        3. 因子第一期不应全为NaN（已移除）
        """
        logger.info("验证时间对齐...")

        # 检查日期
        if not df_factor_aligned.index.equals(df_return_aligned.index):
            logger.warning("警告：因子和收益的日期索引不完全一致")

        # 检查股票
        if not df_factor_aligned.columns.equals(df_return_aligned.columns):
            logger.warning("警告：因子和收益的股票列不完全一致")

        # 检查第一期
        first_date = df_factor_aligned.index[0]
        first_factor_na_count = df_factor_aligned.loc[first_date].isna().sum()
        if first_factor_na_count == len(df_factor_aligned.columns):
            logger.error("错误：对齐后第一期因子仍全为NaN，可能时间对齐有问题")
        else:
            logger.info(f"✅ 第一期因子缺失数: {first_factor_na_count}/{len(df_factor_aligned.columns)}")

        logger.info("✅ 时间对齐验证通过")
