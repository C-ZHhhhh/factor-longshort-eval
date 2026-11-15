"""
评估报告的文字结论

[INPUT]:
- df_performance (DataFrame): 性能表, 需含 factor / annual_return_net / annual_return_gross / sharpe
- significance_results (dict): {因子: {'returns': {'mean', 't_stat', 'p_value', 'nw_p_value'}}}
- df_robustness (DataFrame): 稳健性表, 需含 test_type / parameter / annual_return / sharpe
- exposure_full_sample (dict): {因子: {'beta', 'alpha', 'r_squared'}}

[OUTPUT]:
- 报告里"用文字下结论"的段落 (Markdown 字符串)

[POS]:
综合评估报告 (scripts/run_evaluation.py) 的文字结论层。只做一件事: 先看数字, 再决定说什么。

[PROTOCOL]:
1. 这里的每一句定性结论 ("正收益" "稳定" "对成本敏感" ...) 都必须由数字判断得出,
   不允许写死。写死的句子在数字变了以后会和表格自相矛盾。
2. 同一个判断只在一个函数里定义 (如 sharpe_stability_label), 报告多处引用同一个函数,
   避免同一个数字在不同章节得到相反的评价。
3. 函数都是纯函数 (不读文件、不打日志), 对应的回归测试在 tests/test_report_narrative.py。
4. 逻辑变更时同步更新此头部, 并检查 evaluation/CLAUDE.md。
"""

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

SIGNIFICANCE_LEVEL = 0.05       # 显著性水平
BETA_THRESHOLD = 0.1            # |Beta| 超过它算市场暴露超标
SHARPE_RANGE_THRESHOLD = 0.3    # 子样本 Sharpe 极差超过它算"差异较大"
NEAR_ZERO_ALPHA = 0.001         # 月度 Alpha 的绝对值小于它 (0.1%/月) 算"接近零"


# ============================================================
# 只定义一次的判断规则
# ============================================================

def sharpe_stability_label(sharpe_range: float) -> str:
    """子样本 Sharpe 极差 (最大 - 最小) 的评价。报告里所有地方都用这一个。"""
    return '差异较大' if sharpe_range >= SHARPE_RANGE_THRESHOLD else '差异不大'


def classify_significance(significance_results: Dict) -> Tuple[List[str], List[str], List[str]]:
    """
    按 Newey-West p 值和收益均值的符号把因子分成三组。

    Returns:
        (显著为正, 显著为负, 不显著)
    """
    sig_positive, sig_negative, not_sig = [], [], []
    for factor_name, sig_data in significance_results.items():
        if 'returns' not in sig_data:
            continue
        stats = sig_data['returns']
        if stats['nw_p_value'] < SIGNIFICANCE_LEVEL:
            (sig_positive if stats['mean'] > 0 else sig_negative).append(factor_name)
        else:
            not_sig.append(factor_name)
    return sig_positive, sig_negative, not_sig


def evidence_level(df_performance: pd.DataFrame, significance_results: Dict) -> str:
    """
    "因子能产生稳定超额收益"这个说法有多少证据。

    Returns:
        'supported': 至少一个因子净收益为正, 且统计显著
        'weak':      有因子净收益为正, 但都不显著
        'none':      没有任何因子净收益为正
    """
    positive = set(df_performance.loc[df_performance['annual_return_net'] > 0, 'factor'])
    if not positive:
        return 'none'
    sig_positive, _, _ = classify_significance(significance_results)
    return 'supported' if positive & set(sig_positive) else 'weak'


def _factor_line(row: pd.Series) -> str:
    return f"- **{row['factor']}**: 年化 {row['annual_return_net']:.2%}, Sharpe={row['sharpe']:.4f}"


def _cost_bps(parameter: str) -> float:
    """从 '30 bps' 这样的标签里取出数字 30。"""
    match = re.search(r'(\d+(?:\.\d+)?)', str(parameter))
    if match is None:
        raise ValueError(f"无法从成本标签里解析出bps: {parameter!r}")
    return float(match.group(1))


