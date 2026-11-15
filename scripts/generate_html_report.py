"""
重新渲染网页版报告

[INPUT]: results/report_data.json (由 scripts/run_evaluation.py 生成)
[OUTPUT]: results/report.html
[POS]: 只重新渲染, 不重新回测。改了网页模板 (visualization/report_template.html) 之后用它,
       几秒钟就能看到效果。要更新数字请运行 scripts/run_evaluation.py。

[PROTOCOL]:
1. 这里不计算任何结果, 只把已有的 JSON 填进模板
2. 逻辑变更时同步更新此头部

使用方法:
    python scripts/generate_html_report.py
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from visualization import html_report


def main(output_dir: str = 'results') -> Path:
    data_file = project_root / output_dir / html_report.REPORT_DATA_FILE
    if not data_file.exists():
        raise FileNotFoundError(
            f"找不到 {data_file.relative_to(project_root)}，请先运行 python scripts/run_evaluation.py"
        )
    report_data = json.loads(data_file.read_text(encoding='utf-8'))

    html_file = project_root / output_dir / html_report.REPORT_HTML_FILE
    html_file.write_text(html_report.render_html(report_data), encoding='utf-8')
    print(f"✅ 网页版报告已生成: {html_file.relative_to(project_root)}")
    return html_file


if __name__ == '__main__':
    main()
