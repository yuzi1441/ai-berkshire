import re,json
raw=open('reports/工商银行/_tmp_qq_peers.txt','rb').read().decode('gbk')
out=[]
for code in ['sh601398','sh601939','sh601288','sh601988','sh601328','sh600036']:
 m=re.search(r'v_'+code+r'="(.*?)";',raw,re.S)
 if not m: continue
 f=m.group(1).split('~')
 out.append({'code':f[2],'name':f[1],'price':f[3],'date':f[30],'pe':f[39],'mkt_cap_yi':f[45],'pb':f[46],'high52':f[47],'low52':f[48],'shares':f[73] if len(f)>73 else ''})
print(json.dumps(out,ensure_ascii=False,indent=2))
open('reports/工商银行/_tmp_peer_quotes.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2))