import json
import urllib.parse
import urllib.request
codes=['002050.SZ','300124.SZ','688017.SH','601689.SH','002747.SZ','300024.SZ','002472.SZ','002444.SZ','688322.SH','603662.SH','002896.SZ','603728.SH']
headers={'User-Agent':'Mozilla/5.0'}
rows=[]
for sec in codes:
    params={'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':f'(SECUCODE="{sec}")(REPORT_TYPE="年报")','p':'1','ps':'2','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
    url='https://datacenter.eastmoney.com/securities/api/data/get?'+urllib.parse.urlencode(params)
    try:
        req=urllib.request.Request(url,headers=headers)
        data=json.loads(urllib.request.urlopen(req,timeout=15).read().decode('utf-8'))
        rows.append({'sec':sec,'items':data.get('result',{}).get('data',[])[:2]})
    except Exception as e:
        rows.append({'sec':sec,'error':str(e)})
open('robot_eastmoney_financials_20260706.json','w',encoding='utf-8').write(json.dumps(rows,ensure_ascii=False,indent=2))
print('wrote',len(rows))
