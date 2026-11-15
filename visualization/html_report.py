"""
网页版可视化报告

[INPUT]:
- backtest_results (dict): {策略名: 回测结果}, 需含 nav / nav_no_cost
- df_performance (DataFrame): 性能表 (performance_table_generator 的输出)
- significance_results (dict): {策略名: {'returns': {...}}}
- exposure_full_sample (dict): {策略名: {'beta', 'alpha', 'r_squared', 'correlation'}}
- df_robustness (DataFrame): 稳健性表 (test_type / parameter / annual_return / sharpe / max_drawdown)
- ic_results (dict): {因子名: {'ic_mean', 'ir', 'ic_positive_ratio', 't_statistic'}}
- metadata (dict): results/metadata.json 的内容

[OUTPUT]:
- build_report_data(): 报告要展示的全部数据和文字结论 (一个可以存成 JSON 的 dict)
- render_html(): 把上面的 dict 填进 report_template.html, 得到单文件网页
- write_report(): 写出 results/report_data.json 和 results/report.html

[POS]:
可视化层的网页报告。Python 只负责"准备数据 + 下结论", 画图由模板里的 JS 完成。
由 scripts/run_evaluation.py 在评估末尾调用; scripts/generate_html_report.py 可以只重新渲染。

[PROTOCOL]:
1. 网页里出现的每个数字、每句结论都来自 build_report_data() 的返回值, 模板里不写死任何结果。
2. 定性判断 (是否正收益、是否显著、Beta 是否超标 ...) 复用 evaluation/report_narrative.py,
   不在这里另起一套阈值, 保证网页报告和 EVALUATION_REPORT.md 说法一致。
3. 策略的颜色槽位 (SERIES_SLOTS) 跟着策略名固定, 不随排名或显示与否变化。
4. 逻辑变更时同步更新此头部, 并检查 visualization/CLAUDE.md。
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from backtest.metrics import drawdown_series
from evaluation import report_narrative

TEMPLATE_PATH = Path(__file__).parent / 'report_template.html'
DATA_PLACEHOLDER = '__REPORT_DATA_JSON__'
REPORT_DATA_FILE = 'report_data.json'
REPORT_HTML_FILE = 'report.html'

# 中文名
FACTOR_LABELS = {
    'Momentum': '动量',
    'Reversal': '反转',
    'LowVolatility': '低波',
    'Trend': '趋势',
    'Liquidity': '流动性',
    'Composite': '合成',
}

# 颜色槽位: 跟着策略走, 不跟着排名走 (筛选或排序变化时颜色不变)
SERIES_SLOTS = {
    'Momentum': 1,
    'Reversal': 2,
    'LowVolatility': 3,
    'Trend': 4,
    'Composite': 5,
    'Liquidity': 6,
}

INITIAL_NAV = 1.0


# ============================================================
# 小工具
# ============================================================

def _plain(markdown_text: str) -> str:
    """去掉 Markdown 的加粗标记, 得到可以直接放进网页的纯文本。"""
    return markdown_text.replace('**', '').strip()


def _bullets(markdown_text: str) -> List[str]:
    """把 '- a\\n- b\\n' 这样的 Markdown 列表拆成纯文本列表。"""
    return [_plain(line[2:]) for line in markdown_text.splitlines() if line.startswith('- ')]


def _number(value) -> Optional[float]:
    """转成可以写进 JSON 的数字; NaN / None 一律变成 None。"""
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) or math.isinf(value) else value


def _display_name(strategy: str) -> str:
    label = FACTOR_LABELS.get(strategy)
    return f"{label} {strategy}" if label else strategy


def _pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


def _nav_payload(result: Dict) -> Dict:
    """
    净值和回撤序列。

    回测引擎的 nav[0] 是第一期结束后的净值, 这里在前面补上起点 (上个月末, 净值 1.0),
    这样曲线从 1.0 出发, 第一期的涨跌也看得见。
    """
    nav_net, nav_gross = result['nav'], result['nav_no_cost']
    start = nav_net.index[0] - pd.offsets.MonthEnd(1)
    dates = [start.strftime('%Y-%m')] + [d.strftime('%Y-%m') for d in nav_net.index]

    def with_start(series: pd.Series, first: float) -> List[Optional[float]]:
        return [first] + [_number(v) for v in series]

    return {
        'dates': dates,
        'nav_net': with_start(nav_net, INITIAL_NAV),
        'nav_gross': with_start(nav_gross, INITIAL_NAV),
        'drawdown_net': with_start(drawdown_series(nav_net), 0.0),
        'drawdown_gross': with_start(drawdown_series(nav_gross), 0.0),
    }


def _sub_sample_labels(parameters: List[str]) -> List[str]:
    """'period_1_2016-01_2020-01' → '2020-01 之前' 这样好读的标签。"""
    parsed = [re.match(r'period_\d+_(\d{4}-\d{2})_(\d{4}-\d{2})$', str(p)) for p in parameters]
    if not all(parsed) or len(parsed) < 2:
        return [str(p) for p in parameters]
    labels = []
    for i, match in enumerate(parsed):
        start, end = match.group(1), match.group(2)
        if i == 0:
            labels.append(f"{end} 之前")
        elif i == len(parsed) - 1:
            labels.append(f"{start} 起")
        else:
            labels.append(f"{start} ~ {end}")
    return labels


# ============================================================
# 文字结论
# ============================================================

def _significance_verdict(stats: Dict) -> str:
    if stats['nw_p_value'] >= report_narrative.SIGNIFICANCE_LEVEL:
        return '不显著'
    return '显著为正' if stats['mean'] > 0 else '显著为负'


def _build_verdict(df_performance: pd.DataFrame, significance_results: Dict) -> Dict:
    """页面顶部的总结论: 一句标题 + 几条要点。"""
    level = report_narrative.evidence_level(df_performance, significance_results)
    n_total = len(df_performance)
    positive = df_performance[df_performance['annual_return_net'] > 0]
    negative = df_performance[df_performance['annual_return_net'] <= 0]
    sig_positive, sig_negative, not_sig = report_narrative.classify_significance(significance_results)
    names = lambda factors: '、'.join(_display_name(f) for f in factors)

    if level == 'none':
        title = f"{n_total} 个策略扣除交易成本后全部是负收益"
    elif level == 'weak':
        title = f"{n_total} 个策略中有 {len(positive)} 个为正收益，但统计上不显著"
    else:
        winners = [f for f in positive['factor'] if f in set(sig_positive)]
        title = f"{names(winners)} 扣成本后为正收益，且统计上显著"

    points = []
    gross_negative = df_performance[df_performance['annual_return_gross'] <= 0]
    if len(negative) > 0:
        if len(gross_negative) == len(negative):
            points.append("亏损的策略不扣成本也是负的，所以主因不是交易成本，而是因子在这段样本里没有选对股票。")
        elif len(gross_negative) == 0:
            points.append("亏损的策略扣成本前都是正的，是交易成本把收益吃成了负数。")
        else:
            points.append("亏损的策略里，一部分不扣成本也是负的，另一部分是被交易成本吃成了负数。")

    if sig_positive:
        points.append(f"{names(sig_positive)} 的月度收益在统计上显著为正。")
    if sig_negative:
        points.append(f"{names(sig_negative)} 的负收益在统计上显著，不是偶然波动。")
    if not_sig:
        points.append(f"{names(not_sig)} 的收益和 0 没有显著差别。")

    best = df_performance.sort_values('sharpe', ascending=False).iloc[0]
    best_note = '，但仍是负收益' if best['annual_return_net'] <= 0 else ''
    points.append(
        f"Sharpe 最高的是 {_display_name(best['factor'])}"
        f"（年化 {_pct(best['annual_return_net'])}，Sharpe {best['sharpe']:.2f}）{best_note}。"
    )
    return {'level': level, 'title': title, 'points': points}


def _build_tiles(df_performance: pd.DataFrame) -> List[Dict]:
    """页面顶部的几个关键数字。"""
    n_total = len(df_performance)
    n_positive = int((df_performance['annual_return_net'] > 0).sum())
    best = df_performance.sort_values('sharpe', ascending=False).iloc[0]
    net = df_performance['annual_return_net']
    return [
        {
            'label': '扣成本后为正收益的策略',
            'value': f"{n_positive} / {n_total}",
            'note': '年化净收益大于 0 的个数',
        },
        {
            'label': '最高的 Sharpe',
            'value': f"{best['sharpe']:.2f}",
            'note': _display_name(best['factor']),
        },
        {
            'label': '年化净收益的范围',
            'value': f"{_pct(net.min())} ~ {_pct(net.max())}",
            'note': '最差到最好',
        },
        {
            'label': '平均成本拖累',
            'value': f"{_pct(df_performance['cost_drag_annual'].mean())} / 年",
            'note': f"平均换手率 {_pct(df_performance['avg_turnover'].mean())}",
        },
    ]


def _build_robustness_notes(df_robustness: pd.DataFrame) -> List[str]:
    sub_samples = df_robustness[df_robustness['test_type'] == '子样本']
    cost = df_robustness[df_robustness['test_type'] == '成本敏感性']
    quantile = df_robustness[df_robustness['test_type'] == '分位数敏感性']

    notes = []
    if len(sub_samples) >= 2:
        notes.append('子样本：' + _plain(report_narrative.describe_sub_samples(sub_samples)))
    if len(cost) >= 2:
        notes += ['成本：' + line for line in _bullets(report_narrative.describe_cost_sensitivity(cost))]
    if len(quantile) > 0:
        returns = quantile['annual_return']
        span = f"{_pct(returns.min())} ~ {_pct(returns.max())}"
        if (returns < 0).all():
            notes.append(f"分位数：{len(quantile)} 组进入/退出阈值的年化收益都是负的（{span}）。")
        elif (returns > 0).all():
            notes.append(f"分位数：{len(quantile)} 组进入/退出阈值的年化收益都是正的（{span}）。")
        else:
            notes.append(f"分位数：{len(quantile)} 组进入/退出阈值的年化收益有正有负（{span}），结论依赖具体参数。")
    return notes


def _build_exposure_notes(exposure_full_sample: Dict, benchmark_name: str) -> List[str]:
    threshold = report_narrative.BETA_THRESHOLD
    high = [name for name, stats in exposure_full_sample.items() if abs(stats['beta']) > threshold]
    notes = []
    if high:
        names = '、'.join(_display_name(n) for n in high)
        notes.append(
            f"{len(high)}/{len(exposure_full_sample)} 个策略的 Beta 绝对值超过 {threshold}（{names}），"
            f"它们的收益里混有 {benchmark_name} 涨跌的影响。"
        )
        notes.append(
            "组合只做到了资金中性（多空两边金额相等），资金中性不等于 Beta 中性；"
            "要分清收益来自因子还是来自大盘，需要额外做 Beta 对冲。"
        )
    else:
        notes.append(f"所有策略的 Beta 绝对值都在 {threshold} 以内，大盘涨跌对收益的影响很小。")
    return notes


LIMITATIONS = [
    "幸存者偏差：股票池是今天的 S&P 500 成分股，用它回测过去等于提前知道哪些公司能留在指数里。",
    "成交假设偏理想：假设能按算出信号的那个月末收盘价成交，没有计入滑点和冲击成本。",
    "子样本各自从空仓重新开始，所以两段子样本的结果不能直接拼成全样本的数字。",
    "样本只有大约十年、单一市场，统计上不足以对这些因子下定论。",
]


# ============================================================
# 组装数据
# ============================================================

def build_report_data(
    backtest_results: Dict,
    df_performance: pd.DataFrame,
    significance_results: Dict,
    exposure_full_sample: Dict,
    df_robustness: pd.DataFrame,
    ic_results: Dict,
    metadata: Dict,
    benchmark_name: str = 'SPY'
) -> Dict:
    """
    组装网页报告要展示的全部内容。

    Returns:
        可以直接 json.dumps 的 dict。模板里的 JS 只读这个 dict, 不做任何结论判断。
    """
    strategies = []
    for _, row in df_performance.iterrows():
        name = row['factor']
        sig = significance_results[name]['returns']
        exposure = exposure_full_sample[name]
        ic = ic_results.get(name)
        strategies.append({
            'key': name,
            'label': _display_name(name),
            'slot': SERIES_SLOTS[name],
            'annual_return_net': _number(row['annual_return_net']),
            'annual_return_gross': _number(row['annual_return_gross']),
            'annual_vol': _number(row['annual_vol']),
            'sharpe': _number(row['sharpe']),
            'max_drawdown': _number(row['max_drawdown']),
            'avg_turnover': _number(row['avg_turnover']),
            'cost_drag_annual': _number(row['cost_drag_annual']),
            'series': _nav_payload(backtest_results[name]),
            'significance': {
                'n': int(sig['n']),
                'nw_t_stat': _number(sig['nw_t_stat']),
                'nw_p_value': _number(sig['nw_p_value']),
                'verdict': _significance_verdict(sig),
            },
            'exposure': {
                'beta': _number(exposure['beta']),
                'alpha': _number(exposure['alpha']),
                'r_squared': _number(exposure['r_squared']),
                'exceeds': bool(abs(exposure['beta']) > report_narrative.BETA_THRESHOLD),
            },
            'ic': None if ic is None else {
                'ic_mean': _number(ic['ic_mean']),
                'ir': _number(ic['ir']),
                'ic_positive_ratio': _number(ic['ic_positive_ratio']),
                't_statistic': _number(ic['t_statistic']),
            },
        })

    def robustness_rows(test_type: str, labels: Optional[List[str]] = None) -> List[Dict]:
        table = df_robustness[df_robustness['test_type'] == test_type]
        labels = labels if labels is not None else [str(p) for p in table['parameter']]
        return [
            {
                'label': label,
                'annual_return': _number(row['annual_return']),
                'sharpe': _number(row['sharpe']),
                'max_drawdown': _number(row['max_drawdown']),
            }
            for label, (_, row) in zip(labels, table.iterrows())
        ]

    sub_sample_parameters = list(df_robustness.loc[df_robustness['test_type'] == '子样本', 'parameter'])
    quantile_parameters = list(df_robustness.loc[df_robustness['test_type'] == '分位数敏感性', 'parameter'])
    # '进入10% / 退出15%' → '10% / 15%' (面板标题里已经写明是 进入 / 退出)
    quantile_labels = [str(p).replace('进入', '').replace('退出', '') for p in quantile_parameters]

    config = metadata.get('backtest_config', {})
    sample = metadata.get('sample_period', {})
    return {
        'meta': {
            'generated_at': metadata.get('run_time'),
            'git_commit': metadata.get('git_commit'),
            'sample_start': sample.get('start'),
            'sample_end': sample.get('end'),
            'n_months': sample.get('n_months'),
            'config': config,
            'benchmark': benchmark_name,
        },
        'thresholds': {
            'beta': report_narrative.BETA_THRESHOLD,
            'significance': report_narrative.SIGNIFICANCE_LEVEL,
        },
        'verdict': _build_verdict(df_performance, significance_results),
        'tiles': _build_tiles(df_performance),
        'strategies': strategies,
        'robustness': {
            'factor': _display_name('Momentum'),
            'slot': SERIES_SLOTS['Momentum'],
            'sub_sample': robustness_rows('子样本', _sub_sample_labels(sub_sample_parameters)),
            'cost': robustness_rows('成本敏感性'),
            'quantile': robustness_rows('分位数敏感性', quantile_labels),
            'notes': _build_robustness_notes(df_robustness),
        },
        'exposure_notes': _build_exposure_notes(exposure_full_sample, benchmark_name),
        'limitations': LIMITATIONS,
    }


# ============================================================
# 渲染与输出
# ============================================================

def render_html(report_data: Dict) -> str:
    """把报告数据填进模板, 返回完整的单文件网页。"""
    template = TEMPLATE_PATH.read_text(encoding='utf-8')
    if template.count(DATA_PLACEHOLDER) != 1:
        raise ValueError(f"模板里应该正好有一个 {DATA_PLACEHOLDER} 占位符")
    # allow_nan=False: 数据里混进 NaN 时直接报错, 而不是写出浏览器解析不了的 JSON
    payload = json.dumps(report_data, ensure_ascii=False, allow_nan=False)
    # 防止数据里的 "</script>" 提前结束 <script> 标签
    payload = payload.replace('</', '<\\/')
    return template.replace(DATA_PLACEHOLDER, payload)


def write_report(report_data: Dict, output_dir: str = 'results') -> Path:
    """写出 report_data.json (数据) 和 report.html (网页), 返回网页路径。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / REPORT_DATA_FILE).write_text(
        json.dumps(report_data, ensure_ascii=False, allow_nan=False, indent=1),
        encoding='utf-8'
    )
    html_file = output_path / REPORT_HTML_FILE
    html_file.write_text(render_html(report_data), encoding='utf-8')
    return html_file
