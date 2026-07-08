import requests, re, json
url='https://webf10.gw.com.cn/SZ/B10/SZ000400_B10.html'
for u in [url,'https://f10.eastmoney.com/f10_v2/FinanceAnalysis.aspx?code=sz000400','https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=SZ000400']:
 print('---',u)
 try:
  r=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=15)
  print(r.status_code, r.encoding, r.apparent_encoding, len(r.text))
  print(r.text[:1000])
  open('tmp_web_'+re.sub(r'\W+','_',u[-30:])+'.html','w',encoding='utf-8').write(r.text)
 except Exception as e: print(type(e),e)