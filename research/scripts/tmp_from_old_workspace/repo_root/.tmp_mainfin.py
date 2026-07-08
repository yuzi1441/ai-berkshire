import requests,json
s=requests.Session(); s.trust_env=False
url='https://datacenter-web.eastmoney.com/api/data/v1/get?sortColumns=REPORT_DATE&sortTypes=-1&pageSize=20&pageNumber=1&reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL&filter=(SECURITY_CODE%3D%22002270%22)'
j=s.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'},timeout=20).json()
for d in j['result']['data'][:12]:
 keys=['REPORT_DATE','REPORT_TYPE','NOTICE_DATE','EPSJB','BPS','MGJYXJJE','TOTALOPERATEREVE','MLR','PARENTNETPROFIT','KCFJCXSYJLR','TOTALOPERATEREVETZ','PARENTNETPROFITTZ','ROEJQ','ROEKCJQ','XSMLL','XSJLL','ZCFZL','JYXJLL','TOTAL_ASSETS','TOTAL_LIABILITIES']
 print({k:d.get(k) for k in keys if k in d})