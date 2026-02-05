"""
字体配置模块

自动检测系统可用字体，为matplotlib配置中文显示。

[INPUT]:
- 无（自动检测系统字体）

[OUTPUT]:
- matplotlib字体配置

[POS]:
工具层 - 解决中文显示问题

[PROTOCOL]:
1. 自动检测系统中文字体
2. 按优先级配置matplotlib
3. 提供备选方案（下载字体）
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from typing import List, Optional
import platform
import warnings


def get_available_chinese_fonts() -> List[str]:
    """
    获取系统中可用的中文字体列表

    Returns:
    --------
    fonts : list
        可用的中文字体名称列表
    """
    # 常见的中文字体名称（按优先级排序）
    chinese_font_names = [
        # macOS
        'PingFang SC', 'Heiti SC', 'STHeiti', 'Songti SC', 'STSong',
        'Kaiti SC', 'STKaiti', 'Arial Unicode MS',
        # Windows
        'Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi', 'FangSong',
        # Linux
        'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC',
        'Droid Sans Fallback'
    ]

    # 获取matplotlib已知的所有字体
    available_fonts = []
    font_manager = fm.fontManager

    for font_name in chinese_font_names:
        # 检查字体是否在系统中
        font_found = False
        for font in font_manager.ttflist:
            if font_name.lower() in font.name.lower():
                available_fonts.append(font.name)
                font_found = True
                break

        # 如果没找到，尝试findfont
        if not font_found:
            try:
                font_path = fm.findfont(fm.FontProperties(family=font_name))
                if 'ttf' in font_path.lower() and font_name not in available_fonts:
                    available_fonts.append(font_name)
            except:
                continue

    return available_fonts


def configure_chinese_font(verbose: bool = True) -> bool:
    """
    配置matplotlib的中文字体

    Parameters:
    -----------
    verbose : bool
        是否打印配置信息

    Returns:
    --------
    success : bool
        配置是否成功
    """
    # 清除matplotlib字体缓存
    try:
        import matplotlib as mpl
        cache_dir = mpl.get_cachedir()
        import shutil
        import os
        font_cache = os.path.join(cache_dir, 'fontlist-*.json')
        import glob
        for cache_file in glob.glob(font_cache):
            try:
                os.remove(cache_file)
            except:
                pass
    except:
        pass

    # 重新加载字体管理器
    fm._load_fontmanager(try_read_cache=False)

    # 获取可用字体
    available_fonts = get_available_chinese_fonts()

    if not available_fonts:
        if verbose:
            print("⚠️  未检测到系统中文字体")
            print_font_installation_guide()
        return False

    # 配置matplotlib
    # 使用找到的第一个可用字体
    primary_font = available_fonts[0]

    # 设置字体（包含备选方案）
    plt.rcParams['font.sans-serif'] = available_fonts + ['DejaVu Sans', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
    plt.rcParams['font.family'] = 'sans-serif'

    # 强制刷新字体缓存
    plt.rcParams['font.size'] = plt.rcParams['font.size']

    if verbose:
        print(f"✅ 中文字体配置成功: {primary_font}")
        if len(available_fonts) > 1:
            print(f"   备选字体: {', '.join(available_fonts[1:min(3, len(available_fonts))])}")

    return True


def configure_chinese_font_for_specific_system() -> bool:
    """
    根据操作系统配置中文字体（备选方案）

    Returns:
    --------
    success : bool
        配置是否成功
    """
    system = platform.system()

    if system == 'Darwin':  # macOS
        fonts = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS']
    elif system == 'Windows':
        fonts = ['Microsoft YaHei', 'SimHei', 'SimSun']
    elif system == 'Linux':
        fonts = ['WenQuanYi Micro Hei', 'Noto Sans CJK', 'Droid Sans Fallback']
    else:
        fonts = []

    if fonts:
        plt.rcParams['font.sans-serif'] = fonts + ['DejaVu Sans', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False
        return True

    return False


def print_font_installation_guide():
    """打印字体安装指南"""
    system = platform.system()

    print("\n📖 字体安装指南:")
    print("-" * 60)

    if system == 'Darwin':  # macOS
        print("macOS系统通常已预装中文字体，如果未检测到，请尝试：")
        print("1. 打开「字体册」应用")
        print("2. 检查是否安装了 PingFang SC 或 Heiti SC")
        print("3. 如果未安装，从 App Store 下载中文字体")

    elif system == 'Windows':
        print("Windows系统通常已预装中文字体，如果未检测到，请尝试：")
        print("1. 打开「设置」→「时间和语言」→「语言」")
        print("2. 添加中文（简体）语言包")
        print("3. 系统会自动安装微软雅黑等字体")

    elif system == 'Linux':
        print("Linux系统需要手动安装中文字体：")
        print("Ubuntu/Debian:")
        print("  sudo apt-get install fonts-wqy-microhei fonts-wqy-zenhei")
        print("\nFedora/CentOS:")
        print("  sudo yum install wqy-microhei-fonts wqy-zenhei-fonts")

    print("\n或者下载开源中文字体:")
    print("- 文泉驿微米黑: http://wenq.org/wqy2/index.cgi?MicroHei")
    print("- Noto Sans CJK: https://github.com/googlefonts/noto-cjk")
    print("-" * 60)


def test_chinese_display():
    """
    测试中文显示

    创建一个简单的测试图表
    """
    import numpy as np

    # 配置字体
    success = configure_chinese_font(verbose=True)

    if not success:
        print("\n⚠️  尝试使用系统默认配置...")
        configure_chinese_font_for_specific_system()

    # 创建测试图表
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    ax.plot(x, y, label='正弦曲线')
    ax.set_title('中文显示测试图表', fontsize=16, fontweight='bold')
    ax.set_xlabel('横轴（时间）', fontsize=12)
    ax.set_ylabel('纵轴（数值）', fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # 保存测试图
    from pathlib import Path
    test_dir = Path('results/test')
    test_dir.mkdir(parents=True, exist_ok=True)
    save_path = test_dir / 'chinese_font_test.png'

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ 测试图表已保存: {save_path}")
    print("   请打开图片检查中文是否正常显示")

    plt.close()


if __name__ == '__main__':
    """测试字体配置"""
    print("="*60)
    print("字体配置测试")
    print("="*60)

    # 检测可用字体
    print("\n1. 检测系统中文字体...")
    fonts = get_available_chinese_fonts()
    if fonts:
        print(f"   找到 {len(fonts)} 个中文字体:")
        for font in fonts[:5]:
            print(f"   - {font}")
    else:
        print("   未找到中文字体")

    # 配置并测试
    print("\n2. 配置matplotlib中文字体...")
    test_chinese_display()

    print("\n" + "="*60)
