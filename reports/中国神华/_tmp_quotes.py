import requests,re,json
urls={
'sina_sh':'https://hq.sinajs.cn/list=sh601088',
'sina_hk':'https://hq.sinajs.cn/list=hk01088',
'tencent_sh':'https://qt.gtimg.cn/q=sh601088',
'tencent_hk':'https://qt.gtimg.cn/q=hk01088',
}
for name,url in urls.items():
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15)
 # try gbk
 for enc in ['gbk','utf-8']:
  try:
   txt=r.content.decode(enc)
   break
  except: pass
 print('\n',name,r.status_code,txt[:500])
