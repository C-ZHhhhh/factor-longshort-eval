# 配置Alpaca API（可选）

## 重要说明

⚠️ **Alpaca配置是可选的！** 系统可以完全使用yfinance作为单一数据源正常运行。

## 为什么使用双数据源？

本系统支持**双数据源交叉验证**策略：
- **主数据源**: yfinance（免费，无需配置）
- **备用数据源**: Alpaca（免费，需注册）

双数据源的好处：
1. 交叉验证数据质量，检测异常
2. 互相填补缺失值
3. 提高回测可靠性

## 快速开始（不使用Alpaca）

如果你选择只使用yfinance，什么都不需要做！系统会自动跳过Alpaca：

```bash
# 直接下载数据即可
python scripts/download_data.py --start 2015-01-01
```

你会看到类似这样的警告（可以忽略）：
```
WARNING - Alpaca API密钥未配置,将跳过Alpaca数据获取
INFO - 配置方法: 在.env文件中添加 ALPACA_API_KEY 和 ALPACA_SECRET_KEY
```

## 配置Alpaca（可选）

如果你想启用双数据源验证，按以下步骤操作：

### 1. 注册Alpaca账户

访问 https://alpaca.markets 并注册免费账户（2分钟完成）

### 2. 获取API密钥

1. 登录Alpaca Dashboard
2. 进入 "API Keys" 页面
3. 点击 "Generate New Key"
4. 选择 **Paper Trading**（模拟交易）
5. 复制 `API Key` 和 `Secret Key`

### 3. 配置.env文件

在项目根目录创建或编辑 `.env` 文件：

```bash
# .env
ALPACA_API_KEY=你的API_KEY
ALPACA_SECRET_KEY=你的SECRET_KEY
```

⚠️ **安全提示**: `.env` 文件已在 `.gitignore` 中，不会被提交到Git

### 4. 验证配置

```bash
source venv/bin/activate
python -c "from data.data_fetcher import AlpacaFetcher; f = AlpacaFetcher(); print('✅ Alpaca配置成功!' if f.enabled else '❌ 请检查.env配置')"
```

### 5. 重新下载数据

```bash
# 删除缓存并重新下载
rm -rf data/cache/*.pkl
python scripts/download_data.py --start 2015-01-01
```

现在你应该看到：
```
INFO - Alpaca客户端初始化成功
INFO - 开始从Alpaca下载 503 只股票数据...
```

## Alpaca API限制

免费账户限制：
- **调用频率**: 200次/分钟
- **数据范围**: 最近15年的历史数据
- **数据类型**: 日线、分钟线

对于本项目，这些限制完全足够。

## 常见问题

### Q: 不配置Alpaca会影响功能吗？
**A**: 不会。系统设计为可以完全使用yfinance运行，只是失去了双数据源验证的额外保障。

### Q: Alpaca数据比yfinance更好吗？
**A**: 不一定。Alpaca提供原始价格（无复权），而yfinance提供复权价格。我们以yfinance为主，Alpaca作为验证和补充。

### Q: 如何判断数据源质量？
**A**: 系统会生成验证报告，显示两个数据源的差异率。正常情况下差异率应该<1%。

### Q: 能只使用Alpaca吗？
**A**: 不建议。因为Alpaca不提供复权数据，会影响因子计算的准确性。

## 相关文档

- [Alpaca官方文档](https://alpaca.markets/docs/)
- [alpaca-py Python库](https://github.com/alpacahq/alpaca-py)
