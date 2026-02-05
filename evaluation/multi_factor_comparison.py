"""
多因子对比模块

[INPUT]:
- 因子列表
- 数据
- 回测参数

[OUTPUT]:
- 对比表 (DataFrame)
- 对比报告 (Markdown)

[POS]:
评估层核心模块，负责多因子性能对比

[PROTOCOL]:
1. 支持任意数量因子对比
2. 自动运行回测并提取指标
3. 生成标准化对比表和报告
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
from pathlib import Path
import sys

# 添加项目根目录
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from factors.momentum import MomentumFactor
from factors.reversal import ReversalFactor
from factors.low_volatility import LowVolatilityFactor
from factors.trend import TrendFactor
from factors.liquidity import LiquidityFactor
from factors.factor_processor import FactorProcessor
from factors.factor_combiner import FactorCombiner
from portfolio.portfolio_builder import PortfolioBuilder
from backtest.engine import BacktestEngine
from utils.logger import get_logger

logger = get_logger(__name__)


class MultiFactorComparator:
    """
    多因子对比器

    功能:
    1. 运行多个因子的回测
    2. 生成对比表
    3. 生成对比报告
    """

    # 支持的因子映射
    FACTOR_MAP = {
        'Momentum': MomentumFactor,
        'Reversal': ReversalFactor,
        'LowVolatility': LowVolatilityFactor,
        'Trend': TrendFactor,
        'Liquidity': LiquidityFactor,
    }

    def __init__(
        self,
        rebalance_freq: str = '2monthly',
        min_holding_periods: int = 12,
        entry_quantile: float = 0.25,
        exit_quantile: float = 0.30,
        cost_bps: float = 20.0
    ):
        """
        初始化多因子对比器

        Parameters:
        -----------
        rebalance_freq : str
            调仓频率
        min_holding_periods : int
            最小持有期(月)
        entry_quantile : float
            进入阈值
        exit_quantile : float
            退出阈值
        cost_bps : float
            交易成本(bps)
        """
        self.rebalance_freq = rebalance_freq
        self.min_holding_periods = min_holding_periods
        self.entry_quantile = entry_quantile
        self.exit_quantile = exit_quantile
        self.cost_bps = cost_bps

        logger.info(
            f"初始化多因子对比器: "
            f"调仓={rebalance_freq}, 持有期={min_holding_periods}月, "
            f"阈值={entry_quantile}/{exit_quantile}, 成本={cost_bps}bps"
        )

    def run_single_factor(
        self,
        factor_name: str,
        df_clean: dict
    ) -> Dict:
        """
        运行单个因子回测

        Parameters:
        -----------
        factor_name : str
            因子名称
        df_clean : dict
            清洗后的数据

        Returns:
        --------
        result : dict
            回测结果
        """
        logger.info(f"测试因子: {factor_name}")

        # 1. 获取因子类
        if factor_name not in self.FACTOR_MAP:
            raise ValueError(f"未知因子: {factor_name}")

        factor_class = self.FACTOR_MAP[factor_name]
        factor = factor_class()

        # 2. 计算因子
        if factor_name == 'Liquidity':
            # Liquidity因子需要volume数据
            if 'volume' not in df_clean or df_clean['volume'] is None:
                raise ValueError("Liquidity因子需要volume数据，但数据中没有volume")
            df_factor = factor.calculate(
                df_price=df_clean['price'],
                df_volume=df_clean['volume']
            )
        else:
            df_factor = factor.calculate(
                df_price=df_clean['price'],
                df_return_daily=df_clean.get('daily_return')
            )

        # 3. 标准化
        processor = FactorProcessor()
        df_factor = processor.winsorize(df_factor)
        df_factor = processor.zscore_standardize(df_factor)

        # 4. 构建组合(自动中性化)
        builder = PortfolioBuilder(
            entry_quantile=self.entry_quantile,
            exit_quantile=self.exit_quantile,
            min_holding_periods=self.min_holding_periods,
            long_top=True
        )
        df_weights = builder.build(df_factor, neutralize=True)

        # 5. 回测
        engine = BacktestEngine(
            cost_bps=self.cost_bps,
            rebalance_freq=self.rebalance_freq
        )

        df_return = df_clean['monthly_return']
        backtest_result = engine.run(df_weights, df_return)

        return backtest_result

    def run_composite_factor(
        self,
        df_clean: dict,
        factor_names: Optional[List[str]] = None
    ) -> Dict:
        """
        运行合成因子回测

        Parameters:
        -----------
        df_clean : dict
            清洗后的数据
        factor_names : list, optional
            要合成的因子名称列表，默认使用所有单因子

        Returns:
        --------
        result : dict
            回测结果
        """
        logger.info("测试合成因子")

        if factor_names is None:
            factor_names = list(self.FACTOR_MAP.keys())

        # 1. 计算所有单因子
        df_factors = {}
        for name in factor_names:
            if name not in self.FACTOR_MAP:
                logger.warning(f"跳过未知因子: {name}")
                continue

            # 跳过Liquidity如果没有volume数据
            if name == 'Liquidity' and ('volume' not in df_clean or df_clean['volume'] is None):
                logger.warning(f"跳过Liquidity因子: 缺少volume数据")
                continue

            factor_class = self.FACTOR_MAP[name]
            factor = factor_class()

            if name == 'Liquidity':
                df_factor = factor.calculate(
                    df_price=df_clean['price'],
                    df_volume=df_clean['volume']
                )
            else:
                df_factor = factor.calculate(
                    df_price=df_clean['price'],
                    df_return_daily=df_clean.get('daily_return')
                )
            df_factors[name] = df_factor

        # 2. 标准化
        processor = FactorProcessor()
        processed_factors = {}
        for name, df_factor in df_factors.items():
            df_processed = processor.winsorize(df_factor)
            df_processed = processor.zscore_standardize(df_processed)
            processed_factors[name] = df_processed

        # 3. 合成因子
        combiner = FactorCombiner()
        df_composite = combiner.combine(
            list(processed_factors.values()),
            factor_names=list(processed_factors.keys())
        )

        # 4. 构建组合(自动中性化)
        builder = PortfolioBuilder(
            entry_quantile=self.entry_quantile,
            exit_quantile=self.exit_quantile,
            min_holding_periods=self.min_holding_periods,
            long_top=True
        )
        df_weights = builder.build(df_composite, neutralize=True)

        # 5. 回测
        engine = BacktestEngine(
            cost_bps=self.cost_bps,
            rebalance_freq=self.rebalance_freq
        )

        df_return = df_clean['monthly_return']
        backtest_result = engine.run(df_weights, df_return)

        return backtest_result

    def compare(
        self,
        df_clean: dict,
        factor_names: Optional[List[str]] = None,
        include_composite: bool = True
    ) -> pd.DataFrame:
        """
        对比多个因子

        Parameters:
        -----------
        df_clean : dict
            清洗后的数据
        factor_names : list, optional
            要对比的因子名称列表，默认使用所有单因子
        include_composite : bool
            是否包含合成因子

        Returns:
        --------
        df_comparison : DataFrame
            对比结果表
        """
        logger.info("="*80)
        logger.info("开始多因子对比")
        logger.info("="*80)

        if factor_names is None:
            factor_names = list(self.FACTOR_MAP.keys())

        results = {}

        # 1. 单因子回测
        for factor_name in factor_names:
            try:
                result = self.run_single_factor(factor_name, df_clean)
                results[factor_name] = result
            except Exception as e:
                logger.error(f"因子 {factor_name} 测试失败: {e}")
                import traceback
                traceback.print_exc()

        # 2. 合成因子回测
        if include_composite:
            try:
                result = self.run_composite_factor(df_clean, factor_names)
                results['Composite'] = result
            except Exception as e:
                logger.error(f"合成因子测试失败: {e}")
                import traceback
                traceback.print_exc()

        # 3. 生成对比表
        df_comparison = self._create_comparison_table(results)

        logger.info("="*80)
        logger.info("多因子对比完成")
        logger.info("="*80)

        return df_comparison

    def _create_comparison_table(self, results: Dict) -> pd.DataFrame:
        """
        创建对比表

        Parameters:
        -----------
        results : dict
            各因子的回测结果

        Returns:
        --------
        df_comparison : DataFrame
            对比表
        """
        comparison_data = []

        for factor_name, result in results.items():
            metrics = result['metrics']
            metrics_no_cost = result['metrics_no_cost']

            row = {
                'factor': factor_name,
                'annual_return': metrics['annual_return'],
                'annual_return_no_cost': metrics_no_cost['annual_return'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'sharpe_ratio_no_cost': metrics_no_cost['sharpe_ratio'],
                'max_drawdown': metrics['max_drawdown'],
                'annual_volatility': metrics['annual_volatility'],
                'calmar_ratio': metrics['calmar_ratio'],
                'sortino_ratio': metrics['sortino_ratio'],
                'win_rate': metrics['win_rate'],
                'avg_turnover': result['turnover'].mean(),
                'rebalance_count': (result['turnover'] > 0).sum(),
                'total_cost': result['cost_series'].sum()
            }
            comparison_data.append(row)

        df_comparison = pd.DataFrame(comparison_data)

        # 按Sharpe排序
        df_comparison = df_comparison.sort_values('sharpe_ratio', ascending=False)

        return df_comparison

    def generate_report(
        self,
        df_comparison: pd.DataFrame,
        output_path: Optional[str] = None
    ) -> str:
        """
        生成对比报告

        Parameters:
        -----------
        df_comparison : DataFrame
            对比结果表
        output_path : str, optional
            报告保存路径

        Returns:
        --------
        report : str
            报告内容(Markdown)
        """
        report = f"""# 多因子对比报告 (中性化权重)

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**回测配置**: {self.rebalance_freq} + {self.min_holding_periods}月持有期 + {self.entry_quantile:.0%}/{self.exit_quantile:.0%}阈值 + {self.cost_bps:.0f}bps成本

