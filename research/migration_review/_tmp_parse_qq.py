import re,json
raw=open('reports/工商银行/_tmp_qq_quote.txt','rb').read().decode('gbk')
quotes={}
for code in ['sh601398','hk01398']:
 m=re.search(r'v_'+code+r'="(.*?)";',raw,re.S)
 fields=m.group(1).split('~')
 quotes[code]=fields
 print('\n',code,'len',len(fields))
 for i,v in enumerate(fields[:90]):
  print(i,repr(v))
open('reports/工商银行/_tmp_qq_quote.json','w',encoding='utf-8').write(json.dumps(quotes,ensure_ascii=False,indent=2))