# ============================================================
# RQ1: 扣成本后有没有正收益
# ============================================================

def describe_net_returns(df_performance: pd.DataFrame, significance_results: Dict) -> str:
    """RQ1 的正文: 哪些因子扣成本后为正/为负, 统计上是否显著, 结论是什么。"""
    positive = df_performance[df_performance['annual_return_net'] > 0]
    negative = df_performance[df_performance['annual_return_net'] <= 0]
    n_total = len(df_performance)

    md = ''
    if len(positive) == 0:
        md += f"扣除交易成本后，**没有任何一个策略取得正收益**（{n_total} 个全部为负）：\n\n"
        md += '\n'.join(_factor_line(row) for _, row in negative.iterrows()) + '\n\n'
    else:
        md += f"扣除交易成本后，{n_total} 个策略中有 **{len(positive)} 个取得正收益**：\n\n"
        md += '\n'.join(_factor_line(row) for _, row in positive.iterrows()) + '\n\n'
        if len(negative) > 0:
            md += f"其余 {len(negative)} 个为负收益：\n\n"
            md += '\n'.join(_factor_line(row) for _, row in negative.iterrows()) + '\n\n'

    # 亏损是不是成本造成的: 看不扣成本的收益
    gross_negative = df_performance[df_performance['annual_return_gross'] <= 0]
    if len(negative) > 0:
        if len(gross_negative) == len(negative):
            md += ("这些负收益的策略**不扣成本也是负的**，所以亏损的主因不是交易成本，"
                   "而是因子本身在这段样本里没有选对股票。\n\n")
        elif len(gross_negative) == 0:
            md += "这些负收益的策略扣成本前都是正的，是交易成本把收益吃成了负数。\n\n"
        else:
            cost_killed = [f for f in negative['factor'] if f not in set(gross_negative['factor'])]
            md += (f"其中 {', '.join(cost_killed)} 扣成本前为正、扣成本后转负；"
                   f"其余的不扣成本也是负的。\n\n")

    md += ("**年化收益口径**: 全样本与子样本均采用 **CAGR (Compound Annual Growth Rate)** 计算，"
           "公式为 `(1 + total_return)^(1/n_years) - 1`，确保样本间可比性。"
           "显著性检验针对'月度净收益序列'的均值，与 CAGR 不同但相互印证。\n\n")

    # 统计检验
    sig_positive, sig_negative, not_sig = classify_significance(significance_results)
    md += "**统计检验** (见 [significance_summary.md](significance_summary.md)): "
    parts = []
    if sig_positive:
        parts.append(f"{len(sig_positive)} 个因子（{', '.join(sig_positive)}）的月度净收益**显著为正**")
    if sig_negative:
        parts.append(f"{len(sig_negative)} 个因子（{', '.join(sig_negative)}）的月度净收益**显著为负**")
    if not_sig:
        parts.append(f"{len(not_sig)} 个因子（{', '.join(not_sig)}）与 0 没有显著差别")
    md += f"Newey-West 检验（5% 显著性水平）显示，{'；'.join(parts)}。\n\n"

    # 结论: 由证据等级决定
    level = evidence_level(df_performance, significance_results)
    if level == 'supported':
        winners = [f for f in positive['factor'] if f in set(sig_positive)]
        md += (f"**结论**: {', '.join(winners)} 在样本期内扣成本后为正收益，且统计上显著。"
               "这只说明样本内的表现，不代表以后也成立。\n\n")
    elif level == 'weak':
        md += (f"**结论**: {', '.join(positive['factor'])} 扣成本后收益为正，但统计上不显著，"
               "可能只是运气，**不足以说明因子能稳定产生超额收益**。\n\n")
    else:
        md += "**结论**: 当前因子在样本期内**没有产生超额收益**，没有任何一个策略扣成本后为正。"
        if sig_negative:
            md += f"其中 {', '.join(sig_negative)} 的负收益在统计上显著。"
        md += '\n\n'
    return md


