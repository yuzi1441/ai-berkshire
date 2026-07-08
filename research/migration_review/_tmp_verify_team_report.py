from pathlib import Path
report = Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\联影医疗\联影医疗投资研究报告_team-20260706.md')
text = report.read_text(encoding='utf-8')
checks = ['联影医疗（688271.SH）投资研究报告','综合评分：3.5 / 5','106.75 元','879.79 亿元','【准出】' ]
# last check is in verdict file, not report
verdict = Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\联影医疗\audit_verdict_team_20260706.txt').read_text(encoding='utf-8', errors='ignore')
print('report_exists', report.exists())
print('report_size', report.stat().st_size)
print('report_chars', len(text))
for s in checks[:-1]:
    print(s, s in text)
print('audit_pass', '抽检总数: 15' in verdict and '不通过:' in verdict and '【准出】' in verdict)
