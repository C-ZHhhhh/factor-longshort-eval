"""快速测试Liquidity因子是否有数据"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data import load_clean_data
from factors.liquidity import LiquidityFactor

# 加载数据
print("加载数据...")
df_clean = load_clean_data()

# 测试Liquidity因子
print("\n测试Liquidity因子...")
liquidity_factor = LiquidityFactor()

if df_clean['volume'] is None:
    print("❌ volume数据缺失，无法计算Liquidity因子")
else:
    print("✅ volume数据存在，计算Liquidity因子...")
    df_liquidity = liquidity_factor.calculate(
        df_price=df_clean['price'],
        df_volume=df_clean['volume']
    )
    print(f"✅ Liquidity因子计算成功!")
    print(f"   形状: {df_liquidity.shape}")
    print(f"   非空值数量: {df_liquidity.notna().sum().sum()}")
    print(f"   样本值:\n{df_liquidity.iloc[:5, :5]}")
