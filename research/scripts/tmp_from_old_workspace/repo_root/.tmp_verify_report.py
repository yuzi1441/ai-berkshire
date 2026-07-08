from pathlib import Path
p=Path('reports/思源电气/思源电气研究报告-20260706.md')
text=p.read_text(encoding='utf-8')
checks=['174.20 元','1,363.24 亿元','215.39','31.50','58.03','+85.84%','好公司，但当前价格缺安全边际','report_audit.py extract --dry-run']
print('path', p.resolve())
print('chars', len(text), 'lines', text.count('\n')+1)
for c in checks:
    print(c, 'OK' if c in text else 'MISSING')
print('head:')
print('\n'.join(text.splitlines()[:12]))
