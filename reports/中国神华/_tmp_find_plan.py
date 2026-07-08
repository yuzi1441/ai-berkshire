from pathlib import Path
text=Path('_extract_business.txt').read_text(encoding='utf-8')
for kw in ['2026年度经营计划','经营计划','业务计划','2026年目标','2026 年目标','本集团2026年度']:
 print('KW',kw, text.find(kw))
 if text.find(kw)>=0:
  idx=text.find(kw); print(text[max(0,idx-500):idx+3000])
