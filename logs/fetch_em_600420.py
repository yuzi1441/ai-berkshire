import urllib.request, urllib.parse, json, pathlib, re
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
# quote from Tencent
url='https://qt.gtimg.cn/q=sh600420'
raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read()
try: txt=raw.decode('gbk')
except: txt=raw.decode('utf-8')
print('QQ raw',txt[:300])
fields=txt.split('"')[1].split('~')
quote={'name':fields[1],'code':fields[2],'price':fields[3],'change_pct':fields[32],'market_cap_yi':fields[45],'float_cap_yi':fields[44],'pe':fields[39],'pb':fields[46],'turnover_rate':fields[38]}
print('QUOTE',json.dumps(quote,ensure_ascii=False))
# EM financial main annual
params={'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE="600420.SH")(REPORT_TYPE="年报")','p':'1','ps':'5','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
url='https://datacenter.eastmoney.com/securities/api/data/get?'+urllib.parse.urlencode(params)
text=urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20).read().decode('utf-8')
data=json.loads(text)
rows=data.get('result',{}).get('data',[])
for r in rows[:5]:
    print('EM',r.get('REPORT_DATE')[:10],r.get('TOTALOPERATEREVE'),r.get('PARENTNETPROFIT'),r.get('NETCASHFLOWOPERATE'),r.get('EPSJB'),r.get('ROEJQ'))
path=pathlib.Path('data/国药现代'); path.mkdir(parents=True,exist_ok=True); (path/'em_financials_quote_20260708.json').write_text(json.dumps({'quote':quote,'financials':rows},ensure_ascii=False,indent=2),encoding='utf-8')
