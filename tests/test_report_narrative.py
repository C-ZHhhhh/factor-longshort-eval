"""
[INPUT]: evaluation/report_narrative.py
[OUTPUT]: 评估报告文字结论的回归测试
[POS]: 防止"数字是负的, 文字却写着正收益"这类写死的结论再次出现:
       结论必须跟着数字变

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pandas as pd
import pytest

from evaluation import report_narrative as narrative


def _performance(net_returns: dict, gross_extra: float = 0.004) -> pd.DataFrame:
    """按给定的净年化收益造一张性能表, 毛收益 = 净收益 + gross_extra"""
    rows = [
        {
            "factor": name,
            "annual_return_net": net,
            "annual_return_gross": net + gross_extra,
            "sharpe": net * 10,
        }
        for name, net in net_returns.items()
    ]
    return pd.DataFrame(rows).sort_values("sharpe", ascending=False).reset_index(drop=True)


def _significance(stats: dict) -> dict:
    """stats: {因子: (月均收益, Newey-West p值)}"""
    return {
        name: {"returns": {"mean": mean, "t_stat": 0.0, "p_value": p, "nw_p_value": p}}
        for name, (mean, p) in stats.items()
    }


def _robustness(sub_sample_returns: list, cost_returns: dict) -> pd.DataFrame:
    rows = [
        {"test_type": "子样本", "parameter": f"period_{i}", "annual_return": r, "sharpe": r * 10}
        for i, r in enumerate(sub_sample_returns, 1)
    ]
    rows += [
        {"test_type": "成本敏感性", "parameter": f"{bps} bps", "annual_return": r, "sharpe": r * 10}
        for bps, r in cost_returns.items()
    ]
    return pd.DataFrame(rows)


ALL_NEGATIVE = _performance({"Momentum": -0.03, "Trend": -0.01, "LowVolatility": -0.10})
ALL_NEGATIVE_SIG = _significance(
    {"Momentum": (-0.002, 0.35), "Trend": (-0.001, 0.66), "LowVolatility": (-0.008, 0.01)}
)


def test_all_negative_returns_never_claim_a_positive_return():
    """全部为负时, 报告必须说"没有正收益", 不能出现"实现正收益"之类的说法"""
    text = narrative.describe_net_returns(ALL_NEGATIVE, ALL_NEGATIVE_SIG)

    assert "没有任何一个策略取得正收益" in text
    assert "实现小幅正收益" not in text
    assert "取得正收益**：" not in text
    assert "LowVolatility 的负收益在统计上显著" in text


def test_gross_negative_is_not_blamed_on_costs():
    """不扣成本也是负的 → 亏损主因不是成本"""
    text = narrative.describe_net_returns(ALL_NEGATIVE, ALL_NEGATIVE_SIG)

    assert "不扣成本也是负的" in text


def test_positive_but_insignificant_is_weak_evidence():
    """有正收益但不显著 → 弱证据, 不是"没有正收益"也不是"显著"""
    performance = _performance({"Momentum": 0.02, "Trend": -0.01})
    significance = _significance({"Momentum": (0.002, 0.40), "Trend": (-0.001, 0.60)})

    assert narrative.evidence_level(performance, significance) == "weak"
    text = narrative.describe_net_returns(performance, significance)
    assert "有 **1 个取得正收益**" in text
    assert "统计上不显著" in text
    assert "弱证据" in narrative.final_conclusion(performance, significance, None)


def test_evidence_levels_follow_the_numbers():
    """证据等级: 全负=none, 正且显著=supported"""
    assert narrative.evidence_level(ALL_NEGATIVE, ALL_NEGATIVE_SIG) == "none"
    assert "没有找到证据" in narrative.final_conclusion(ALL_NEGATIVE, ALL_NEGATIVE_SIG, None)

    performance = _performance({"Momentum": 0.05})
    significance = _significance({"Momentum": (0.004, 0.01)})
    assert narrative.evidence_level(performance, significance) == "supported"


def test_sub_sample_label_is_the_same_everywhere():
    """同一个 Sharpe 极差只有一种评价 (曾经一处写"稳定"一处写"差异较大")"""
    sub_samples = _robustness([-0.043, -0.034], {})  # Sharpe 极差 0.09
    text = narrative.describe_sub_samples(sub_samples)

    assert narrative.sharpe_stability_label(0.09) == "差异不大"
    assert "差异不大" in text and "差异较大" not in text
    assert "都是负的" in text


def test_cost_sign_flip_is_only_reported_when_it_happens():
    """收益本来就是负的 → 不能说"转为负值"; 真的由正转负才这么说"""
    always_negative = _robustness([], {10: -0.028, 20: -0.030, 30: -0.032})
    text = narrative.describe_cost_sensitivity(always_negative)
    assert "成本不是亏损的主因" in text
    assert "由正转负" not in text

    crossing = _robustness([], {10: 0.004, 20: 0.001, 30: -0.002})
    text = narrative.describe_cost_sensitivity(crossing)
    assert "在 30 bps 时**由正转负**" in text


def test_cost_drag_uses_the_actual_bps_range():
    """每10bps的拖累按表里实际的成本范围算, 不假设固定是40bps"""
    table = _robustness([], {10: -0.010, 30: -0.016})  # 20bps 跨度下降 0.6% → 每10bps 0.3%

    assert narrative.cost_drag_per_10bps(table) == pytest.approx(-0.003)


def test_robustness_conclusion_matches_the_signs():
    """子样本和各档成本全为负 → "稳定地为负"; 有正有负 → "稳健性有限"""
    consistent = _robustness([-0.04, -0.03], {10: -0.028, 20: -0.030})
    assert "稳定地为负" in narrative.describe_robustness(consistent)

    mixed = _robustness([0.04, -0.03], {10: 0.01, 20: 0.005})
    assert "有正有负" in narrative.describe_robustness(mixed)


def test_beta_within_threshold_is_not_called_excessive():
    """Beta 没超标时不能写"超过阈值"""
    low = {"Momentum": {"beta": 0.02, "alpha": 0.0001, "r_squared": 0.005}}
    high = {"Momentum": {"beta": -0.17, "alpha": 0.0001, "r_squared": 0.08}}

    assert "阈值以内" in narrative.describe_exposure_caveat(low)
    assert "超过 0.1 阈值" in narrative.describe_exposure_caveat(high)
    assert "Beta-Neutral" in narrative.final_conclusion(ALL_NEGATIVE, ALL_NEGATIVE_SIG, high)
    assert "Beta-Neutral" not in narrative.final_conclusion(ALL_NEGATIVE, ALL_NEGATIVE_SIG, low)
