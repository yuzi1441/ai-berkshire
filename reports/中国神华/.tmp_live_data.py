import urllib.request, json, re, pathlib, ssl, urllib.parse
from html import unescape
out={}
# Tencent quote
raw=urllib.request.urlopen(urllib.request.Request('http://qt.gtimg.cn/q=sh601088',headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read().decode('gbk')
f=raw.split('"')[1].split('~')
out['tencent_quote']={str(i):v for i,v in enumerate(f)}
# Eastmoney quote try HTTP not HTTPS
url='http://push2.eastmoney.com/api/qt/stock/get?secid=1.601088&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f85,f116,f117,f162,f167,f168,f170,f171,f173,f174,f175,f127,f128,f129,f130'
try:
    data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://quote.eastmoney.com/'}),timeout=20).read().decode('utf-8')
    out['eastmoney_quote_raw']=data
except Exception as e:
    out['eastmoney_quote_error']=repr(e)
# Eastmoney financials annual and q1
for key,report_type in [('em_annual','年报'),('em_q1','一季报')]:
    params={
        'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL',
        'filter':f'(SECUCODE="601088.SH")(REPORT_TYPE="{report_type}")',
        'p':'1','ps':'6','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'
    }
    u='https://datacenter.eastmoney.com/securities/api/data/get?'+urllib.parse.urlencode(params)
    try:
        txt=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}),timeout=30).read().decode('utf-8')
        out[key]=json.loads(txt)
    except Exception as e:
        out[key+'_error']=repr(e)
path=pathlib.Path('sources/live_data.json')
path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(path, path.stat().st_size)
print(json.dumps(out.get('tencent_quote',{}),ensure_ascii=False)[:1000])
print(out.get('eastmoney_quote_raw','')[:500], out.get('eastmoney_quote_error',''))
