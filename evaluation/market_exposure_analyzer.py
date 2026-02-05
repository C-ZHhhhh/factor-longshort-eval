"""
市场暴露分析器

计算策略对市场指数(SPY)的暴露，包括：
- 全样本 beta (OLS 回归)
- 滚动 12M beta (可选)
- 相关系数、R²
- Beta 显著性检验

[INPUT]:
- 策略收益率序列
- 市场收益率(SPY)序列

[OUTPUT]:
- exposure_summary.md: Beta分析报告
- exposure_stats.csv: Beta统计数据

[POS]:
评估层暴露分析模块

[PROTOCOL]:
1. 使用 OLS 回归估计 beta
2. 计算 rolling 12M beta (可选)
3. 输出详细的暴露报告
4. 如果 |beta| > 0.1，发出警告
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sys
from scipy.stats import linregress

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from evaluation.exposure_check import ExposureChecker
from utils.logger import get_logger

logger = get_logger(__name__)


class MarketExposureAnalyzer:
    """
    市场暴露分析器

    分析策略对市场指数(如SPY)的暴露
    """

    def __init__(self, beta_threshold: float = 0.1):
        """
        初始化市场暴露分析器

        Parameters:
        -----------
        beta_threshold : float
            Beta 阈值，超过此值发出警告
        """
        self.beta_threshold = beta_threshold
        self.exposure_checker = ExposureChecker()

    def analyze_market_exposure(
        self,
        strategy_returns: Dict[str, pd.Series],
        market_returns: pd.Series,
        output_dir: str = 'results',
        rolling_window: int = 12
    ) -> Dict:
        """
        完整的市场暴露分析

        Parameters:
        -----------
        strategy_returns : dict
            {strategy_name: returns_series} 字典
        market_returns : Series
            市场收益率(SPY)
        output_dir : str
            输出目录
        rolling_window : int
            滚动窗口大小(月)

        Returns:
        --------
        result : dict
            暴露分析结果
        """
        logger.info("="*80)
        logger.info("开始市场暴露分析")
        logger.info("="*80)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 对每个策略计算全样本 beta
        logger.info("\n[1/3] 计算全样本 Beta...")
        full_sample_results = {}

        for strategy_name, returns in strategy_returns.items():
            logger.info(f"  分析 {strategy_name}...")

            beta_stats = self.exposure_checker.estimate_beta_from_returns(
                df_portfolio_return=returns,
                df_market_return=market_returns
            )

            # 计算相关系数
            common_idx = returns.index.intersection(market_returns.index)
            if len(common_idx) > 0:
                corr = returns.loc[common_idx].corr(market_returns.loc[common_idx])
            else:
                corr = np.nan

            full_sample_results[strategy_name] = {
                'beta': beta_stats['beta'],
                'alpha': beta_stats['alpha'],
                'r_squared': beta_stats['r_squared'],
                'p_value': beta_stats['p_value'],
                'std_error': beta_stats.get('std_error', np.nan),
                'correlation': corr,
                'n_periods': len(common_idx)
            }

            logger.info(f"    Beta = {beta_stats['beta']:.4f}")
            logger.info(f"    Alpha = {beta_stats['alpha']:.4f}")
            logger.info(f"    R² = {beta_stats['r_squared']:.4f}")
            logger.info(f"    相关系数 = {corr:.4f}")

            # 检查 beta 是否超过阈值
            if abs(beta_stats['beta']) > self.beta_threshold:
                logger.warning(
                    f"    ⚠️  警告: {strategy_name} 的 Beta ({beta_stats['beta']:.4f}) "
                    f"超过阈值 {self.beta_threshold}，市场中性化不充分!"
                )

        # 2. 计算滚动 beta (可选)
        logger.info(f"\n[2/3] 计算滚动 {rolling_window}M Beta...")
        rolling_beta_results = {}

        for strategy_name, returns in strategy_returns.items():
            logger.info(f"  计算 {strategy_name} 滚动Beta...")

            rolling_beta = self._calculate_rolling_beta(
                returns, market_returns, rolling_window
            )

            rolling_beta_results[strategy_name] = rolling_beta

            if rolling_beta is not None and len(rolling_beta) > 0:
                logger.info(f"    滚动Beta 均值 = {rolling_beta.mean():.4f}")
                logger.info(f"    滚动Beta 标准差 = {rolling_beta.std():.4f}")
                logger.info(f"    滚动Beta 范围 = [{rolling_beta.min():.4f}, {rolling_beta.max():.4f}]")

        # 3. 生成报告
        logger.info("\n[3/3] 生成暴露报告...")
        self._save_exposure_summary(
            full_sample_results=full_sample_results,
            rolling_beta_results=rolling_beta_results,
            output_path=output_path,
            rolling_window=rolling_window
        )

        logger.info("\n" + "="*80)
        logger.info("✅ 市场暴露分析完成")
        logger.info("="*80)

        return {
            'full_sample': full_sample_results,
            'rolling_beta': rolling_beta_results
        }

    def _calculate_rolling_beta(
        self,
        strategy_returns: pd.Series,
        market_returns: pd.Series,
        window: int
    ) -> Optional[pd.Series]:
        """
        计算滚动 beta

        Parameters:
        -----------
        strategy_returns : Series
            策略收益率
        market_returns : Series
            市场收益率
        window : int
            滚动窗口大小

        Returns:
        --------
        rolling_beta : Series
            滚动 beta 序列
        """
        # 对齐数据
        common_idx = strategy_returns.index.intersection(market_returns.index)

        if len(common_idx) < window:
            logger.warning(f"    样本数 ({len(common_idx)}) 小于窗口大小 ({window})，跳过滚动Beta计算")
            return None

        strategy_ret = strategy_returns.loc[common_idx]
        market_ret = market_returns.loc[common_idx]

        # 计算滚动 beta
        rolling_beta = []
        rolling_dates = []

        for i in range(window, len(common_idx) + 1):
            window_strategy = strategy_ret.iloc[i-window:i]
            window_market = market_ret.iloc[i-window:i]

            # OLS 回归
            valid_mask = window_strategy.notna() & window_market.notna()
            if valid_mask.sum() < 10:
                rolling_beta.append(np.nan)
            else:
                slope, _, _, _, _ = linregress(
                    window_market[valid_mask],
                    window_strategy[valid_mask]
                )
                rolling_beta.append(slope)

            rolling_dates.append(common_idx[i-1])

        rolling_beta_series = pd.Series(rolling_beta, index=rolling_dates)
        return rolling_beta_series

    def _save_exposure_summary(
        self,
        full_sample_results: Dict,
        rolling_beta_results: Dict,
        output_path: Path,
        rolling_window: int
    ):
        """保存暴露分析报告"""

        # 1. 保存 CSV
        df_full_sample = pd.DataFrame(full_sample_results).T
        df_full_sample.index.name = 'strategy'
        df_full_sample.to_csv(output_path / 'exposure_stats.csv', float_format='%.6f')
        logger.info(f"✅ 暴露统计数据已保存: {output_path / 'exposure_stats.csv'}")

        # 2. 生成 Markdown 报告
        md_content = self._create_markdown_report(
            full_sample_results, rolling_beta_results, rolling_window
        )

        md_file = output_path / 'exposure_summary.md'
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logger.info(f"✅ 暴露分析报告已保存: {md_file}")

    def _create_markdown_report(
        self,
        full_sample_results: Dict,
        rolling_beta_results: Dict,
        rolling_window: int
    ) -> str:
        """创建 Markdown 格式报告"""

        md = f"""# 市场暴露分析报告

