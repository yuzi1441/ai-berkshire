import requests, json, re
headers={'User-Agent':'Mozilla/5.0'}
s=requests.Session(); s.trust_env=False
for url in ['https://push2.eastmoney.com/api/qt/stock/get?secid=1.600900&fields=f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f84,f85,f116,f117,f167,f168,f162,f167,f173,f107','https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&filter=(SECUCODE%3D%22600900.SH%22)(REPORT_TYPE%3D%22%E5%B9%B4%E6%8A%A5%22)&p=1&ps=5&sr=-1&st=REPORT_DATE&source=HSF10&client=PC']:
    r=s.get(url,headers=headers,timeout=20)
    print('URL',url,'status',r.status_code)
    print(r.text[:1200])
