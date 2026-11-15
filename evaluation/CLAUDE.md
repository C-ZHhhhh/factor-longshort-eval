# evaluation/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

评估层,负责因子有效性分析(IC/IR)、暴露检查、稳健性测试。

## 边界

**输入**: 因子值、收益率、回测结果
**输出**: IC时间序列、IR统计量、暴露报告、稳健性对比表

## 约束

1. **IC计算**: 使用Spearman秩相关,每月独立计算
2. **子样本测试**: 至少2个子样本验证
3. **参数敏感性**: 测试不同成本、分位数的影响。`test_parameter_sensitivity` 对参数网格做笛卡尔积;需要成对变化的参数(退出阈值=进入阈值+5%)必须逐对运行,分位数敏感性每个进入阈值只有一行
4. **文字结论跟着数字走**: 报告里的定性结论("正收益""稳定""对成本敏感"等)一律由 `report_narrative.py` 根据数字判断后生成,不允许在报告模板里写死句子;同一个判断只定义一次,多处引用
5. **失败要报错**: 因子回测、参数组合、显著性检验失败时直接抛异常,不允许捕获后跳过或用NaN顶替(否则失败的那一行会从结果表里悄悄消失)

## 成员清单

**__init__.py**: 包初始化文件，导出所有评估类

**ic_analysis.py**: IC/IR分析模块。计算IC_t = Spearman(factor_t, return_t+1), IR = mean(IC)/std(IC)。

**exposure_check.py**: 暴露检查模块。计算组合beta、行业暴露等。

**attribution.py**: 归因分析模块。拆解收益来源（多头/空头/交易成本）。

**robustness.py**: 稳健性测试模块。子样本测试、参数敏感性分析。提供 `analyze_robustness()` 完整工作流。

**report_narrative.py**: 评估报告的文字结论。纯函数,输入性能表/显著性/稳健性/暴露数据,输出RQ1、RQ2、Caveat、最终结论等段落。由 `scripts/run_evaluation.py` 调用。

**performance_table_generator.py**: 性能表格生成器。输出 performance_table.csv/.md 和 drawdown_stats.csv。

**market_exposure_analyzer.py**: 市场暴露分析。对 SPY 回归得到 Beta/Alpha/R²,输出 exposure_summary.md。

**multi_factor_comparison.py**: 多因子对比模块。封装单因子回测、合成因子回测、对比表生成、报告生成。提供 `MultiFactorComparator` 类。支持5个因子：Momentum, Reversal, LowVolatility, Trend, Liquidity。

**comprehensive_report.py**: 综合评估报告生成器（新增）。整合多因子对比和稳健性测试，生成完整的评估报告。提供 `ComprehensiveReportGenerator` 类，一次运行输出完整评估。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