生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 概述

本报告分析策略对市场指数(SPY)的暴露。

**策略类型说明**:
- **当前实现**: Dollar-Neutral (资金中性)
  - 定义: sum(w) = 0, long = +1, short = -1
  - 保证多空资金平衡，但 **不保证 Beta = 0**
- **Beta-Neutral (Beta 中性)**:
  - 需要额外对冲，使组合 Beta ≈ 0
  - 可选功能（未实现）

**关键指标**:
- **Beta**: 策略对市场的敏感度 (dollar-neutral 不保证=0)
- **Alpha**: 策略的超额收益，扣除市场影响后的纯选股收益
- **R²**: 市场能解释策略收益的比例，越低越好
- **相关系数**: 策略与市场的相关性，越低越好

**警告阈值**: |Beta| > {self.beta_threshold}

---

## 全样本 Beta 分析

| 策略 | Beta | Alpha | R² | 相关系数 | p-value | 样本数 | 评价 |
|------|------|-------|-----|---------|---------|-------|------|
"""

        for strategy_name, result in full_sample_results.items():
            beta = result['beta']

            # 评价
            if abs(beta) > self.beta_threshold:
                rating = f"⚠️  超标 (|{beta:.4f}| > {self.beta_threshold})"
            elif abs(beta) > self.beta_threshold / 2:
                rating = "🟡 需关注"
            else:
                rating = "✅ 良好"

            md += (
                f"| {strategy_name} "
                f"| {beta:.4f} "
                f"| {result['alpha']:.4f} "
                f"| {result['r_squared']:.4f} "
                f"| {result['correlation']:.4f} "
                f"| {result['p_value']:.4f} "
                f"| {result['n_periods']:.0f} "
                f"| {rating} |\n"
            )

        md += """
---

## Beta 解读

### 理想的 Market-Neutral 策略特征

