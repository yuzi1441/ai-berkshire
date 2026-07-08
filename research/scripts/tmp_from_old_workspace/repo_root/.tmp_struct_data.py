import requests,json,decimal,csv,pathlib
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sz002028.html'}
root=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources')
# main annual from eastmoney
params={'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE="002028.SZ")(REPORT_TYPE="年报")','p':'1','ps':'8','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
js=requests.get('https://datacenter.eastmoney.com/securities/api/data/get',params=params,headers=headers,timeout=20).json()
data=js['result']['data']
(root/'eastmoney_main_annual.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('annual main')
for r in data:
    print(r['REPORT_DATE'][:10], r.get('TOTALOPERATEREVE'), r.get('PARENTNETPROFIT'), r.get('KCFJCXSYJLR'), r.get('JYXJLYYSR'), r.get('XSMLL'), r.get('ROEJQ'), r.get('ZCFZL'), r.get('EPSJB'), r.get('BPS'))
# reports annual cash/balance/income
for reportName in ['RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_INCOME','RPT_DMSK_FN_CASHFLOW']:
    params={'reportName':reportName,'columns':'ALL','quoteColumns':'','filter':'(SECURITY_CODE="002028")(REPORT_TYPE_CODE="001")','pageNumber':'1','pageSize':'8','sortTypes':'-1','sortColumns':'REPORT_DATE','source':'HSF10','client':'PC'}
    j=requests.get('https://datacenter.eastmoney.com/securities/api/data/v1/get',params=params,headers=headers,timeout=20).json()
    (root/(reportName+'.json')).write_text(json.dumps(j.get('result',{}).get('data',[]),ensure_ascii=False,indent=2),encoding='utf-8')
print('saved')
# peers quote parse
peers={'思源电气':'sz002028','平高电气':'sh600312','中国西电':'sh601179','许继电气':'sz000400','国电南瑞':'sh600406','特变电工':'sh600089'}
print('peers')
for name,code in peers.items():
    raw=requests.get('https://qt.gtimg.cn/q='+code,headers=headers,timeout=20).content.decode('gbk')
    f=raw.split(chr(34))[1].split('~')
    print(name, f[2], 'price',f[3], 'chg%',f[32], 'pe',f[39], 'mc_yi',f[45], 'pb',f[46])
