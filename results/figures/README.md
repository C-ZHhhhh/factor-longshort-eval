# Figures Directory

**交付版图表集合** | 更新时间: 2026-02-05

本目录包含7张核心交付图表，所有图表均基于最新results数据生成。

---

## 核心图表清单

| 文件名 | 说明 | 展示位置 |
|--------|------|----------|
| `fig_01_equity_gross_vs_net_momentum.png` | Momentum因子毛收益vs净收益曲线 | README.md, 03_results_snapshot.md |
| `fig_02_drawdown_momentum.png` | Momentum因子净回撤曲线 | - |
| `fig_03_cost_sensitivity_momentum.png` | 成本敏感性分析（10-50 bps vs CAGR） | README.md, 03_results_snapshot.md |
| `fig_04_subsample_bar_momentum.png` | 子样本CAGR/Sharpe对比（period_1 vs period_2） | - |
| `fig_05_exposure_alpha_beta.png` | 市场暴露：Alpha & Beta条形图 | README.md |
| `fig_06_significance_tstats.png` | 显著性检验：标准t vs Newey-West t统计量 | 03_results_snapshot.md |
| `fig_07_equity_gross_vs_net_composite.png` | Composite因子毛收益vs净收益曲线 | - |

---

## Archive

`archive/` 目录包含已归档的旧版图表：
- `drawdown_analysis.png` - 旧版回撤分析（已被fig_02替代）
- `equity_gross_vs_net.png` - 旧版净值对比（已被fig_01替代）
- `factor_correlation_heatmap.png` - 因子相关性热图
- `ic_timeseries.png` - IC时间序列图
- `nav_comparison.png` - 旧版净值对比

---

## 图表生成

所有图表由以下脚本生成：
- `scripts/generate_figures.py` - 生成fig_01至fig_06
- `scripts/generate_composite_figure.py` - 生成fig_07

重新生成：
```bash
venv/bin/python scripts/generate_figures.py
venv/bin/python scripts/generate_composite_figure.py
```

---

*自动生成 | 数据来源: results/*
