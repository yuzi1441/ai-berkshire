import re, requests, json, math, pathlib, subprocess, sys
from decimal import Decimal
import akshare as ak
import pandas as pd
root=pathlib.Path.cwd(); outdir=root/'reports'/'平高电气'; outdir.mkdir(parents=True, exist_ok=True)
# Extract AkShare financial abstract
fin=ak.stock_financial_abstract(symbol='600312')
metrics=['营业总收入','营业成本','归母净利润','扣非净利润','经营现金流量净额','基本每股收益','每股净资产','毛利率','销售净利率','资产负债率','净资产收益率(ROE)','总资产报酬率(ROA)','期间费用率','应收账款周转率','存货周转率']
years=['20251231','20241231','20231231','20221231','20211231','20260331','20250331']
rows=[]
for m in metrics:
    sub=fin[fin['指标']==m]
    if not sub.empty:
        row=sub.iloc[0]
        rows.append({'指标':m, **{y: row.get(y) for y in years if y in fin.columns}})
fin_df=pd.DataFrame(rows)
fin_df.to_csv(outdir/'平高电气_akshare_financial_abstract.csv', index=False, encoding='utf-8-sig')
print(fin_df.to_string(index=False))
# Quote from Sina/Tencent
s=requests.Session(); s.trust_env=False
sina=s.get('https://hq.sinajs.cn/list=sh600312',headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'},timeout=20)
sina_text=sina.content.decode('gb18030','ignore')
print('SINA',sina_text)
tx=s.get('https://qt.gtimg.cn/q=sh600312',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
tx_text=tx.content.decode('gbk','ignore')
print('TENCENT',tx_text[:800])
# Save raw quote
(outdir/'平高电气_quote_raw.txt').write_text(sina_text+'\n'+tx_text, encoding='utf-8')
# Parse quote
sina_body=sina_text.split('="',1)[1].rsplit('"',1)[0].split(',')
tx_body=tx_text.split('="',1)[1].rsplit('"',1)[0].split('~')
quote={
 'sina_name':sina_body[0], 'sina_close':float(sina_body[3]), 'sina_date':sina_body[30], 'sina_time':sina_body[31], 'sina_volume_shares':int(sina_body[8]), 'sina_amount_yuan':float(sina_body[9]),
 'tencent_name':tx_body[1], 'tencent_price':float(tx_body[3]), 'tencent_date_time':tx_body[30], 'tencent_market_cap_yi':float(tx_body[44]), 'tencent_total_shares':int(tx_body[72]), 'tencent_pe_ttm':float(tx_body[39]), 'tencent_pb':float(tx_body[46])
}
print(json.dumps(quote,ensure_ascii=False,indent=2))
(outdir/'平高电气_quote_parsed.json').write_text(json.dumps(quote,ensure_ascii=False,indent=2),encoding='utf-8')
# Financial rigor calls
cmds=[
 ['python','tools/financial_rigor.py','verify-market-cap','--price',str(quote['tencent_price']),'--shares',str(quote['tencent_total_shares']),'--reported',str(quote['tencent_market_cap_yi']*1e8),'--currency','CNY'],
 ['python','tools/financial_rigor.py','verify-valuation','--price',str(quote['tencent_price']),'--eps','0.8253','--bvps','8.288862','--fcf-per-share','0.5974','--dividend','0.26','--revenue-per-share',str(12516931784.56/1356921309)],
 ['python','tools/financial_rigor.py','three-scenario','--price',str(quote['tencent_price']),'--eps','0.8253','--shares','13.56921309','--growth','0.12','0.06','-0.02','--pe','22','17','12','--years','3','--currency','CNY'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2025营业收入','--values',json.dumps({'巨潮年报':125.1693178456,'AkShare东方财富口径':125.1693178456},ensure_ascii=False),'--unit','亿元'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2026Q1归母净利润','--values',json.dumps({'巨潮一季报':4.148464791,'AkShare东方财富口径':4.148464791},ensure_ascii=False),'--unit','亿元'],
]
rig=[]
for c in cmds:
    p=subprocess.run(c,cwd=root,capture_output=True,text=True,encoding='utf-8')
    rig.append('$ '+' '.join(c)+'\n'+p.stdout+p.stderr)
    print(rig[-1])
(outdir/'financial_rigor_outputs.txt').write_text('\n\n'.join(rig),encoding='utf-8')
