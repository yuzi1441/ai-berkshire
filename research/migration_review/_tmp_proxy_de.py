import os
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']:
    print(k, os.environ.get(k))
import requests
for url in ['http://push2.eastmoney.com/api/qt/stock/get','https://push2.eastmoney.com/api/qt/stock/get','http://hq.sinajs.cn/list=sz000682','https://hq.sinajs.cn/list=sz000682']:
    try:
        r=requests.get(url, params={'secid':'0.000682','fields':'f43,f57,f58,f60,f84,f116,f162'} if 'eastmoney' in url else None, headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}, timeout=10, proxies={'http':None,'https':None})
        print('\nURL',url,'status',r.status_code,'ct',r.headers.get('content-type'),'text',r.text[:300])
    except Exception as e:
        print('\nURL',url,'ERR',repr(e))