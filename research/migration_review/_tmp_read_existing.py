from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire')
for rel in ['reports/联影医疗/联影医疗-management-20260706.md','reports/联影医疗/联影医疗研究报告-20260706.md','reports/联影医疗/audit_verdict_20260706.txt']:
    p=base/rel
    print('\n---',rel,p.exists(),p.stat().st_size if p.exists() else None,'---')
    if p.exists(): print(p.read_text(encoding='utf-8')[:3500])