---

## 完整对比表

| 因子 | 年化收益 | Sharpe | 最大回撤 | 波动率 | Calmar | 胜率 | 换手率 |
|------|----------|--------|----------|--------|--------|------|--------|
"""

        for _, row in df_comparison.iterrows():
            report += (
                f"| {row['factor']} | {row['annual_return']:.2%} | "
                f"{row['sharpe_ratio']:.4f} | {row['max_drawdown']:.2%} | "
                f"{row['annual_volatility']:.2%} | {row['calmar_ratio']:.4f} | "
                f"{row['win_rate']:.2%} | {row['avg_turnover']:.2%} |\n"
            )

        report += f"""
---

## 关键发现

### 最佳因子

**{df_comparison.iloc[0]['factor']}** 表现最优:
- 年化收益: {df_comparison.iloc[0]['annual_return']:.2%}
- Sharpe比率: {df_comparison.iloc[0]['sharpe_ratio']:.4f}
- 最大回撤: {df_comparison.iloc[0]['max_drawdown']:.2%}
- 平均换手率: {df_comparison.iloc[0]['avg_turnover']:.2%}

### 成本影响

平均成本拖累: {df_comparison['total_cost'].mean():.2%}

### 合成因子表现

"""

        if 'Composite' in df_comparison['factor'].values:
            composite_row = df_comparison[df_comparison['factor'] == 'Composite'].iloc[0]
            composite_rank = df_comparison.index[df_comparison['factor'] == 'Composite'].tolist()[0] + 1
            report += f"""合成因子排名: {composite_rank}/{len(df_comparison)}
- 年化收益: {composite_row['annual_return']:.2%}
- Sharpe比率: {composite_row['sharpe_ratio']:.4f}
- 最大回撤: {composite_row['max_drawdown']:.2%}
"""
        else:
            report += "未包含合成因子\n"

        report += f"""
---

**报告生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        # 保存报告
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"报告已保存: {output_path}")

        return report
