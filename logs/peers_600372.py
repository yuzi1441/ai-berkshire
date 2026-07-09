import akshare as ak, pandas as pd, pathlib, requests, json, re
codes=['600760','600893','600038','000768','600372']
# Try spot em via akshare
try:
 df=ak.stock_zh_a_spot_em()
 print(df.columns.tolist())
 sub=df[df['代码'].isin(codes)]
 print(sub.to_string())
 sub.to_csv('data/600372/peer_quotes_em.csv',index=False,encoding='utf-8-sig')
except Exception as e:
 print('ERR spot',e)
# financial abstract for peers latest
rows=[]
for code in codes:
 try:
  f=ak.stock_financial_abstract(symbol=code)
  def get(ind, col):
   s=f.loc[f['指标'].eq(ind), col]
   return None if s.empty else float(s.iloc[0])
  rows.append({'code':code,'rev2025':get('营业总收入','20251231'),'np2025':get('归母净利润','20251231'),'roe2025':get('净资产收益率(ROE)','20251231'),'eps2025':get('基本每股收益','20251231'),'bvps2025':get('每股净资产','20251231'),'debt_ratio2025':get('资产负债率','20251231')})
 except Exception as e:
  rows.append({'code':code,'err':str(e)})
pd.DataFrame(rows).to_csv('data/600372/peer_financial_2025.csv',index=False,encoding='utf-8-sig')
print(pd.DataFrame(rows).to_string())