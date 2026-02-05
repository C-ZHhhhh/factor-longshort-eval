"""快速测试多因子对比中是否包含Liquidity"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data import load_clean_data
from evaluation.multi_factor_comparison import MultiFactorComparator

# 加载数据
print("加载数据...")
df_clean = load_clean_data()

# 初始化对比器
print("\n初始化多因子对比器...")
comparator = MultiFactorComparator(
    rebalance_freq='2monthly',
    min_holding_periods=12,
    entry_quantile=0.25,
    exit_quantile=0.30,
    cost_bps=20.0
)

# 测试Liquidity因子
print("\n测试Liquidity因子回测...")
try:
    result = comparator.run_single_factor('Liquidity', df_clean)
    print("✅ Liquidity因子回测成功!")
    print(f"   年化收益: {result['metrics']['annual_return']:.2%}")
    print(f"   Sharpe比率: {result['metrics']['sharpe_ratio']:.4f}")
    print(f"   最大回撤: {result['metrics']['max_drawdown']:.2%}")
except Exception as e:
    print(f"❌ Liquidity因子回测失败: {e}")
    import traceback
    traceback.print_exc()

print("\n检查FACTOR_MAP...")
print(f"支持的因子: {list(comparator.FACTOR_MAP.keys())}")
if 'Liquidity' in comparator.FACTOR_MAP:
    print("✅ Liquidity已在FACTOR_MAP中")
else:
    print("❌ Liquidity不在FACTOR_MAP中")
