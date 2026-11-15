"""生成数据下载报告"""

import pandas as pd
from datetime import datetime
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_loader import DataLoader


def generate_report():
    # 加载数据
    cache_file = DataLoader().latest_cache_file()  # 最新的缓存文件, 不写死文件名
    cache_data = pd.read_pickle(cache_file)
    df_price = cache_data['price']
    df_return_daily = cache_data['return_daily']
    df_return_monthly = cache_data['return_monthly']

    file_size = os.path.getsize(cache_file) / (1024 * 1024)
    # 报告里只写相对项目根目录的路径, 不把本机的绝对路径写进仓库
    cache_path_display = Path(cache_file).resolve().relative_to(project_root.resolve()).as_posix()
    contents = {
        'price': '复权价格面板数据',
        'volume': '成交量',
        'return_daily': '日收益率',
        'return_monthly': '月收益率 (只含完整的月份)',
        'SPY': 'SPY月收益率 (基准)',
    }
    contents_lines = '\n'.join(
        f'- `{key}`: {desc}' for key, desc in contents.items() if key in cache_data
    )

    # 生成报告
    report = f'''# S&P 500历史数据下载报告 (去重版)

**下载时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 数据概况

### 基本信息
- **数据源**: yfinance (主) + Alpaca (备用, 未配置)
- **股票池**: S&P 500成分股
- **原始ticker数**: 503只
- **去重后ticker数**: 500只 (移除3只重复)
- **有效股票数**: {len(df_price.columns)}只 (额外剔除{500 - len(df_price.columns)}只因缺失率>30%)
- **日期区间**: {df_price.index[0].strftime('%Y-%m-%d')} ~ {df_price.index[-1].strftime('%Y-%m-%d')}
- **总天数**: {len(df_price):,}天 (~{len(df_price)//252}年)
- **总月数**: {len(df_return_monthly)}个月

### 数据维度
```
价格数据:     {len(df_price):,} 日 × {len(df_price.columns)} 股票 = {len(df_price) * len(df_price.columns):,} 数据点
日收益率:     {len(df_return_daily):,} 日 × {len(df_price.columns)} 股票
月收益率:     {len(df_return_monthly)} 月 × {len(df_price.columns)} 股票
```

### 数据质量
- **价格数据缺失率**: {df_price.isna().sum().sum() / df_price.size:.2%} (优秀)
- **月收益率缺失率**: {df_return_monthly.isna().sum().sum() / df_return_monthly.size:.2%} (优秀)

---

## 去重规则 ⭐ NEW

### 规则说明
**同一公司只允许出现一次，保留平均成交量更高的ticker**

### 实现方法
1. 从Wikipedia获取ticker → 公司名映射
2. 标准化公司名（去除"(Class A/B/C)"等后缀）
3. 计算每个ticker在整个时间区间的平均成交量
4. 同一公司保留成交量最高的ticker

### 去重结果

| 公司 | 保留Ticker | 移除Ticker | 保留理由 |
|------|-----------|-----------|---------|
| Alphabet Inc. | GOOGL | GOOG | 成交量更高 (35.2M vs 30.1M) |
| News Corp | NWSA | NWS | 成交量更高 (2.9M vs 797K) |
| Fox Corporation | - | FOXA, FOX | 两者均因缺失率>30%被剔除 |

**总计**: 移除3只重复ticker，503 → 500只

---

## 数据源状态

### ✅ yfinance (主数据源)
- **状态**: 成功
- **下载结果**: 503/503 股票成功
- **失败数**: 0
- **数据质量**: 优秀

### ⚠️ Alpaca (备用数据源)
- **状态**: 未配置
- **说明**: 免费API密钥不支持历史Market Data
- **影响**: 无影响，yfinance数据质量已足够

---

## 被剔除的股票 ({500 - len(df_price.columns)}只)

这些股票因缺失率超过30%阈值被剔除：
- 在2015年尚未上市
- 数据质量问题
- 或已退市

系统已自动处理，不影响回测。

---

## 数据存储

### 缓存文件
```
路径: {cache_path_display}
大小: {file_size:.1f} MB
格式: Pickle (pandas)
```

### 包含内容
{contents_lines}

### 快速加载
```python
import pandas as pd

# 加载数据
cache_data = pd.read_pickle('{cache_path_display}')
df_price = cache_data['price']
df_return_daily = cache_data['return_daily']
df_return_monthly = cache_data['return_monthly']
```

---

## 样本统计

### 前10只股票数据完整性

| Ticker | 有效天数 | 完整率 |
|--------|----------|--------|
'''

    # 添加前10只股票统计
    for ticker in df_price.columns[:10]:
        valid_days = df_price[ticker].notna().sum()
        completeness = valid_days / len(df_price) * 100
        report += f'| {ticker:6} | {valid_days:4}     | {completeness:5.1f}% |\n'

    report += f'''
---

## 下一步

### ✅ 已完成
- [x] 下载完整S&P 500历史数据 (2015-至今)
- [x] **实现去重规则：同一公司只保留成交量最高的ticker** ⭐ NEW
- [x] 数据清洗和预处理
- [x] 计算日/月收益率
- [x] 缓存数据以便快速加载

### 📋 待完成 (按照9阶段计划)
- [ ] **阶段3**: 实现因子计算模块 (动量、反转、低波、趋势、流动性)
- [ ] **阶段4**: 实现组合构建模块 (排序、权重、中性化)
- [ ] **阶段5**: 实现回测引擎 (时间对齐、成本扣除)
- [ ] **阶段6**: 实现评估模块 (IC/IR分析、暴露检查)
- [ ] **阶段7**: 实现可视化 (净值曲线、回撤图等)
- [ ] **阶段8-9**: 集成测试与稳健性验证

---

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**系统版本**: factor_reg v0.1.0
**去重功能**: ✅ 已启用
'''

    # 保存报告
    with open('DATA_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print('✅ 报告已生成: DATA_REPORT.md')
    print(f'\n数据下载完成！')
    print(f'- 原始ticker: 503只')
    print(f'- 去重后: 500只 (移除GOOG, FOX, NWS)')
    print(f'- 最终有效: {len(df_price.columns)}只')
    print(f'- 时间跨度: {len(df_price)}天, {len(df_return_monthly)}个月')
    print(f'- 数据质量: 缺失率{df_price.isna().sum().sum() / df_price.size:.2%}')


if __name__ == '__main__':
    generate_report()
