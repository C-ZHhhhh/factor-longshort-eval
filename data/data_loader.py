"""
数据加载器

[INPUT]:
- 缓存文件路径

[OUTPUT]:
- 清洗后的数据字典 (包含price, volume, return_daily, return_monthly)

[POS]:
数据加载工具，用于加载缓存的清洗数据

[PROTOCOL]:
1. 从缓存加载数据
2. 如果缓存不存在，抛出错误
3. 向后兼容旧缓存（可能没有volume）

[UPDATE 2026-11-15]:
- 新增 latest_cache_file(): "用哪个缓存文件"的唯一入口。脚本不要再写死
  clean_data_<日期>_<数量>.pkl 这种文件名（换一天下载文件名就变了）。
- 默认缓存目录改为相对项目根目录（data/cache），不再依赖从哪个目录启动脚本。
"""

import pandas as pd
import pickle
from pathlib import Path
from typing import Optional


class DataLoader:
    """数据加载器"""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Args:
            cache_dir: 缓存目录，默认是项目下的 data/cache
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / 'cache'
        self.cache_dir = Path(cache_dir)

    def latest_cache_file(self) -> Path:
        """
        找到最新的清洗数据缓存文件

        Returns:
            修改时间最新的 clean_data_*.pkl 的路径

        Raises:
            FileNotFoundError: 缓存目录里没有任何缓存文件
        """
        cache_files = list(self.cache_dir.glob('clean_data_*.pkl'))
        if not cache_files:
            raise FileNotFoundError(
                f"未找到缓存数据文件: {self.cache_dir}\n"
                f"请先运行: python scripts/download_data.py"
            )
        return max(cache_files, key=lambda p: p.stat().st_mtime)

    def load_cleaned_data(self, cache_file: Optional[str] = None):
        """
        加载清洗后的数据

        Parameters:
        -----------
        cache_file : str, optional
            缓存文件名，如果不指定则自动查找最新的

        Returns:
        --------
        data : dict
            包含 'price', 'volume', 'daily_return', 'monthly_return'等键的字典
            注意: 旧缓存可能没有'volume'键
        """
        if cache_file is None:
            cache_file = self.latest_cache_file()
        else:
            cache_file = self.cache_dir / cache_file

        print(f"加载缓存数据: {cache_file}")

        with open(cache_file, 'rb') as f:
            data = pickle.load(f)

        # 处理数据格式
        if isinstance(data, dict):
            # 标准化键名
            if 'return_monthly' in data:
                data['monthly_return'] = data['return_monthly']
            if 'return_daily' in data:
                data['daily_return'] = data['return_daily']

            # 向后兼容: 旧缓存可能没有volume
            if 'volume' not in data:
                print("  ⚠️  警告: 缓存文件缺少volume数据，Liquidity因子将无法使用")
                data['volume'] = None

            print(f"数据包含键: {list(data.keys())}")

            # 打印形状信息
            for key, df in data.items():
                if isinstance(df, pd.DataFrame):
                    print(f"  {key}: {df.shape}")
                    if not df.empty:
                        print(f"    时间范围: {df.index.min()} ~ {df.index.max()}")
                elif df is None:
                    print(f"  {key}: None (缺失)")
        else:
            # 如果是DataFrame，转换为字典格式
            print(f"数据形状: {data.shape}")
            print(f"时间范围: {data.index.min()} ~ {data.index.max()}")
            data = {'price': data, 'volume': None}

        return data
