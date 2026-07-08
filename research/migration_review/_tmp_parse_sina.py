import re,json
raw=open('reports/工商银行/_tmp_sina_quote.txt','rb').read().decode('gbk')
print(raw[:1000])
for code in ['sh601398','hk01398']:
 m=re.search(r'hq_str_'+code+r'=["\'](.*?)["\'];',raw,re.S)
 if m:
  fields=m.group(1).split(',')
  print('\n',code,len(fields))
  for i,v in enumerate(fields[:60]): print(i,repr(v))