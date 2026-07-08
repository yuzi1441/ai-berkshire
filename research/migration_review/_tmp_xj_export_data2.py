import akshare as ak, pandas as pd, pathlib, json, requests, re
out=pathlib.Path('data/xj-electric'); out.mkdir(parents=True, exist_ok=True)
symbol='000400'
abstract=ak.stock_financial_abstract(symbol=symbol)
indicator=ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2020')
quote={}
# raw quote
s=requests.get('https://hq.sinajs.cn/list=sz000400',headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
quote['sina_raw']=s.text
m=re.search(r'="(.*)"', s.text)
if m:
 parts=m.group(1).split(',')
 quote['sina']={'name':parts[0],'open':float(parts[1]),'prev_close':float(parts[2]),'price':float(parts[3]),'high':float(parts[4]),'low':float(parts[5]),'volume_shares':int(parts[8]),'amount_yuan':float(parts[9]),'date':parts[30],'time':parts[31]}
t=requests.get('https://qt.gtimg.cn/q=sz000400',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
quote['tencent_raw']=t.text
m=re.search(r'="(.*)"',t.text)
if m:
 p=m.group(1).split('~')
 quote['tencent']={'name':p[1],'code':p[2],'price':float(p[3]),'prev_close':float(p[4]),'open':float(p[5]),'volume_lot':int(p[6]),'datetime':p[30],'change':float(p[31]),'pct':float(p[32]),'high':float(p[33]),'low':float(p[34]),'turnover_pct':float(p[38]),'pe_ttm':float(p[39]),'float_cap_yi':float(p[44]),'market_cap_yi':float(p[45]),'pb':float(p[46]),'shares_total':int(p[72]),'shares_float':int(p[73])}
(out/'quote_sina_tencent_000400.json').write_text(json.dumps(quote,ensure_ascii=False,indent=2),encoding='utf-8')
cols=['20260331','20251231','20241231','20231231','20221231','20211231']
keys=['归母净利润','营业总收入','营业成本','扣非净利润','经营活动产生的现金流量净额','资产总计','归属于母公司股东权益合计','基本每股收益','加权净资产收益率','毛利率','销售净利率','资产负债率']
summary={'quote':quote}
for key in keys:
 row=abstract[abstract['指标'].astype(str).str.contains(key, na=False)]
 if not row.empty:
  summary[key]={c: (None if pd.isna(row.iloc[0][c]) else float(row.iloc[0][c])) for c in cols if c in row.columns}
# selected indicator rows date sorted
summary['em_indicator_selected']=indicator.tail(5).to_dict(orient='records')
(out/'summary_000400.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str)[:7000])