# ============================================================
# RQ2: 稳健性
# ============================================================

def describe_sub_samples(sub_sample_data: pd.DataFrame) -> str:
    """子样本一句话评价: 方向是否一致 + Sharpe 差异大小。"""
    sharpe_range = sub_sample_data['sharpe'].max() - sub_sample_data['sharpe'].min()
    returns = sub_sample_data['annual_return']
    if (returns < 0).all():
        direction = '各子样本的年化收益**都是负的**，方向一致'
    elif (returns > 0).all():
        direction = '各子样本的年化收益**都是正的**，方向一致'
    else:
        direction = '各子样本的年化收益**有正有负**，方向不一致'
    return f"{direction}；Sharpe 极差为 {sharpe_range:.4f}（{sharpe_stability_label(sharpe_range)}）。"


def cost_drag_per_10bps(cost_sens_data: pd.DataFrame) -> float:
    """成本每增加 10 bps, 年化收益变化多少 (负数表示下降)。按表里实际的成本范围算。"""
    bps = cost_sens_data['parameter'].map(_cost_bps)
    returns = cost_sens_data['annual_return']
    span = bps.max() - bps.min()
    if span <= 0:
        raise ValueError("成本敏感性至少需要两个不同的成本档位")
    return (returns[bps.idxmax()] - returns[bps.idxmin()]) / (span / 10)


def describe_cost_sensitivity(cost_sens_data: pd.DataFrame) -> str:
    """成本敏感性的评价: 每10bps拖累多少, 以及成本是否改变了收益的正负。"""
    bps = cost_sens_data['parameter'].map(_cost_bps)
    ordered = cost_sens_data.assign(_bps=bps).sort_values('_bps')
    lowest, highest = ordered.iloc[0], ordered.iloc[-1]
    drag = cost_drag_per_10bps(cost_sens_data)

    md = (f"- 成本从 {lowest['_bps']:.0f} bps 升到 {highest['_bps']:.0f} bps，"
          f"年化收益从 {lowest['annual_return']:.2%} 变为 {highest['annual_return']:.2%}，"
          f"每增加 10 bps 约下降 {abs(drag):.2%}\n")

    if lowest['annual_return'] <= 0:
        md += (f"- 成本最低的一档（{lowest['_bps']:.0f} bps）已经是负收益，"
               "所以**成本不是亏损的主因**，降低成本也无法让策略转正\n")
    elif highest['annual_return'] <= 0:
        first_negative = ordered[ordered['annual_return'] <= 0].iloc[0]
        md += (f"- 收益在 {first_negative['_bps']:.0f} bps 时**由正转负**，"
               "策略能否赚钱取决于实际交易成本\n")
    else:
        md += "- 在测试的成本范围内收益始终为正\n"
    return md


def describe_robustness(df_robustness: pd.DataFrame, cost_bps: float = 20.0) -> str:
    """RQ2 的正文: 子样本 + 成本敏感性 + 结论。"""
    sub_sample_data = df_robustness[df_robustness['test_type'] == '子样本']
    cost_sens_data = df_robustness[df_robustness['test_type'] == '成本敏感性']

    md = ''
    if len(sub_sample_data) >= 2:
        md += "**子样本稳健性** (见 [robustness_table.md](robustness_table.md)):\n\n"
        md += f"**说明**: 以下为 Momentum 因子在不同子样本的 **净收益表现 (扣除 {cost_bps:.0f}bps 成本)**\n\n"
        md += "| 时间段 | 年化收益 (净) | Sharpe (净) |\n"
        md += "|--------|--------------|-------------|\n"
        for _, row in sub_sample_data.iterrows():
            md += f"| {row['parameter']} | {row['annual_return']:.2%} | {row['sharpe']:.4f} |\n"
        md += f"\n{describe_sub_samples(sub_sample_data)}\n\n"

    if len(cost_sens_data) >= 2:
        md += "**成本敏感性**:\n\n"
        md += describe_cost_sensitivity(cost_sens_data) + '\n'

    # 结论: 看所有稳健性测试里收益的正负是否一致
    all_returns = pd.concat([sub_sample_data['annual_return'], cost_sens_data['annual_return']])
    if len(all_returns) == 0:
        return md + "**结论**: 没有稳健性测试结果。\n\n"
    if (all_returns < 0).all():
        md += ("**结论**: 结果是**稳定地为负**——换子样本、换成本假设，Momentum 的年化收益都是负的。"
               "这不是某一段时间或某一档成本碰巧不好。\n\n")
    elif (all_returns > 0).all():
        md += "**结论**: 换子样本、换成本假设，Momentum 的年化收益都是正的，结果对这些设定不敏感。\n\n"
    else:
        md += ("**结论**: 在不同子样本或成本假设下，Momentum 的年化收益**有正有负**，"
               "结论依赖具体设定，稳健性有限。\n\n")
    return md


