"""
[INPUT]: None (加载配置文件)
[OUTPUT]: Config对象,提供全局配置参数
[POS]: 系统配置管理中心,所有模块通过此获取配置

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import os
from pathlib import Path
from typing import Dict, Any
import yaml
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """全局配置类"""

    def __init__(self, config_path: str = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径,如果为None则使用默认配置
        """
        self.project_root = Path(__file__).parent.parent
        self.config_path = config_path

        # 默认配置
        self._config = self._get_default_config()

        # 如果提供了配置文件,则加载并覆盖默认配置
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                custom_config = yaml.safe_load(f)
                self._config.update(custom_config)

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            # 数据配置
            'data': {
                'start_date': '2015-01-01',
                'end_date': None,  # None表示使用当前日期
                'universe': 'SP500',
                'data_dir': str(self.project_root / 'data' / 'cache'),
                'use_cache': True,
            },
            # API配置
            'api': {
                'yfinance': {
                    'max_workers': 10,  # 并行下载线程数
                },
                'alpaca': {
                    'api_key': os.getenv('ALPACA_API_KEY'),
                    'secret_key': os.getenv('ALPACA_SECRET_KEY'),
                    'base_url': 'https://paper-api.alpaca.markets',  # 模拟交易
                },
            },
            # 因子配置
            'factors': {
                'momentum': {
                    'lookback_months': 12,
                    'skip_months': 1,
                },
                'reversal': {
                    'lookback_months': 1,
                },
                'low_volatility': {
                    'lookback_months': 3,
                },
                'trend': {
                    'ma_window': 200,
                },
                'liquidity': {
                    'lookback_days': 20,
                },
                # 预处理参数
                'winsorize_limits': (0.01, 0.99),
                'standardize_method': 'zscore',
            },
            # 组合配置
            'portfolio': {
                'quantile': 0.2,  # Top/Bottom 20%
                'weighting_method': 'equal',  # equal, market_cap, risk_parity
                'rebalance_freq': 'M',  # M=月度, Q=季度
            },
            # 回测配置
            'backtest': {
                'cost_bps': 20,  # 交易成本(基点)
                'initial_capital': 1000000,  # 初始资金
            },
            # 结果输出配置
            'output': {
                'figures_dir': str(self.project_root / 'results' / 'figures'),
                'tables_dir': str(self.project_root / 'results' / 'tables'),
                'reports_dir': str(self.project_root / 'results' / 'reports'),
            },
            # 日志配置
            'logging': {
                'level': 'INFO',
                'format': '<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>',
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项(支持点号分隔的嵌套键)

        Args:
            key: 配置键,支持嵌套如'data.start_date'
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        return self.get(key)

    def __repr__(self) -> str:
        return f"Config({self.config_path or 'default'})"


# 全局配置实例
config = Config()
