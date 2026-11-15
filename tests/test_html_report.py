"""
[INPUT]: visualization/html_report.py, visualization/report_template.html
[OUTPUT]: 网页版报告的回归测试
[POS]: 锁定三件事: (1) 网页上的结论跟着数字变; (2) 策略颜色跟着策略走, 不跟着排名走;
       (3) 生成的网页是单文件、不依赖外部资源, 数据能被浏览器正确解析

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import json
import re

import pandas as pd
import pytest

from visualization import html_report


def _backtest(monthly_returns: list) -> dict:
    dates = pd.date_range("2021-01-31", periods=len(monthly_returns), freq="ME")
    returns = pd.Series(monthly_returns, index=dates)
    nav = (1 + returns).cumprod()
    return {"nav": nav, "nav_no_cost": nav * 1.001}


def _inputs(net_returns: dict, p_values: dict, betas: dict = None) -> dict:
    """按给定的年化净收益 / p值 / Beta 造一套 build_report_data 的入参"""
    betas = betas or {}
    performance = pd.DataFrame([
        {
            "factor": name, "annual_return_net": net, "annual_return_gross": net + 0.004,
            "annual_vol": 0.08, "sharpe": net * 10, "max_drawdown": -0.2,
            "avg_turnover": 0.16, "cost_drag_annual": -0.004,
        }
        for name, net in net_returns.items()
    ]).sort_values("sharpe", ascending=False).reset_index(drop=True)
    robustness = pd.DataFrame([
        {"test_type": "子样本", "parameter": "period_1_2016-01_2020-01", "annual_return": -0.04, "sharpe": -0.4, "max_drawdown": -0.2},
        {"test_type": "子样本", "parameter": "period_2_2020-01_2026-02", "annual_return": -0.03, "sharpe": -0.3, "max_drawdown": -0.3},
        {"test_type": "成本敏感性", "parameter": "10 bps", "annual_return": -0.028, "sharpe": -0.27, "max_drawdown": -0.34},
        {"test_type": "成本敏感性", "parameter": "20 bps", "annual_return": -0.030, "sharpe": -0.29, "max_drawdown": -0.35},
        {"test_type": "分位数敏感性", "parameter": "进入10% / 退出15%", "annual_return": -0.042, "sharpe": -0.26, "max_drawdown": -0.44},
    ])
    return dict(
        backtest_results={name: _backtest([-0.10, 0.02, 0.01]) for name in net_returns},
        df_performance=performance,
        significance_results={
            name: {"returns": {"mean": net / 12, "n": 120, "nw_t_stat": -1.0, "nw_p_value": p_values[name]}}
            for name, net in net_returns.items()
        },
        exposure_full_sample={
            name: {"beta": betas.get(name, 0.02), "alpha": 0.0001, "r_squared": 0.05, "correlation": 0.1}
            for name in net_returns
        },
        df_robustness=robustness,
        ic_results={},
        metadata={
            "run_time": "2026-01-01 00:00:00", "git_commit": "abc1234",
            "sample_period": {"start": "2015-02-28", "end": "2026-01-31", "n_months": 132},
            "backtest_config": {"cost_bps": 20.0, "rebalance_freq": "2monthly", "min_holding_periods": 12,
                                "entry_quantile": 0.25, "exit_quantile": 0.3},
        },
    )


ALL_NEGATIVE = _inputs(
    {"Momentum": -0.03, "Trend": -0.01, "LowVolatility": -0.10},
    {"Momentum": 0.35, "Trend": 0.66, "LowVolatility": 0.01},
    betas={"LowVolatility": -0.5},
)


def test_verdict_follows_the_numbers():
    """全负 → 标题说「全部是负收益」; 有正但不显著 → 标题说「不显著」"""
    data = html_report.build_report_data(**ALL_NEGATIVE)
    assert data["verdict"]["level"] == "none"
    assert data["verdict"]["title"] == "3 个策略扣除交易成本后全部是负收益"
    assert data["tiles"][0]["value"] == "0 / 3"

    mixed = _inputs({"Momentum": 0.02, "Trend": -0.01}, {"Momentum": 0.40, "Trend": 0.60})
    data = html_report.build_report_data(**mixed)
    assert data["verdict"]["level"] == "weak"
    assert "有 1 个为正收益，但统计上不显著" in data["verdict"]["title"]
    assert data["tiles"][0]["value"] == "1 / 2"


def test_series_color_follows_the_strategy_not_its_rank():
    """排名变了, 每个策略的颜色槽位不变"""
    first = html_report.build_report_data(**ALL_NEGATIVE)
    reordered = _inputs(
        {"Momentum": -0.01, "Trend": -0.10, "LowVolatility": -0.03},
        {"Momentum": 0.35, "Trend": 0.66, "LowVolatility": 0.01},
    )
    second = html_report.build_report_data(**reordered)

    slots = lambda data: {s["key"]: s["slot"] for s in data["strategies"]}
    assert [s["key"] for s in first["strategies"]] != [s["key"] for s in second["strategies"]]
    assert slots(first) == slots(second) == {"Momentum": 1, "Trend": 4, "LowVolatility": 3}


def test_nav_series_starts_from_one():
    """净值曲线前面补上起点 1.0, 第一期的亏损在图上和回撤里都看得见"""
    series = html_report.build_report_data(**ALL_NEGATIVE)["strategies"][0]["series"]

    assert series["dates"][:2] == ["2020-12", "2021-01"]
    assert series["nav_net"][0] == 1.0
    assert series["nav_net"][1] == pytest.approx(0.90)
    assert series["drawdown_net"][0] == 0.0
    assert series["drawdown_net"][1] == pytest.approx(-0.10)
    assert len(series["dates"]) == len(series["nav_net"]) == len(series["drawdown_gross"])


def test_exposure_and_significance_flags():
    """Beta 超标、显著性的标记由阈值判断得出"""
    data = html_report.build_report_data(**ALL_NEGATIVE)
    by_key = {s["key"]: s for s in data["strategies"]}

    assert by_key["LowVolatility"]["exposure"]["exceeds"] is True
    assert by_key["Momentum"]["exposure"]["exceeds"] is False
    assert by_key["LowVolatility"]["significance"]["verdict"] == "显著为负"
    assert by_key["Momentum"]["significance"]["verdict"] == "不显著"
    assert "1/3 个策略的 Beta 绝对值超过 0.1" in data["exposure_notes"][0]


def test_robustness_labels_are_readable():
    """子样本和分位数的标签转成好读的写法"""
    robustness = html_report.build_report_data(**ALL_NEGATIVE)["robustness"]

    assert [r["label"] for r in robustness["sub_sample"]] == ["2020-01 之前", "2020-01 起"]
    assert [r["label"] for r in robustness["quantile"]] == ["10% / 15%"]
    assert any("都是负的" in note for note in robustness["notes"])


def test_rendered_html_embeds_the_data_and_is_self_contained():
    """渲染结果: 占位符被替换、数据能原样解析回来、不引用任何外部资源"""
    data = html_report.build_report_data(**ALL_NEGATIVE)
    html = html_report.render_html(data)

    assert html_report.DATA_PLACEHOLDER not in html
    match = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', html, re.S)
    assert match is not None
    assert json.loads(match.group(1)) == json.loads(json.dumps(data))
    # 离线可看: 没有外链的脚本、样式、图片、字体
    assert re.search(r'(src|href)\s*=\s*["\']https?://', html) is None
    assert "@import" not in html and "url(http" not in html


def test_script_closing_tag_in_data_cannot_break_the_page():
    """数据里出现 </script> 时要被转义, 不能提前结束脚本标签"""
    data = html_report.build_report_data(**ALL_NEGATIVE)
    data["limitations"] = ["</script><script>alert(1)</script>"]
    html = html_report.render_html(data)

    assert "</script><script>alert(1)" not in html
    match = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', html, re.S)
    assert json.loads(match.group(1))["limitations"] == ["</script><script>alert(1)</script>"]


def test_nan_in_report_data_is_rejected():
    """数据里混进 NaN 时渲染要报错, 而不是写出浏览器解析不了的 JSON"""
    data = html_report.build_report_data(**ALL_NEGATIVE)
    data["strategies"][0]["sharpe"] = float("nan")

    with pytest.raises(ValueError):
        html_report.render_html(data)


def test_beta_hedge_section_is_optional_and_follows_the_table():
    """没有对冲对比表时网页数据里没有这一节; 有的话每个策略一行, 颜色槽位不变"""
    assert html_report.build_report_data(**ALL_NEGATIVE)["beta_hedge"] is None

    hedge = pd.DataFrame([{
        "factor": "LowVolatility", "start": "2015-08", "end": "2026-01", "ex_ante_beta_mean": -0.49,
        "beta_before": -0.50, "beta_after": -0.02,
        "annual_return_before": -0.10, "annual_return_after": -0.035,
        "sharpe_before": -0.77, "sharpe_after": -0.29,
        "max_drawdown_before": -0.70, "max_drawdown_after": -0.39,
        "mean_return_before": -0.008, "mean_return_after": -0.003,
        "nw_p_value_before": 0.01, "nw_p_value_after": 0.34,
    }])
    data = html_report.build_report_data(**ALL_NEGATIVE, df_hedge=hedge)

    row = data["beta_hedge"]["rows"][0]
    assert (row["key"], row["slot"], row["short_label"]) == ("LowVolatility", 3, "低波")
    assert (row["beta_before"], row["beta_after"]) == (-0.50, -0.02)
    assert any("对冲有效" in note for note in data["beta_hedge"]["notes"])
    assert "下一节" in data["exposure_notes"][1]
    html_report.render_html(data)  # 能正常渲染
