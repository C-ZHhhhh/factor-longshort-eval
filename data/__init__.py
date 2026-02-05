"""
数据层包

提供便捷的数据加载函数
"""

from data.data_loader import DataLoader


def load_clean_data(cache_file=None):
    """
    便捷函数: 加载清洗后的数据

    Parameters:
    -----------
    cache_file : str, optional
        缓存文件名，如果不指定则自动查找最新的

    Returns:
    --------
    data : dict
        包含 'price', 'volume', 'daily_return', 'monthly_return'的字典
        注意: 如果是旧缓存，volume可能为None

    Examples:
    ---------
    >>> df_clean = load_clean_data()
    >>> print(df_clean.keys())
    dict_keys(['price', 'volume', 'daily_return', 'monthly_return'])
    """
    loader = DataLoader()
    return loader.load_cleaned_data(cache_file)


__all__ = ['load_clean_data', 'DataLoader']
