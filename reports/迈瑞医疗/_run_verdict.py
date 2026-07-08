from pathlib import Path
import json, subprocess, sys
res=[
  {"id":1,"label":"体外诊断 · 2026Q1收入","reported_value":31.93,"unit":"亿元","fetched_value":31.93,"fetched_source":"迈瑞医疗2026年第一季度报告PDF原文第193行","fetched_value2":31.93,"fetched_source2":"本地PDF抽取文本 sources/mindray_2026_q1.txt 第193行"},
  {"id":2,"label":"生命信息与支持 · 2026Q1收入","reported_value":22.64,"unit":"亿元","fetched_value":22.64,"fetched_source":"迈瑞医疗2026年第一季度报告PDF原文第200行","fetched_value2":22.64,"fetched_source2":"本地PDF抽取文本 sources/mindray_2026_q1.txt 第200行"},
  {"id":11,"label":"海外风险 · 当前证据","reported_value":53.00,"unit":"%","fetched_value":53.00,"fetched_source":"迈瑞医疗2026年第一季度报告PDF原文第178行 国际收入占集团整体收入比重达53%","fetched_value2":53.03,"fetched_source2":"迈瑞医疗2025年年度报告PDF原文 国际业务占比53.03%"}
]
Path('reports/迈瑞医疗/audit_results_2026Q1.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',json.dumps(res,ensure_ascii=False),'--report','reports/迈瑞医疗/迈瑞医疗-earnings-2026Q1.md','--output-json']
p=subprocess.run(cmd, text=True, capture_output=True, encoding='utf-8')
print('returncode', p.returncode)
print(p.stdout)
print(p.stderr)
Path('reports/迈瑞医疗/audit_verdict_2026Q1.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
