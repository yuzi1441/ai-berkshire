from pathlib import Path
text=Path('sources/联影医疗/2025年报.pdf.txt').read_text(encoding='utf-8')
for pat in ['研发投入情况表','研发投入总额','研发人员数量','开发支出','研发费用','研发费用资本化','公司研发投入情况']:
 print('\n###',pat)
 idx=0; n=0
 while True:
  i=text.find(pat, idx)
  if i<0: break
  print('@',i,'\n',text[max(0,i-600):i+1800])
  idx=i+len(pat); n+=1
  if n>=5: break
