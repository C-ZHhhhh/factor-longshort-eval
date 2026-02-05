# Matplotlib 中文字体配置指南

> 本文档记录因子回测系统中实现 matplotlib 图表正确显示中文的完整策略

## 问题背景

matplotlib 默认不支持中文显示，未配置时会出现：
- 中文字符显示为方框 (□□□)
- 控制台输出大量 `findfont: Font family [...] not found` 警告
- 图表标题、标签、图例等中文内容无法正常阅读

## 解决方案概览

**核心思路**: 跨平台字体检测 + 优先级回退机制 + matplotlib 全局配置

实现位置: `visualization/factor_visualizer.py:75-93`

## 实现细节

### 1. 跨平台字体检测

使用 `platform.system()` 检测操作系统，为不同平台设置不同的字体优先级列表：

```python
import platform
import matplotlib as mpl

def _configure_chinese_font(self):
    """配置中文字体"""
    system = platform.system()

    # 根据操作系统选择字体
    if system == 'Darwin':  # macOS
        fonts = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS', 'Songti SC']
    elif system == 'Windows':
        fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
    elif system == 'Linux':
        fonts = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Droid Sans Fallback']
    else:
        fonts = []
```

### 2. 字体优先级列表设计原则

**macOS 字体选择**:
- `PingFang SC` (苹方) - macOS 默认中文字体，现代美观
- `Heiti SC` (黑体) - 备选方案，覆盖面广
- `STHeiti` - 华文黑体，老版本 macOS 支持
- `Arial Unicode MS` - Unicode 字体，包含中文
- `Songti SC` (宋体) - 最后备选

**Windows 字体选择**:
- `Microsoft YaHei` (微软雅黑) - Windows 7+ 默认，最佳显示效果
- `SimHei` (黑体) - 通用兼容性好
- `SimSun` (宋体) - 经典字体，覆盖面广
- `KaiTi` (楷体) - 最后备选

**Linux 字体选择**:
- `WenQuanYi Micro Hei` (文泉驿微米黑) - 开源中文字体
- `Noto Sans CJK SC` (思源黑体) - Google 开源字体
- `Droid Sans Fallback` - Android 字体，Linux 常见

### 3. 回退机制

在中文字体列表后添加英文字体，确保系统在找不到中文字体时仍能正常工作：

```python
if fonts:
    mpl.rcParams['font.sans-serif'] = fonts + ['DejaVu Sans', 'Arial']
```

**字体查找顺序**:
```
中文字体列表 → DejaVu Sans → Arial → matplotlib 默认字体
```

### 4. matplotlib 全局配置

配置 matplotlib 的全局参数，确保所有图表都使用正确的字体设置：

```python
mpl.rcParams['font.sans-serif'] = fonts + ['DejaVu Sans', 'Arial']
mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
mpl.rcParams['font.family'] = 'sans-serif'  # 使用无衬线字体
```

**关键参数说明**:
- `font.sans-serif`: 设置无衬线字体的优先级列表
- `axes.unicode_minus`: 设为 `False` 防止负号显示为方框
- `font.family`: 指定使用 sans-serif 字体族

### 5. 初始化时机

在 `FactorVisualizer` 类初始化时自动调用字体配置：

```python
class FactorVisualizer:
    def __init__(self, output_dir: str = 'results/figures'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 配置中文字体 (在任何绘图操作之前执行)
        self._configure_chinese_font()

        # ... 其他初始化代码
```

## 验证测试

### 测试脚本

`scripts/test_visualization_font.py` 提供完整的字体测试流程：

```bash
# 运行测试 (过滤字体查找日志)
source venv/bin/activate && \
rm -rf results/test/font_test && \
python scripts/test_visualization_font.py 2>&1 | grep -v "^findfont:"
```

### 测试内容

测试脚本会生成 4 种包含中文的图表：

1. **净值曲线对比图** (`nav_comparison.png`)
   - 测试中文标题、轴标签、图例

2. **IC时间序列图** (`ic_timeseries.png`)
   - 测试中文标题、动态文本格式化

3. **回撤曲线图** (`drawdown_analysis.png`)
   - 测试中文标题、百分比格式

4. **因子相关性热图** (`factor_correlation_heatmap.png`)
   - 测试热图中的中文标签

### 验证清单

检查生成的图片：
- ✅ 标题中文正常显示（无方框）
- ✅ 轴标签中文正常显示
- ✅ 图例中文正常显示
- ✅ 数值格式正确（负号不是方框）
- ✅ 整体布局美观无错位

## 最佳实践

