import pandas as pd, pathlib, json, math, subprocess, os, sys
base=pathlib.Path('data/oriental_electronics')
absdf=pd.read_csv(base/'financial_abstract_000682.csv')
# make metric dict from abstract
metrics={}
for _,r in absdf.iterrows():
    m=str(r['指标'])
    if m not in metrics: metrics[m]={}
    for c in ['20260331','20251231','20241231','20231231','20221231','20211231']:
        if c in r and pd.notna(r[c]): metrics[m][c]=float(r[c])
# statement data
profit=pd.read_csv(base/'profit_em_SZ000682.csv')
bal=pd.read_csv(base/'balance_em_SZ000682.csv')
cf=pd.read_csv(base/'cashflow_em_SZ000682.csv')
# helper first row by name
rows={}
for dfname,df in [('profit',profit),('balance',bal),('cashflow',cf)]:
    for _,r in df.head(10).iterrows():
        rows[(dfname,r['REPORT_DATE_NAME'])]=r.to_dict()
# quotes parse from saved? fetch live
import requests, re
quotes={}
for src,url in {'sina':'https://hq.sinajs.cn/list=sz000682','tencent':'https://qt.gtimg.cn/q=sz000682'}.items():
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15)
    text=r.content.decode('gb18030','ignore')
    quotes[src]=text
# parse
sina_fields=re.search(r'"(.*)"',quotes['sina']).group(1).split(',')
tx_fields=re.search(r'"(.*)"',quotes['tencent']).group(1).split('~')
price_sina=float(sina_fields[3]); date_sina=sina_fields[30]+' '+sina_fields[31]
price_tx=float(tx_fields[3]); mcap_tx=float(tx_fields[45]) # 亿? from quote string 165.83
float_mcap_tx=float(tx_fields[46])
shares_total=float(tx_fields[70]); shares_float=float(tx_fields[71])
# if shares fields are raw shares
print('parsed quote',price_sina, date_sina, price_tx, mcap_tx, shares_total)
# compute derived
price=(price_sina+price_tx)/2
shares=shares_total
mcap=price*shares
eps2025=metrics['基本每股收益']['20251231']
bvps2025=metrics['每股净资产']['20251231']
revps=metrics['营业总收入']['20251231']/shares
ocfps=metrics['经营现金流量净额']['20251231']/shares
# dividend from 2025 distribution? 10转? annual report says? 2025 profit distribution: likely 10派1.5? Use EM? fetch notices? We'll omit exact or use current div yield quote tencent field 1.68? unsure.
summary={
 'quote':{'sina_price':price_sina,'sina_time':date_sina,'tencent_price':price_tx,'avg_price':price,'tencent_total_mcap_yi':mcap_tx,'total_shares':shares,'calc_mcap_yuan':mcap},
 'derived':{'eps2025':eps2025,'bvps2025':bvps2025,'revenue_per_share_2025':revps,'ocf_per_share_2025':ocfps,'pe':price/eps2025,'pb':price/bvps2025,'ps':price/revps,'pcfo':price/ocfps},
 'metrics':metrics
}
(base/'summary_metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary['quote'],ensure_ascii=False,indent=2))
print(json.dumps(summary['derived'],ensure_ascii=False,indent=2))
