"""检查缓存数据是否包含volume"""
import pandas as pd
import sys

cache_file = 'data/cache/clean_data_2015-01-01_2026-02-04_503_dedup.pkl'

try:
    data = pd.read_pickle(cache_file)
    print('✅ 成功加载缓存文件')
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