- **Beta ≈ 0**: 策略收益与市场无关，完全来自选股能力
- **R² < 0.1**: 市场只能解释 <10% 的策略收益
- **|相关系数| < 0.3**: 与市场低相关或无相关

### 警告信号

"""

        # 检查是否有策略超标
        warning_strategies = [
            name for name, result in full_sample_results.items()
            if abs(result['beta']) > self.beta_threshold
        ]

        if warning_strategies:
            md += "以下策略的 Beta 超过阈值，需要优化中性化效果：\n\n"
            for name in warning_strategies:
                result = full_sample_results[name]
                md += f"- **{name}**: Beta = {result['beta']:.4f}\n"
                md += f"  - 原因分析: R² = {result['r_squared']:.2%}，市场能解释 {result['r_squared']:.2%} 的收益波动\n"
                md += f"  - 建议: 检查权重中性化、增加对冲、调整因子选股逻辑\n\n"
        else:
            md += "✅ 所有策略的 Beta 均在阈值范围内，中性化效果良好。\n\n"

        md += f"""
---

## 滚动 {rolling_window}M Beta 分析

"""

        # 滚动 beta 统计
        for strategy_name, rolling_beta in rolling_beta_results.items():
            if rolling_beta is None or len(rolling_beta) == 0:
                md += f"### {strategy_name}\n\n无滚动Beta数据\n\n"
                continue

            md += f"### {strategy_name}\n\n"
            md += "| 指标 | 数值 |\n"
            md += "|------|------|\n"
            md += f"| 均值 | {rolling_beta.mean():.4f} |\n"
            md += f"| 标准差 | {rolling_beta.std():.4f} |\n"
            md += f"| 最小值 | {rolling_beta.min():.4f} |\n"
            md += f"| 最大值 | {rolling_beta.max():.4f} |\n"
            md += f"| 超标比例 | {(abs(rolling_beta) > self.beta_threshold).mean():.2%} |\n"
            md += "\n"

        md += """
---

## 结论与建议

### 主要发现

"""

        # 生成结论
        conclusions = []

        # 1. Beta 水平
        avg_abs_beta = np.mean([abs(r['beta']) for r in full_sample_results.values()])
        if avg_abs_beta < 0.05:
            conclusions.append(f"1. **优秀的市场中性化**: 平均 |Beta| = {avg_abs_beta:.4f}，策略成功规避市场风险")
        elif avg_abs_beta < 0.1:
            conclusions.append(f"1. **良好的市场中性化**: 平均 |Beta| = {avg_abs_beta:.4f}，大部分市场风险已被中性化")
        else:
            conclusions.append(f"1. **⚠️  中性化不足**: 平均 |Beta| = {avg_abs_beta:.4f}，仍有较大市场暴露")

        # 2. R² 水平
        avg_r_squared = np.mean([r['r_squared'] for r in full_sample_results.values()])
        if avg_r_squared < 0.1:
            conclusions.append(f"2. **高选股能力**: 平均 R² = {avg_r_squared:.2%}，策略收益主要来自选股而非市场")
        else:
            conclusions.append(f"2. **⚠️  市场依赖较高**: 平均 R² = {avg_r_squared:.2%}，策略收益受市场影响较大")

        # 3. 相关性
        avg_corr = np.mean([abs(r['correlation']) for r in full_sample_results.values()])
        if avg_corr < 0.3:
            conclusions.append(f"3. **低市场相关性**: 平均 |相关系数| = {avg_corr:.4f}，策略与市场相关性低")
        else:
            conclusions.append(f"3. **⚠️  市场相关性较高**: 平均 |相关系数| = {avg_corr:.4f}，策略与市场走势较为同步")

        for conclusion in conclusions:
            md += f"{conclusion}\n\n"

        md += """
### 改进建议

"""

        suggestions = []

        if warning_strategies:
            suggestions.append("""1. **加强中性化**
   - 检查权重归一化逻辑，确保 Σw ≈ 0
   - 考虑增加市场对冲头寸
   - 调整多空比例，确保资金配置平衡""")

        if avg_r_squared > 0.1:
            suggestions.append("""2. **降低市场依赖**
   - 增加横截面选股信号强度
   - 减少因子中的市场beta成分
   - 考虑添加行业中性化约束""")

        if not suggestions:
            suggestions.append("""✅ **当前策略表现良好**
   - 保持现有的中性化逻辑
   - 继续监控滚动Beta的稳定性
   - 定期验证市场暴露是否漂移""")

        for idx, suggestion in enumerate(suggestions, 1):
            if idx <= len(suggestions):
                md += f"{suggestion}\n\n"

        md += """
---

*本报告由市场暴露分析器自动生成*
"""

        return md


if __name__ == '__main__':
    """测试代码"""
    logger.info("市场暴露分析器模块")
    logger.info("请使用 scripts/run_evaluation.py 运行评估")
