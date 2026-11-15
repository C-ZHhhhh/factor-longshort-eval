# backtest/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

回测引擎层,负责时间对齐、执行回测循环、计算绩效指标。系统核心。✅ 阶段5已完成。

## 边界

**输入**: 因子值、收益率、组合权重
**输出**: 净值曲线、绩效指标、持仓历史、换手率序列

## 约束

1. **防look-ahead**: 因子在t计算,必须shift(1)后用t+1收益
2. **交易成本**: cost = turnover × cost_bps / 10000 (默认20 bps)
3. **时间对齐**: 确保因子和收益的时间索引正确对齐
4. **净值更新**: nav_t = nav_t-1 × (1 + portfolio_return - transaction_cost)
5. **滞后只在time_aligner**: 权重之外其他"月末才知道"的量(如股票Beta)也要滞后一期,统一走`TimeAligner.lag_to_return_dates()`,其他模块不得自己shift
6. **对冲不偷看未来**: 第t月的对冲仓位只能用t-1月末及之前的数据;Beta窗口是事先定的常规值,不得拿回测结果去挑

## 成员清单

**__init__.py**: 包初始化文件。导出TimeAligner, TransactionCostModel, BacktestEngine, PerformanceMetrics。

**time_aligner.py**: 时间对齐模块(⭐ CRITICAL)。实现align_factor_and_return()和align_weights_and_return(),通过shift(1)防止look-ahead bias。确保因子t预测收益t+1。`lag_to_return_dates()`把其他月末已知的量(如股票Beta)滞后一期对到收益月份。

**engine.py**: 回测引擎(⭐ CRITICAL)。主回测循环,按月迭代计算组合收益,计算换手率,扣除交易成本,更新净值曲线。输出含/不含成本的两条净值曲线,以及`effective_weights`(每期实际生效的权重,非调仓期是延续下来的权重;`holdings_history`只是目标权重)。

**transaction.py**: 交易成本模型。根据换手率计算单边交易成本。cost = turnover × cost_bps / 10000。支持单期、序列、年化成本计算。

**beta_hedge.py**: Beta对冲。`rolling_stock_beta()`用过去252个交易日的日收益估计每只股票月末的Beta;`apply_market_hedge()`在回测结果上叠加市场基准仓位(对冲仓位=-组合Beta,每月更新,换手计入成本),返回与引擎结果同结构的dict;`restrict_to_dates()`把未对冲结果截到同一段时间以便比较。不改选股和权重。

**metrics.py**: 绩效指标计算器。计算总收益、年化收益、年化波动、Sharpe、Calmar、Sortino、最大回撤、胜率、盈亏比等指标。总收益/年化收益从收益率序列计算(prod(1+r)-1,期数=len(returns)),不能用nav[-1]/nav[0](nav[0]已含第一期收益,会漏算第一期)。模块级函数drawdown_series()是全系统回撤的唯一算法,历史高点包含初始净值1.0。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
