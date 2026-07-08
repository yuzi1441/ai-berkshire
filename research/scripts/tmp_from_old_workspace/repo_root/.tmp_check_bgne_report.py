from pathlib import Path
p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\百济神州\巴菲特Checklist-百济神州-20260706.md')
s=p.read_text(encoding='utf-8')
keys=['灰色地带 / 当前不通过买入 Checklist','A股估值','镜子测试：未通过','百济神州']
for k in keys:
    print(k, 'OK' if k in s else 'MISSING')
print('chars', len(s))