### 1. 在项目初始化时配置

确保在任何绘图操作之前完成字体配置：

```python
# ✅ 正确：在初始化时配置
visualizer = FactorVisualizer(output_dir='results/figures')
# 字体已配置完成，后续绘图都会生效

# ❌ 错误：绘图后配置
plt.plot(...)
_configure_chinese_font()  # 太晚了，不会影响已创建的图表
```

### 2. 避免重复配置

matplotlib 的全局配置在进程生命周期内持久存在，无需重复配置：

```python
# ✅ 正确：只配置一次
visualizer1 = FactorVisualizer()  # 配置字体
visualizer2 = FactorVisualizer()  # 复用配置

# ❌ 不必要：每次绘图前都配置
for factor in factors:
    _configure_chinese_font()  # 浪费性能
    plot_factor(factor)
```

### 3. 抑制字体查找警告

matplotlib 会在查找字体时输出大量日志，可以通过以下方式过滤：

```bash
# 方法1: grep 过滤
python script.py 2>&1 | grep -v "^findfont:"

# 方法2: Python 代码中抑制
import warnings
warnings.filterwarnings('ignore')
```

### 4. 检查系统字体

如果中文仍然显示不正常，检查系统是否安装了中文字体：

```python
# 列出系统所有可用字体
import matplotlib.font_manager as fm
fonts = [f.name for f in fm.fontManager.ttflist]
chinese_fonts = [f for f in fonts if any(c in f for c in ['SC', 'Hei', 'Song', 'YaHei'])]
print(chinese_fonts)
```

## 故障排除

### 问题1: 仍然显示方框

**可能原因**:
- 系统未安装任何中文字体
- 字体路径问题
- matplotlib 缓存问题

**解决方案**:
```bash
# 1. 清除 matplotlib 缓存
rm -rf ~/.matplotlib

# 2. 检查字体是否安装
# macOS: 打开"字体册"查看
# Windows: C:\Windows\Fonts
# Linux: fc-list | grep -i chinese

# 3. 手动安装中文字体
# macOS: 已内置
# Windows: 已内置
# Linux: sudo apt-get install fonts-wqy-microhei
```

### 问题2: 负号显示为方框

**解决方案**:
```python
mpl.rcParams['axes.unicode_minus'] = False
```

### 问题3: 警告信息过多

**解决方案**:
```python
import warnings
warnings.filterwarnings('ignore')

# 或在命令行过滤
python script.py 2>&1 | grep -v "^findfont:"
```

## 技术总结

| 层面 | 策略 | 效果 |
|------|------|------|
| **检测** | `platform.system()` 跨平台检测 | 自动适配 macOS/Windows/Linux |
| **字体** | 优先级列表 + 回退机制 | 总能找到可用中文字体 |
| **配置** | matplotlib 全局 rcParams | 一次配置，全局生效 |
| **时机** | 类初始化时配置 | 确保绘图前配置完成 |
| **测试** | 4 种典型图表验证 | 覆盖所有中文显示场景 |

## 扩展场景

### 在其他可视化模块中复用

如需在新的可视化模块中使用相同策略：

```python
from visualization.factor_visualizer import FactorVisualizer

class MyVisualizer:
    def __init__(self):
        # 方法1: 继承 FactorVisualizer
        # 自动获得字体配置

        # 方法2: 复制字体配置代码
        self._configure_chinese_font()

    def _configure_chinese_font(self):
        """复制 FactorVisualizer 的字体配置逻辑"""
        # ... (同上)
```

### 支持其他语言

扩展支持日文、韩文等：

```python
def _configure_cjk_font(self):
    """配置中日韩字体"""
    system = platform.system()

    if system == 'Darwin':
        fonts = [
            'PingFang SC',      # 简体中文
            'PingFang TC',      # 繁体中文
            'Hiragino Sans',    # 日文
            'Apple SD Gothic Neo'  # 韩文
        ]
    # ...
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `visualization/factor_visualizer.py:75-93` | 字体配置实现 |
| `scripts/test_visualization_font.py` | 字体测试脚本 |
| `visualization/CLAUDE.md` | 可视化模块文档 |

## 参考资源

- [Matplotlib 字体配置官方文档](https://matplotlib.org/stable/tutorials/text/text_props.html)
- [Python platform 模块文档](https://docs.python.org/3/library/platform.html)
- [常见中文字体列表](https://en.wikipedia.org/wiki/List_of_CJK_fonts)

---

**更新日期**: 2026-02-04
**维护者**: Factor Regression System Team
**状态**: ✅ 已验证生效
