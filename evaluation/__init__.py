"""
评估层 (Evaluation Layer)

[INPUT]:
- 因子数据 (DataFrame): 月度横截面因子值
- 收益率数据 (DataFrame): 月度股票收益率
- 回测结果 (dict): 净值、权重、持仓等

[OUTPUT]:
- IC/IR指标 (dict): IC序列、IR、IC均值等
- 暴露分析 (dict): 市场beta、行业暴露等
- 归因分析 (dict): 收益来源拆解
- 稳健性测试 (DataFrame): 子样本和参数敏感性结果

[POS]:
系统评估层，用于评估因子质量、策略表现和稳健性

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查 evaluation/CLAUDE.md
"""

from .ic_analysis import ICAnalyzer
from .exposure_check import ExposureChecker
from .attribution import AttributionAnalyzer
from .robustness import RobustnessTest
from .multi_factor_comparison import MultiFactorComparator
from .comprehensive_report import ComprehensiveReportGenerator

__all__ = [
    'ICAnalyzer',
    'ExposureChecker',
    'AttributionAnalyzer',
    'RobustnessTest',
    'MultiFactorComparator',
    'ComprehensiveReportGenerator'
]
