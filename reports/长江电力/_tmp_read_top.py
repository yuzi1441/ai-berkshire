from pathlib import Path
for name in ['长江电力-financial-analyst-20260707.md','长江电力投资研究报告.md']:
 t=Path(name).read_text(encoding='utf-8')
 print('\n###', name)
 print(t[:9000])
