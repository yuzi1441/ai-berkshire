from pathlib import Path
for name in ['长江电力投资研究报告.md','长江电力-earnings-最新-巴菲特.md','巴菲特Checklist-长江电力.md','长江电力-business-analyst-商业模式护城河分析-20260707.md']:
 p=Path(name)
 print('\n===== ', name, p.exists(), p.stat().st_size if p.exists() else None, '====')
 if p.exists():
  t=p.read_text(encoding='utf-8')
  print(t[:5000])
