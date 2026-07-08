import requests, pathlib, re
code='688271'
urls={
'eastmoney_quote_no_noproxy': f'https://push2.eastmoney.com/api/qt/stock/get?secid=1.{code}&fields=f43,f57,f58,f60,f84,f85,f116,f117,f162,f167,f168,f170,f292',
'netease_quote': f'https://api.money.126.net/data/feed/060{code},money.api',
'qq_quote': f'https://qt.gtimg.cn/q=sh{code}',
'xueqiu_quote': f'https://stock.xueqiu.com/v5/stock/quote.json?symbol=SH{code}&extend=detail',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
for name,url in urls.items():
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print('\n',name,r.status_code,r.headers.get('content-type'),len(r.content))
        print(r.text[:500])
        pathlib.Path(f'data/lianying_{name}.txt').write_text(r.text,encoding='utf-8',errors='ignore')
    except Exception as e: print(name,'ERR',repr(e))
