import urllib.request, json, re
urls=[
('sina_sh','https://hq.sinajs.cn/list=sh601398'),
('sina_hk','https://hq.sinajs.cn/list=hk01398'),
('tencent_sh','https://qt.gtimg.cn/q=sh601398'),
('tencent_hk','https://qt.gtimg.cn/q=hk01398'),
('em_mob','https://82.push2.eastmoney.com/api/qt/stock/get?secid=1.601398&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f174,f115,f128,f152'),
]
for name,u in urls:
    print('---',name,u)
    try:
        req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
        data=urllib.request.urlopen(req,timeout=20).read()
        for enc in ['gbk','utf-8']:
            try:
                s=data.decode(enc); print(s[:1000]); break
            except: pass
    except Exception as e: print('ERR',repr(e))