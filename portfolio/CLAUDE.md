# portfolio/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

组合层,负责根据因子值构建多空组合,分配权重,实现market-neutral中性化。

## 边界

**输入**: 标准化后的因子值
**输出**: 中性化后的组合权重序列、换手率

## 约束

1. **分位数选股**: 默认Top 20% (多头) + Bottom 20% (空头)
2. **权重归一化**: 多头权重和=+1,空头权重和=-1
3. **中性化验证**: 必须满足 Σw ≈ 0

## 成员清单

**__init__.py**: 包初始化文件

**portfolio_builder.py**: 排序选股模块。根据因子值排序,选择Top/Bottom分位数股票。

**weighting.py**: 权重分配模块。支持等权、市值加权、风险平价等方法。

**neutralization.py**: 中性化模块(⭐ CRITICAL)。实现market_neutral()和beta_neutral()。

**rebalancer.py**: 换手率计算模块。计算TO = 0.5 × Σ|Δw|。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
