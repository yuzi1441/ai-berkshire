from pathlib import Path
files=[
 r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\长江电力\长江电力-business-analyst-商业模式护城河分析-20260707.md',
 r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\长江电力\industry-researcher_长江电力_水电电力行业分析_2026-07-07.md',
]
for f in files:
 p=Path(f); t=p.read_text(encoding='utf-8')
 print('\n===== ', p.name, len(t), '====')
 for key in ['一页结论','总体结论','评分','事实与推断边界','同业对比表']:
  i=t.find(key)
  if i>=0:
   print('\n--', key, '--')
   print(t[max(0,i-500):i+1500])
   break
