"""
显著性检验的小工具

[INPUT]: 月度收益率序列
[OUTPUT]: Newey-West t 统计量和 p 值
[POS]: 评估层里"收益均值是否显著不为 0"的统一算法。正式评估和 Beta 对冲对比都用这一个,
       保证两处的显著性口径一致。

[PROTOCOL]:
1. 算不出来就报错, 不返回 NaN (NaN 会被下游的结论当成"不显著")
2. 逻辑变更时同步更新此头部, 并检查 evaluation/CLAUDE.md
"""

from typing import Tuple

import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS

NEWEY_WEST_MAX_LAGS = 6  # 约半年


def newey_west_mean_test(returns: pd.Series, maxlags: int = NEWEY_WEST_MAX_LAGS) -> Tuple[float, float]:
    """
    检验收益率均值是否为 0 (Newey-West, 考虑自相关和异方差)

    做法: 把收益率对常数项回归, 用 HAC 标准误。

    Returns:
        (t 统计量, p 值)
    """
    y = np.asarray(returns, dtype=float)
    if len(y) <= maxlags + 1 or np.isnan(y).any():
        raise ValueError(f"Newey-West 检验需要多于 {maxlags + 1} 个无缺失的观测, 当前 {len(y)} 个")
    model = OLS(y, np.ones((len(y), 1))).fit(cov_type='HAC', cov_kwds={'maxlags': maxlags})
    return float(model.tvalues[0]), float(model.pvalues[0])
