import requests
urls=[
 'https://hq.sinajs.cn/list=sh688271',
 'https://qt.gtimg.cn/q=sh688271',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.688271&fields=f43,f57,f58,f60,f46,f44,f45,f47,f48,f116,f117,f162,f167,f168,f169,f170,f171,f172,f173,f84,f85,f86,f127,f9,f23,f20,f21,f13,f14,f15,f16,f17,f18,f10,f8,f6,f2,f3'
]
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}
for u in urls:
    print('\nURL',u)
    try:
        r=requests.get(u,headers=headers,timeout=15)
        print(r.status_code, r.text[:2000])
    except Exception as e: print('ERR',repr(e))
