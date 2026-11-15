"""
[INPUT]: evaluation/multi_factor_comparison.py
[OUTPUT]: 多因子对比的回归测试 (因子回测失败时必须报错)
[POS]: 防止"某个因子跑失败, 只记一行日志, 然后从对比表里悄悄消失"再次出现

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import pytest

from evaluation.multi_factor_comparison import MultiFactorComparator


def test_failing_factor_stops_the_comparison(monkeypatch):
    """单因子回测抛异常 → 整个对比抛异常, 而不是返回一张少了一行的表"""
    comparator = MultiFactorComparator()

    def broken_backtest(factor_name, df_clean):
        raise RuntimeError(f"{factor_name} 回测失败")

    monkeypatch.setattr(comparator, "run_single_factor", broken_backtest)

    with pytest.raises(RuntimeError, match="Momentum 回测失败"):
        comparator.compare({}, factor_names=["Momentum"], include_composite=False)


def test_failing_composite_stops_the_comparison(monkeypatch):
    """合成因子回测抛异常 → 同样要抛出来"""
    comparator = MultiFactorComparator()

    monkeypatch.setattr(comparator, "run_single_factor", lambda name, data: {})

    def broken_composite(df_clean, factor_names):
        raise RuntimeError("合成因子回测失败")

    monkeypatch.setattr(comparator, "run_composite_factor", broken_composite)

    with pytest.raises(RuntimeError, match="合成因子回测失败"):
        comparator.compare({}, factor_names=["Momentum"], include_composite=True)
