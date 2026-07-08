import requests,json,re
s=requests.Session(); s.trust_env=False
url='https://datacenter-web.eastmoney.com/api/data/v1/get'
params_list=[
 {'reportName':'RPT_SHAREBONUS_DET','columns':'ALL','filter':'(SECURITY_CODE="601398")','pageNumber':'1','pageSize':'20','sortColumns':'REPORT_DATE','sortTypes':'-1','source':'WEB','client':'WEB'},
 {'reportName':'RPT_SHAREBONUS_DET','columns':'ALL','filter':'(SECURITY_CODE="601398")','pageNumber':'1','pageSize':'20','sortColumns':'EX_DIVIDEND_DATE','sortTypes':'-1','source':'WEB','client':'WEB'},
 {'reportName':'RPT_SHAREBONUS_DET','columns':'ALL','filter':'(SECURITY_CODE="601398")','pageNumber':'1','pageSize':'50','source':'WEB','client':'WEB'},
]
for p in params_list:
 r=s.get(url,params=p,headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'},timeout=20)
 print('status',r.status_code,r.url[:200],r.text[:100])
 try:
  js=r.json(); data=js.get('result',{}).get('data',[]); print('len',len(data));
  for d in data[:5]: print(d)
 except Exception as e: print('err',e)