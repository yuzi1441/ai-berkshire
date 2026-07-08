import requests, json, re, sys
urls={
 'eastmoney_a':'https://push2.eastmoney.com/api/qt/stock/get?secid=1.688235&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f84,f85,f168,f169,f170,f171,f162,f167,f127,f164,f163,f152',
 'tencent_a':'https://qt.gtimg.cn/q=sh688235',
 'sina_a':'https://hq.sinajs.cn/list=sh688235',
 'eastmoney_hk':'https://push2.eastmoney.com/api/qt/stock/get?secid=116.06160&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f84,f85,f168,f169,f170,f171,f162,f167,f127,f164,f163,f152',
 'tencent_hk':'https://qt.gtimg.cn/q=hk06160',
 'eastmoney_us':'https://push2.eastmoney.com/api/qt/stock/get?secid=105.ONC&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f84,f85,f168,f169,f170,f171,f162,f167,f127,f164,f163,f152',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'}
for k,u in urls.items():
    print('\n---',k,u)
    try:
        r=requests.get(u,headers=headers,timeout=12)
        print(r.status_code, r.text[:800])
    except Exception as e: print('ERR',e)