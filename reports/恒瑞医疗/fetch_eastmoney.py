import urllib.request, urllib.parse, json
urls=[]
base='https://datacenter.eastmoney.com/securities/api/data/get'
params={
 'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE="600276.SH")(REPORT_TYPE="年报")','p':'1','ps':'8','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'
}
urls.append(base+'?'+urllib.parse.urlencode(params))
params2={
 'type':'RPT_DMSK_FN_BALANCE','sty':'APP_F10_MAIN','filter':'(SECUCODE="600276.SH")','p':'1','ps':'5','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'
}
urls.append(base+'?'+urllib.parse.urlencode(params2))
for url in urls:
  print('\nURL',url[:120])
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/','Accept':'application/json,text/plain,*/*'})
  try:
    txt=urllib.request.urlopen(req,timeout=20).read().decode('utf-8')
    print(txt[:1000])
    obj=json.loads(txt)
    print('keys', obj.keys(), 'count', len((obj.get('result') or {}).get('data') or []))
    for r in ((obj.get('result') or {}).get('data') or [])[:3]:
      print({k:r.get(k) for k in ['REPORT_DATE','REPORT_DATE_NAME','TOTALOPERATEREVE','PARENTNETPROFIT','NETCASHFLOWOPERATE','EPSJB','BPS','ROEJQ','TOTALOPERATEREVETZ','PARENTNETPROFITTZ']})
  except Exception as e: print('ERR',repr(e))