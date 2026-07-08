import requests, json
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'1.601126','fields':'f43,f44,f45,f46,f47,f48,f57,f58,f60,f84,f85,f116,f117,f162,f167,f168,f169,f170,f173,f187,f188,f189,f190,f191,f193'}
r=s.get(url,params=params,headers=headers,timeout=20)
print(r.status_code, r.text[:2000])
# financials q/latest api maybe
url2='https://datacenter.eastmoney.com/securities/api/data/get'
params2={'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE="601126.SH")','p':'1','ps':'10','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
r=s.get(url2,params=params2,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'},timeout=20)
print('fin',r.status_code,r.text[:2000])