import requests, json, re
urls={
'em_spot':'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600276&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f173,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198,f199,f152',
'em_kline':'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600276&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116&klt=101&fqt=0&beg=20260701&end=20260706',
'em_valuation':'https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_VALUEANALYSIS_DET&columns=ALL&filter=(SECURITY_CODE="600276")',
}
s=requests.Session(); s.trust_env=False
for name,url in urls.items():
    try:
        r=s.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sh600276.html'})
        print('\n',name,r.status_code,r.headers.get('content-type'),r.text[:1000])
    except Exception as e: print(name,type(e).__name__,e)
