"""
[INPUT]: 多个标准化后的因子值
[OUTPUT]: 合成因子
[POS]: 多因子合成模块

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class FactorCombiner:
    """多因子合成器

    将多个因子合成为一个综合因子
    """

    def __init__(self, method: str = 'equal_weight'):
        """
        初始化

        Args:
            method: 合成方法
                - 'equal_weight': 等权平均
                - 'weighted': 加权平均 (需要提供权重)
        """
        self.method = method
        logger.info(f"初始化因子合成器: method={method}")

    def combine(
        self,
        factors: List[pd.DataFrame],
        weights: Optional[List[float]] = None,
        factor_names: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        合成多个因子

        Args:
            factors: 因子列表 (每个因子是 月末日期 × 股票 的DataFrame)
            weights: 权重列表 (与factors对应), 仅method='weighted'时使用
            factor_names: 因子名称列表 (用于日志)

        Returns:
            合成后的因子值 (月末日期 × 股票)
        """
        if not factors:
            raise ValueError("因子列表不能为空")

        logger.info(f"开始合成 {len(factors)} 个因子...")

        if factor_names is None:
            factor_names = [f"Factor_{i+1}" for i in range(len(factors))]

        # 验证因子形状一致性
        shapes = [f.shape for f in factors]
        logger.info(f"因子形状: {dict(zip(factor_names, shapes))}")

        # 对齐所有因子的日期和股票
        # 取所有因子的交集日期
        common_dates = factors[0].index
        for factor in factors[1:]:
            common_dates = common_dates.intersection(factor.index)

        # 取所有因子的交集股票
        common_tickers = factors[0].columns
        for factor in factors[1:]:
            common_tickers = common_tickers.intersection(factor.columns)

        logger.info(f"对齐后: {len(common_dates)} 个日期 × {len(common_tickers)} 只股票")

        # 对齐所有因子
        aligned_factors = []
        for factor, name in zip(factors, factor_names):
            aligned = factor.loc[common_dates, common_tickers]
            aligned_factors.append(aligned)
            logger.info(f"  {name}: {aligned.shape}, 缺失率={aligned.isna().sum().sum() / aligned.size:.2%}")

        # 合成
        if self.method == 'equal_weight':
            # 等权平均
            df_combined = pd.concat(aligned_factors).groupby(level=0).mean()
            logger.info("使用等权平均合成")

        elif self.method == 'weighted':
            # 加权平均
            if weights is None:
                raise ValueError("method='weighted'时必须提供weights参数")

            if len(weights) != len(factors):
                raise ValueError(f"权重数量({len(weights)})与因子数量({len(factors)})不匹配")

            # 标准化权重
            weights = np.array(weights)
            weights = weights / weights.sum()
            logger.info(f"使用加权平均合成: {dict(zip(factor_names, weights))}")

            # 初始化合成因子
            df_combined = pd.DataFrame(0.0, index=common_dates, columns=common_tickers)

            # 加权求和
            for factor, weight, name in zip(aligned_factors, weights, factor_names):
                df_combined += factor * weight

        else:
            raise ValueError(f"不支持的合成方法: {self.method}")

        logger.info(f"合成完成: {df_combined.shape}")
        logger.info(f"合成因子缺失率: {df_combined.isna().sum().sum() / df_combined.size:.2%}")

        return df_combined

    def combine_dict(
        self,
        factor_dict: Dict[str, pd.DataFrame],
        weights: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        从字典合成因子

        Args:
            factor_dict: {因子名: 因子DataFrame} 字典
            weights: {因子名: 权重} 字典, 可选

        Returns:
            合成后的因子值
        """
        factor_names = list(factor_dict.keys())
        factors = list(factor_dict.values())

        if weights is not None:
            weight_list = [weights.get(name, 1.0) for name in factor_names]
        else:
            weight_list = None

        return self.combine(
            factors=factors,
            weights=weight_list,
            factor_names=factor_names
        )
