from pathlib import Path
p=Path('长江电力研究报告-20260707.md')
text=p.read_text(encoding='utf-8')
keys=['长江电力（600900.SH）研究报告','AI研究偏见自觉','四维评分总表','巴菲特买入前 Checklist','最终投资建议','准出']
for k in keys:
 print(f'KEY {k}:', k in text)
print('chars', len(text))
