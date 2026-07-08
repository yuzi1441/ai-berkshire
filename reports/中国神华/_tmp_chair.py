from pathlib import Path
text=Path('_annual_full.txt').read_text(encoding='utf-8')
for kw in ['董事长','吕志韧', '董事会主席', '选举董事长', '未设董事长']:
 print('\n###',kw)
 start=0;c=0
 while True:
  idx=text.find(kw,start)
  if idx<0 or c>=8: break
  print(text[max(0,idx-350):idx+700].replace('\n',' ')[:1400]); print('---')
  start=idx+len(kw); c+=1
