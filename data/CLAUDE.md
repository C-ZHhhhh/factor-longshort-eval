# data/

> L2 文档 | 父级: [../CLAUDE.md](../CLAUDE.md) | 分形协议: 三层结构

## 地位

数据层,负责获取、验证、清洗美股S&P 500历史数据。系统的数据来源。

## 边界

**输入**: ticker列表、日期区间
**输出**: 清洗后的价格/成交量数据、日/月收益率数据

## 约束

1. **双数据源策略**: 同时使用yfinance和Alpaca,交叉验证后合并
2. **数据质量**: 剔除缺失率>30%的股票
3. **复权处理**: 必须使用Adj Close
4. **缓存机制**: 支持本地缓存,避免重复下载
5. **完整月份**: 月收益率的每一行必须对应一个走完的月份,不完整的最后一个月不得进入回测
6. **市场基准**: Beta/暴露分析用的基准是真实的SPY;缺失时必须在报告中写明用的是替代基准,不得仍标为SPY

## 成员清单

**__init__.py**: 包初始化文件

**universe.py**: S&P 500成分股管理,提供get_sp500_tickers()函数获取ticker列表。

**data_fetcher.py**: 双数据源获取器。包含YFinanceFetcher和AlpacaFetcher类,支持并行下载。

**data_validator.py**: 交叉验证模块(⭐ CRITICAL)。对比两个数据源,标记差异>1%的数据点,实现合并策略。

**data_cleaner.py**: 数据清洗模块。处理缺失值、计算收益率、剔除低质量股票。月收益率只保留走完的月份(月中下载时剔除不完整的最后一个月);get_clean_data同时下载市场基准SPY,以月收益率存入缓存的'SPY'键。

**data_loader.py**: 缓存加载器。读取data/cache下最新的clean_data_*.pkl,标准化键名(monthly_return/daily_return),'SPY'键(基准月收益率)原样透传。latest_cache_file()是"用哪个缓存文件"的唯一入口,脚本不得写死clean_data_<日期>_<数量>.pkl文件名。

⚡触发器: 一旦本文件夹增删文件或架构逻辑调整,请立即重写此文档。
