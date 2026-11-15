"""检查缓存数据是否包含volume"""
import pandas as pd
import sys

from data.data_loader import DataLoader

try:
    cache_file = DataLoader().latest_cache_file()  # 最新的缓存文件, 不写死文件名
    data = pd.read_pickle(cache_file)
    print(f'✅ 成功加载缓存文件: {cache_file.name}')
    print(f'缓存中的键: {list(data.keys())}')

    if 'volume' in data:
        if data['volume'] is None:
            print('❌ volume键存在，但值为None')
        else:
            print(f'✅ volume数据存在')
            print(f'   形状: {data["volume"].shape}')
            print(f'   时间范围: {data["volume"].index.min()} ~ {data["volume"].index.max()}')
            print(f'   股票数: {len(data["volume"].columns)}')
    else:
        print('❌ 缺少volume键！这是旧缓存文件')

except Exception as e:
    print(f'❌ 错误: {e}')
    sys.exit(1)
