"""
[INPUT]: None
[OUTPUT]: 配置好的logger实例
[POS]: 全局日志管理,所有模块通过此记录日志

[PROTOCOL]:
1. 逻辑变更时同步更新此头部
2. 更新后检查所在文件夹的 CLAUDE.md
"""

import sys
from loguru import logger
from utils.config import config

# 移除默认的handler
logger.remove()

# 添加控制台handler
logger.add(
    sys.stderr,
    format=config.get('logging.format'),
    level=config.get('logging.level', 'INFO'),
    colorize=True,
)

# 添加文件handler(可选)
logger.add(
    config.project_root / 'logs' / 'factor_reg_{time:YYYY-MM-DD}.log',
    rotation='1 day',
    retention='30 days',
    level='DEBUG',
    encoding='utf-8',
)


def get_logger(name: str = None):
    """
    获取logger实例

    Args:
        name: 模块名称

    Returns:
        logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger
