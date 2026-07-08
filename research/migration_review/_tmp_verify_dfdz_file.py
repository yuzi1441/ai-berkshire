from pathlib import Path
p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\东方电子\巴菲特Checklist-东方电子.md')
s=p.read_text(encoding='utf-8')
for key in ['巴菲特价值投资买入前 Checklist：东方电子','灰色地带','未通过买入 Checklist','投资第一条规则是不要亏损']:
    print(key, key in s)
print('chars', len(s))
