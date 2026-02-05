# Alpaca API 配置指南

## 为什么需要Alpaca?

本系统使用**双数据源策略**来确保数据质量:
- **主数据源**: yfinance (免费)
- **备用数据源**: Alpaca (免费,需注册)

通过交叉验证两个数据源,可以检测并标记异常数据点,提高回测的可靠性。

## 配置步骤

### 1. 注册Alpaca账户

访问 https://alpaca.markets 并注册账户 (完全免费)

### 2. 获取API密钥

1. 登录后进入 Dashboard
2. 点击左侧菜单的 "API Keys"
3. 点击 "Generate New Key"
4. 选择 "Paper Trading" (模拟交易)
5. 复制 API Key 和 Secret Key

### 3. 配置.env文件

在项目根目录的 `.env` 文件中添加:

```bash
ALPACA_API_KEY=你的API_KEY
ALPACA_SECRET_KEY=你的SECRET_KEY
```

### 4. 验证配置

运行测试脚本验证配置是否成功:

```bash
source venv/bin/activate
python -c "from data.data_fetcher import AlpacaFetcher; f = AlpacaFetcher(); print('Alpaca配置成功!' if f.enabled else '请检查.env配置')"
```

## 注意事项

1. **免费限制**: Alpaca免费账户有API调用频率限制,但对于本项目足够使用
2. **数据质量**: Alpaca提供的是原始收盘价,没有复权数据,所以我们仍以yfinance为主
3. **可选配置**: 即使不配置Alpaca,系统仍可正常运行(仅使用yfinance)

## 如果不使用Alpaca

如果选择只使用yfinance:
- 不需要配置`.env`文件
- 系统会自动跳过Alpaca数据获取
- 数据验证环节会跳过,直接使用yfinance数据

这不会影响系统功能,只是失去了双数据源交叉验证的额外保障。