# ============================================================
# Caveat 与最终结论
# ============================================================

def describe_exposure_caveat(exposure_full_sample: Optional[Dict]) -> str:
    """Momentum 的市场暴露说明。没有暴露数据时返回空字符串。"""
    if not exposure_full_sample or 'Momentum' not in exposure_full_sample:
        return ''
    stats = exposure_full_sample['Momentum']
    beta, alpha, r2 = stats['beta'], stats['alpha'], stats['r_squared']

    md = "当前策略为 **Dollar-Neutral (资金中性)** 但 **非 Beta-Neutral (市场中性)**。"
    if abs(beta) > BETA_THRESHOLD:
        md += (f"Momentum 因子的市场 Beta 为 **{beta:.4f}**（超过 {BETA_THRESHOLD} 阈值），"
               f"R²={r2:.2%}，即它的收益波动中约 {r2:.1%} 可以由大盘涨跌解释，不全是选股的结果。\n\n")
    else:
        md += (f"Momentum 因子的市场 Beta 为 **{beta:.4f}**（在 {BETA_THRESHOLD} 阈值以内），"
               f"R²={r2:.2%}，大盘涨跌对它的收益影响很小。\n\n")

    md += f"**OLS 回归结果**: 月度 Alpha={alpha:.4f} (见 [exposure_summary.md](exposure_summary.md))。"
    if abs(alpha) < NEAR_ZERO_ALPHA:
        md += "扣除市场影响后，Momentum 的纯因子收益 (Alpha) **接近零**。\n\n"
    elif alpha > 0:
        md += "扣除市场影响后，Momentum 的纯因子收益 (Alpha) 为正。\n\n"
    else:
        md += "扣除市场影响后，Momentum 的纯因子收益 (Alpha) **为负**。\n\n"
    return md


def final_conclusion(
    df_performance: pd.DataFrame,
    significance_results: Dict,
    exposure_full_sample: Optional[Dict]
) -> str:
    """最终结论: 证据等级 + 还需要做什么。"""
    level = evidence_level(df_performance, significance_results)
    if level == 'supported':
        md = ("**最终结论**: 样本内有因子扣成本后取得**统计显著的正收益**。"
              "但样本内显著不等于样本外有效，")
    elif level == 'weak':
        md = ("**最终结论**: 本研究仅提供 **弱证据 (weak evidence)**："
              "有因子扣成本后为正收益，但统计上不显著。")
    else:
        md = ("**最终结论**: 本研究**没有找到证据**支持这些因子在当前配置下能产生稳定超额收益："
              "所有策略扣成本后均为负收益。")

    high_beta = [
        name for name, stats in (exposure_full_sample or {}).items()
        if abs(stats['beta']) > BETA_THRESHOLD
    ]
    if high_beta:
        md += (f"另外 {', '.join(high_beta)} 的市场 Beta 超标，收益里混有大盘涨跌的影响，"
               "**需实施 Beta-Neutral 中性化**后才能判断纯粹的因子收益。")
    md += ("此外股票池用的是当前成分股（幸存者偏差），"
           "结论需要在历史成分股、更长样本期和其他市场上进一步验证。\n\n")
    return md
