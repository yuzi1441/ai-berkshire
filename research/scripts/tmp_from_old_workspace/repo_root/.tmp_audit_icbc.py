import json, subprocess, sys
from pathlib import Path
results=[
 {"id":5,"label":"数据截止","reported_value":2026,"unit":"","fetched_value":2026,"fetched_source":"本地Get-Date/报告头，2026-07-07","fetched_value2":2026,"fetched_source2":"工商银行2026Q1报告标题/披露年份"},
 {"id":1,"label":"营业收入 · 数值","reported_value":2303.70,"unit":"亿元","fetched_value":2303.70,"fetched_source":"工商银行2026年第一季度报告A股官方PDF，营业收入230,370百万元","fetched_value2":2303.70,"fetched_source2":"子Agent/巨潮公告PDF同口径交叉核验"},
 {"id":3,"label":"各类资产减值损失 · 数值","reported_value":694.46,"unit":"亿元","fetched_value":694.46,"fetched_source":"工商银行2026年第一季度报告A股官方PDF，计提各类资产减值损失694.46亿元","fetched_value2":694.46,"fetched_source2":"利润表信用减值损失692.94亿元+其他资产减值损失1.52亿元=694.46亿元"},
]
js=json.dumps(results,ensure_ascii=False)
cmd=[sys.executable,'tools/report_audit.py','verdict','--report','reports/工商银行/工商银行-earnings-2026Q1.md','--results',js]
print('RUN',cmd[:4], '...')
cp=subprocess.run(cmd,cwd=Path.cwd(),text=True,encoding='utf-8',capture_output=True)
print(cp.stdout)
print(cp.stderr,file=sys.stderr)
sys.exit(cp.returncode)