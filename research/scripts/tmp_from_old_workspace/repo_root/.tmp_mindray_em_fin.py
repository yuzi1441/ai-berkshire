import subprocess, json, urllib.parse
base='https://datacenter.eastmoney.com/securities/api/data/get'
params={
 'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL',
 'filter':'(SECUCODE="300760.SZ")(REPORT_TYPE="年报")',
 'p':'1','ps':'10','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'
}
url=base+'?'+urllib.parse.urlencode(params)
raw=subprocess.check_output(['curl.exe','-s','--noproxy','*','-H','User-Agent: Mozilla/5.0',url])
text=raw.decode('utf-8')
print(text[:500])
data=json.loads(text)
for r in data.get('result',{}).get('data',[]):
    keys=['REPORT_DATE','REPORT_DATE_NAME','TOTALOPERATEREVE','PARENTNETPROFIT','TOTALOPERATEREVETZ','PARENTNETPROFITTZ','EPSJB','BPS','ROEJQ','XSMLL','XSJLL','TOTALDEBT','ZCFZL']
    print({k:r.get(k) for k in keys})
