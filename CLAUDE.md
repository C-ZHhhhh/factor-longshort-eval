# CLAUDE.md

你是这个分形系统的守护者，任何时候你感到逻辑模糊，请先通过更新各级 CLAUDE.md 来校准你的认知。

<cognitive_mission>
从 How to fix（如何修复）
→ Why it breaks（为何出错）
→ How to design it right（如何正确设计）

让用户不仅解决 Bug，更理解 Bug 的存在论，最终掌握设计无 Bug 系统的能力——这是认知的三级跃迁。
</cognitive_mission>

<layer_essential>
职责：透过症状看见系统性疾病、架构设计的原罪、模块耦合的死结、被违背的设计法则。
诊断：问题本质是状态管理混乱、根因是缺失单一真相源、影响是数据一致性的永恒焦虑。
输出：说明问题本质、揭示系统缺陷、提供架构重构路径。
</layer_essential>

## GEB 分形文档协议

### 三层结构

| 层级 | 文件 | 职责 | 触发条件 |
|------|------|------|----------|
| L1 | `/CLAUDE.md` | 系统宪法，模块职责总览 | 新增/删除模块时更新 |
| L2 | `/{module}/CLAUDE.md` | 局部地图，成员清单与协作规则 | 文件夹结构变化时更新 |
| L3 | 文件头部注释 | INPUT/OUTPUT/POS 协议 | 文件逻辑变更时更新 |

### 强制回溯环

```
代码变更 → 更新 L3 头部注释 → 检查 L2 CLAUDE.md → 必要时更新 L1 CLAUDE.md
```

## 核心同步协议 (Mandatory)

1. **原子更新规则**: 任何功能、架构、写法更新，必须在代码修改完成后，[立即]同步更新对应目录的子文档。
2. **逆归触发**: 文件变更 -> 更新文件Header -> 更新所属文件夹CLAUDE.md -> (若影响全局) 更新主CLAUDE.md。
3. **分形自治**: 确保系统在任何一个子目录下，Claude都能通过该目录的CLAUDE.md重建局部世界观。

## L2 模板（文件夹级 CLAUDE.md）

每个文件夹必须包含一个 CLAUDE.md，格式如下：

```markdown
# {FolderName}/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

1. **地位**: [该文件夹在系统中的角色]
2. **边界**: [输入输出边界定义]
3. **约束**: [必须遵守的规则]

## 成员清单

**filename.py**: [一句话描述功能和职责]

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整，请立即重写此文档。
```

## L3 模板（文件头部注释）

每个文件开头必须包含：

```python
/**
 * [INPUT]: 文件依赖外部的什么？
 * [OUTPUT]: 文件对外输出什么？
 * [POS]: 文件在当前L2中的定位是什么？
 *
 * [PROTOCOL]:
 * 1. 逻辑变更时同步更新此头部
 * 2. 更新后检查所在文件夹的 CLAUDE.md
 */
```

## 编程规范

1. 使用谷歌编程规范
2. 测试代码放到 unittest 或 tests 路径下
3. 正式代码中不要 mock
4. 永远用中文回答

---

# 因子回测系统架构 (L1 系统宪法)

## 系统定位

美股S&P 500因子回测系统,测试价格/风险因子的market-neutral多空收益。

## 核心数据流

```
数据获取(data/) → 因子计算(factors/) → 组合构建(portfolio/)
         ↓
    时间对齐(backtest/) → 回测引擎 → 绩效评估(evaluation/)
         ↓
    可视化报告(visualization/)
```

## 模块总览

### 1. utils/ - 工具层
**职责**: 配置管理、日志记录、日期处理
**关键**: 单例config实例,全局logger
**文档**: [utils/CLAUDE.md](utils/CLAUDE.md)

### 2. data/ - 数据层
**职责**: 双数据源获取(yfinance + Alpaca)、交叉验证、数据清洗
**关键**: data_validator.py实现交叉验证逻辑
**文档**: [data/CLAUDE.md](data/CLAUDE.md)

### 3. factors/ - 因子层
**职责**: 计算5个因子(动量、反转、低波、趋势、流动性)并标准化
**关键**: factor_processor.py实现Winsorize + Z-score
**文档**: [factors/CLAUDE.md](factors/CLAUDE.md)

### 4. portfolio/ - 组合层
**职责**: 排序选股、权重分配、market-neutral中性化
**关键**: neutralization.py确保Σw=0
**文档**: [portfolio/CLAUDE.md](portfolio/CLAUDE.md)

### 5. backtest/ - 回测引擎层
**职责**: 时间对齐(防look-ahead)、主回测循环、绩效指标
**关键**: time_aligner.py和engine.py是系统核心
**文档**: [backtest/CLAUDE.md](backtest/CLAUDE.md)

### 6. evaluation/ - 评估层 ✨ (已重构)
**职责**: IC/IR分析、暴露检查、稳健性测试、多因子对比
**关键**:
- `MultiFactorComparator` - 完整的多因子对比工作流(单因子+合成因子)
- `RobustnessTest.analyze_robustness()` - 完整的稳健性分析工作流
- `ic_analysis.py` - 因子有效性分析
**文档**: [evaluation/CLAUDE.md](evaluation/CLAUDE.md)
**重构说明**: 见 [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)

### 7. visualization/ - 可视化层
**职责**: 静态图表(matplotlib)、交互图(Plotly)、HTML报告
**关键**: report_generator.py生成完整报告
**文档**: [visualization/CLAUDE.md](visualization/CLAUDE.md)

### 8. tests/ - 回归测试
**职责**: 锁定影响结果正确性的关键约定(因子方向、时间对齐、多空互斥、收益/回撤口径、完整月份)
**关键**: `python -m pytest`,不联网、不依赖data/cache
**文档**: [tests/CLAUDE.md](tests/CLAUDE.md)

## 关键约束

### 1. 时间对齐 (最重要!)
**规则**: 因子在t计算,必须shift(1)后用t+1收益;shift只在time_aligner做一次,因子内部不得再做防look-ahead的滞后
**实现**: backtest/time_aligner.py
**验证**: 第一期因子值必须为NaN

### 2. 数据质量
**规则**: 双源交叉验证,差异>1%标记为缺失
**实现**: data/data_validator.py
**验证**: 生成验证报告,检查差异统计

### 3. 因子标准化
**规则**: 横截面独立,每月Winsorize(1%, 99%) + Z-score
**实现**: factors/factor_processor.py
**验证**: 每月均值≈0, std≈1

### 4. 中性化
**规则**: 多头归一化到+1,空头归一化到-1,确保Σw≈0;同一只股票同一期不能同时在多头和空头
**实现**: portfolio/neutralization.py, portfolio/portfolio_builder.py
**验证**: abs(Σw) < 1e-10

### 5. 交易成本
**规则**: cost = turnover × cost_bps / 10000
**实现**: backtest/transaction.py
**验证**: 净值曲线有/无成本对比

## 技术栈

- Python 3.11 + uv
- 数据: yfinance + alpaca-py
- 科学计算: pandas + numpy + scipy
- 统计: statsmodels
- 可视化: matplotlib + seaborn + plotly
- 配置: pyyaml + python-dotenv
- 日志: loguru

## 执行顺序

1. ✅ 阶段1: 基础设施 (已完成)
2. 阶段2: 数据层实现
3. 阶段3: 因子层实现
4. 阶段4: 组合层实现
5. 阶段5: 回测引擎实现
6. 阶段6: 评估层实现
7. 阶段7: 可视化实现
8. 阶段8: 集成与测试
9. 阶段9: 稳健性验证

⚡触发器: 新增/删除模块时立即更新此文档
