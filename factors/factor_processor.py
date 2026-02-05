"""
[INPUT]: 原始因子值
[OUTPUT]: 预处理后的因子值 (Winsorize + Z-score)
[POS]: 因子预处理模块 - 系统核心

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class FactorProcessor:
    """因子预处理器

    提供Winsorize去极值和Z-score标准化功能
    """

    def __init__(
        self,
        winsorize_limits: Tuple[float, float] = (0.01, 0.99),
        standardize: bool = True
    ):
        """
        初始化

        Args:
            winsorize_limits: Winsorize的分位数限制, 默认(1%, 99%)
            standardize: 是否进行Z-score标准化, 默认True
        """
        self.winsorize_limits = winsorize_limits
        self.standardize = standardize
        logger.info(f"初始化因子预处理器: Winsorize={winsorize_limits}, Standardize={standardize}")

    def winsorize(self, df_factor: pd.DataFrame) -> pd.DataFrame:
        """
        Winsorize去极值

        对每个横截面（每个月），将极端值压缩到指定分位数

        Args:
            df_factor: 因子值 (月末日期 × 股票)

        Returns:
            去极值后的因子值
        """
        logger.info(f"开始Winsorize去极值: {self.winsorize_limits}...")

        df_winsorized = df_factor.copy()

        # 横截面处理：对每个月独立处理
        for date in df_factor.index:
            values = df_factor.loc[date]

            # 计算分位数
            lower_q = values.quantile(self.winsorize_limits[0])
            upper_q = values.quantile(self.winsorize_limits[1])

            # Winsorize: 压缩极值到分位数边界
            df_winsorized.loc[date] = values.clip(lower=lower_q, upper=upper_q)

        logger.info("Winsorize完成")
        return df_winsorized

    def zscore_standardize(self, df_factor: pd.DataFrame) -> pd.DataFrame:
        """
        Z-score标准化

        对每个横截面（每个月），进行标准化: (x - μ) / σ

        Args:
            df_factor: 因子值 (月末日期 × 股票)

        Returns:
            标准化后的因子值
        """
        logger.info("开始Z-score标准化...")

        df_standardized = df_factor.copy()

        # 横截面处理：对每个月独立处理
        for date in df_factor.index:
            values = df_factor.loc[date]

            # Z-score: (x - mean) / std
            mean = values.mean()
            std = values.std()

            if std > 1e-10:  # 避免除以0
                df_standardized.loc[date] = (values - mean) / std
            else:
                logger.warning(f"日期 {date}: 标准差接近0，跳过标准化")
                df_standardized.loc[date] = 0.0

        logger.info("Z-score标准化完成")
        return df_standardized

    def process(self, df_factor: pd.DataFrame) -> pd.DataFrame:
        """
        完整预处理流程

        1. Winsorize去极值
        2. Z-score标准化 (如果启用)

        Args:
            df_factor: 原始因子值 (月末日期 × 股票)

        Returns:
            预处理后的因子值
        """
        logger.info(f"开始预处理因子: {df_factor.shape}")

        # 1. Winsorize
        df_processed = self.winsorize(df_factor)

        # 2. 标准化
        if self.standardize:
            df_processed = self.zscore_standardize(df_processed)

        # 验证标准化结果
        if self.standardize:
            sample_date = df_processed.index[len(df_processed) // 2]
            sample_values = df_processed.loc[sample_date].dropna()
            logger.info(f"标准化验证 ({sample_date}): "
                       f"均值={sample_values.mean():.6f}, "
                       f"标准差={sample_values.std():.6f}")

        logger.info("预处理完成")
        return df_processed
