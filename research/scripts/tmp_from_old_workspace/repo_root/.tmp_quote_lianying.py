import requests, json, re, pathlib, pandas as pd
code='688271'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
urls={
 'eastmoney_quote': f'https://push2.eastmoney.com/api/qt/stock/get?secid=1.{code}&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f71,f84,f85,f86,f116,f117,f162,f167,f168,f169,f170,f171,f173,f187,f188,f189,f190,f292',
 'eastmoney_kline': f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.{code}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260701&end=20260706',
 'sina_quote': f'https://hq.sinajs.cn/list=sh{code}',
 'tencent_quote': f'https://qt.gtimg.cn/q=sh{code}',
}
for name,url in urls.items():
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print('\n---',name,r.status_code,r.headers.get('content-type'),len(r.text))
        print(r.text[:1000])
        pathlib.Path(f'data/lianying_{name}.txt').write_text(r.text,encoding='utf-8')
    except Exception as e:
        print(name,'ERR',repr(e))
