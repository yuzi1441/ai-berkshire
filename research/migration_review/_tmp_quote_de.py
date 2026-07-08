import requests, re, json, datetime
# Eastmoney quote
em_url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'0.000682','fields':'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f71,f84,f85,f86,f107,f116,f117,f162,f167,f168,f169,f170,f171,f173,f184'}
r=requests.get(em_url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=20)
print('eastmoney',r.status_code,r.text[:500])
print(json.dumps(r.json().get('data'),ensure_ascii=False,indent=2))
# Sina quote
sina='https://hq.sinajs.cn/list=sz000682'
r=requests.get(sina,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
r.encoding='gbk'
print('sina',r.status_code,r.text[:500])
# Eastmoney financial summary maybe
url='https://datacenter-web.eastmoney.com/api/data/v1/get'
params={'sortColumns':'REPORT_DATE','sortTypes':'-1','pageSize':'10','pageNumber':'1','reportName':'RPT_LICO_FN_CPD','columns':'ALL','filter':'(SECURITY_CODE="000682")'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'},timeout=20)
print('em_fin',r.status_code,r.text[:300])
try:
 print(json.dumps(r.json().get('result',{}).get('data',[])[:3],ensure_ascii=False,indent=2)[:3000])
except Exception as e: print(e)