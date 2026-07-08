import re
quotes=open('reports/长江电力/sources/tencent_quotes_20260706.txt',encoding='utf-8').read()
for sym in ['600900','600905','600025','600886']:
 m=re.search(r'v_sh%s="([^"]+)"'%sym,quotes); f=m.group(1).split('~')
 print('\n',sym,len(f),f[1])
 for i,x in enumerate(f):
  if i<95:
   print(i,x)
