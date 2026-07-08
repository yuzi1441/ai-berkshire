import requests, re, json, pathlib
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/sz002270/gp'}
urls=[
 'https://qt.gtimg.cn/q=sz002270',
 'http://qt.gtimg.cn/q=sz002270',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.002270&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171,f113,f114,f115,f135,f136,f137,f163,f164,f169,f152,f120,f121,f122,f130,f131,f132,f133,f134,f135,f138,f139,f140,f141,f142,f143,f144,f145,f146,f149,f161,f292',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.002270&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171,f113,f114,f115,f152'
]
out=pathlib.Path('reports/华明装备/sources/quotes'); out.mkdir(parents=True,exist_ok=True)
for i,u in enumerate(urls):
    try:
        r=s.get(u,headers=headers,timeout=30)
        print('\nURL',u,'status',r.status_code,'ct',r.headers.get('content-type'), 'len',len(r.content))
        txt=r.content.decode('gbk','ignore') if 'qt.gtimg' in u else r.text
        print(txt[:2000])
        (out/f'quote_{i}.txt').write_text(txt,encoding='utf-8')
    except Exception as e: print('ERR',type(e).__name__,e)
