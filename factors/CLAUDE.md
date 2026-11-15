# factors/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

因子层,负责计算5个因子(动量、反转、低波、趋势、流动性)并进行预处理。

## 边界

**输入**: 清洗后的价格/成交量数据
**输出**: 标准化后的因子值(月度横截面)

## 约束

1. **横截面标准化**: 每月独立进行Winsorize + Z-score
2. **缺失值处理**: 缺失值的股票不参与排序(标记为NaN)
3. **因子定义**: 严格按照学术定义实现
4. **时间约定**: 索引t的因子值只能用到t月末及之前的数据;因子内部不做防look-ahead的shift,统一由backtest/time_aligner.py把因子t对齐到收益t+1

## 成员清单

**__init__.py**: 包初始化文件

**base_factor.py**: 因子基类,定义统一接口calculate()。

**momentum.py**: 动量因子 - (P_t-1m / P_t-12m) - 1 (近价在分子,过去涨得多→因子值高)

**reversal.py**: 短期反转因子 - -R_t (因子内部不shift,滞后统一由time_aligner处理)

**low_volatility.py**: 低波因子 - -σ(日收益, 3个月)

**trend.py**: 趋势因子 - P_t / MA200(P_t) - 1

**liquidity.py**: 流动性因子 - 成交额或换手率

**factor_processor.py**: 因子预处理(⭐ CRITICAL)。提供winsorize()和standardize()方法。

**factor_combiner.py**: 多因子合成。平均多个因子的Z-score值。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
