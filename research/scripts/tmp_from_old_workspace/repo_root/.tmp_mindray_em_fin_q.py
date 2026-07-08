import subprocess, json, urllib.parse
base='https://datacenter.eastmoney.com/securities/api/data/get'
for rpt in ['一季报','中报','三季报','年报']:
 params={
  'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL',
  'filter':f'(SECUCODE="300760.SZ")(REPORT_TYPE="{rpt}")',
  'p':'1','ps':'3','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'
 }
 url=base+'?'+urllib.parse.urlencode(params)
 raw=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','User-Agent: Mozilla/5.0',url])
 data=json.loads(raw.decode('utf-8'))
 print('\n',rpt)
 for r in data.get('result',{}).get('data',[])[:3]:
  keys=['REPORT_DATE','REPORT_DATE_NAME','TOTALOPERATEREVE','PARENTNETPROFIT','TOTALOPERATEREVETZ','PARENTNETPROFITTZ','EPSJB','ROEJQ','XSMLL','XSJLL']
  print({k:r.get(k) for k in keys})
