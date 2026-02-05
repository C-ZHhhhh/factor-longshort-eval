"""
[INPUT]: 原始权重
[OUTPUT]: 中性化后的权重
[POS]: 中性化模块 - 系统核心

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import numpy as np
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class Neutralizer:
    """中性化器

    实现market-neutral和beta-neutral
    """

    def __init__(self, tolerance: float = 1e-10):
        """
        初始化

        Args:
            tolerance: 中性化验证容差
        """
        self.tolerance = tolerance
        logger.info(f"初始化中性化器: tolerance={tolerance}")

    def market_neutral(self, df_weights: pd.DataFrame) -> pd.DataFrame:
        """
        市场中性化

        确保每个横截面:
        - 多头权重和 = +1
        - 空头权重和 = -1
        - 总权重和 = 0

        Args:
            df_weights: 原始权重 (月末日期 × 股票)

        Returns:
            中性化后的权重
        """
        logger.info("开始market-neutral中性化...")

        df_neutral = df_weights.copy()

        for date in df_weights.index:
            weights = df_weights.loc[date]

            # 分离多空权重
            long_mask = weights > 0
            short_mask = weights < 0

            long_weights = weights[long_mask]
            short_weights = weights[short_mask]

            # 归一化
            if len(long_weights) > 0:
                long_sum = long_weights.sum()
                if abs(long_sum) > self.tolerance:
                    df_neutral.loc[date, long_mask] = long_weights / long_sum
                else:
                    logger.warning(f"日期 {date}: 多头权重和接近0")

            if len(short_weights) > 0:
                short_sum = short_weights.sum()
                if abs(short_sum) > self.tolerance:
                    df_neutral.loc[date, short_mask] = short_weights / abs(short_sum)
                else:
                    logger.warning(f"日期 {date}: 空头权重和接近0")

        # 验证中性化效果
        self._verify_neutralization(df_neutral)

        logger.info("market-neutral中性化完成")
        return df_neutral

    def beta_neutral(
        self,
        df_weights: pd.DataFrame,
        df_beta: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Beta中性化

        确保组合beta ≈ 0: Σ(w_i × β_i) ≈ 0

        Args:
            df_weights: 原始权重 (月末日期 × 股票)
            df_beta: 股票beta (月末日期 × 股票)

        Returns:
            beta中性化后的权重
        """
        logger.info("开始beta-neutral中性化...")

        # 先进行market-neutral
        df_neutral = self.market_neutral(df_weights)

        # 对每个月调整权重使得组合beta ≈ 0
        for date in df_neutral.index:
            weights = df_neutral.loc[date]
            betas = df_beta.loc[date]

            # 计算当前组合beta
            portfolio_beta = (weights * betas).sum()

            if abs(portfolio_beta) < self.tolerance:
                continue  # 已经中性

            # 简单调整：对多空头分别按beta调整
            # 这是一个简化实现，更复杂的实现需要优化算法
            long_mask = weights > 0
            short_mask = weights < 0

            if portfolio_beta > 0:
                # 组合beta为正，增加低beta多头，减少高beta多头
                long_betas = betas[long_mask]
                if len(long_betas) > 0:
                    # 反beta加权调整
                    adjustment = 1.0 / (long_betas + 1.0)
                    df_neutral.loc[date, long_mask] *= adjustment
                    # 重新归一化多头
                    df_neutral.loc[date, long_mask] /= df_neutral.loc[date, long_mask].sum()
            else:
                # 组合beta为负，增加低beta空头，减少高beta空头
                short_betas = betas[short_mask]
                if len(short_betas) > 0:
                    adjustment = 1.0 / (short_betas.abs() + 1.0)
                    df_neutral.loc[date, short_mask] *= adjustment
                    # 重新归一化空头
                    df_neutral.loc[date, short_mask] /= abs(df_neutral.loc[date, short_mask].sum())

        logger.info("beta-neutral中性化完成")
        return df_neutral

    def _verify_neutralization(self, df_weights: pd.DataFrame):
        """
        验证中性化效果

        检查:
        1. 每个月总权重和 ≈ 0
        2. 多头权重和 ≈ 1
        3. 空头权重和 ≈ -1
        """
        logger.info("验证中性化效果...")

        violations = []

        for date in df_weights.index:
            weights = df_weights.loc[date]

            # 总权重和
            total_weight = weights.sum()
            if abs(total_weight) > self.tolerance * 100:  # 放宽容差
                violations.append(f"{date}: 总权重和={total_weight:.6f}")

            # 多头权重和
            long_weight = weights[weights > 0].sum()
            if abs(long_weight - 1.0) > self.tolerance * 100:
                violations.append(f"{date}: 多头权重和={long_weight:.6f}")

            # 空头权重和
            short_weight = weights[weights < 0].sum()
            if abs(short_weight + 1.0) > self.tolerance * 100:
                violations.append(f"{date}: 空头权重和={short_weight:.6f}")

        if violations:
            logger.warning(f"发现 {len(violations)} 个中性化异常:")
            for v in violations[:5]:  # 只显示前5个
                logger.warning(f"  {v}")
            if len(violations) > 5:
                logger.warning(f"  ... 还有 {len(violations) - 5} 个异常")
        else:
            logger.info("✅ 中性化验证通过")

        # 显示样本统计
        sample_date = df_weights.index[len(df_weights) // 2]
        sample_weights = df_weights.loc[sample_date]
        logger.info(f"样本验证 ({sample_date}):")
        logger.info(f"  总权重和: {sample_weights.sum():.10f}")
        logger.info(f"  多头权重和: {sample_weights[sample_weights > 0].sum():.10f}")
        logger.info(f"  空头权重和: {sample_weights[sample_weights < 0].sum():.10f}")
