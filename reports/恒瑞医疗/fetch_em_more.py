import urllib.request, urllib.parse, json
queries=[
 ('现金流','RPT_DMSK_FN_CASHFLOW','APP_F10_MAIN'),
 ('利润','RPT_DMSK_FN_INCOME','APP_F10_MAIN'),
 ('资产','RPT_DMSK_FN_BALANCE','ALL'),
 ('现金ALL','RPT_DMSK_FN_CASHFLOW','ALL'),
]
base='https://datacenter.eastmoney.com/securities/api/data/get'
for name,typ,sty in queries:
 params={'type':typ,'sty':sty,'filter':'(SECUCODE="600276.SH")','p':'1','ps':'2','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
 url=base+'?'+urllib.parse.urlencode(params)
 print('\n',name,typ,sty)
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'})
 try:
  txt=urllib.request.urlopen(req,timeout=20).read().decode('utf-8')
  print(txt[:700])
  obj=json.loads(txt); data=(obj.get('result') or {}).get('data') or []
  print('count',len(data),'keys', list(data[0].keys())[:20] if data else [])
 except Exception as e: print('ERR',repr(e))