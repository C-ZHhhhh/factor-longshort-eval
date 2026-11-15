"""
[INPUT]: 原始权重
[OUTPUT]: 中性化后的权重
[POS]: 中性化模块 - 系统核心

[UPDATE 2026-11-15]:
- 删除 beta_neutral(): 它只是按 1/(beta+1) 调了一下单边权重, 并不能让组合 Beta 归零,
  而且从未接入回测、没有测试。Beta 对冲现在由 backtest/beta_hedge.py 完成
  (不改权重, 在组合之外加一份市场基准仓位)。

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
