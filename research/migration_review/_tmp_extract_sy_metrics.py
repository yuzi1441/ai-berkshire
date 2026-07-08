import akshare as ak, pandas as pd, json, pathlib, math
pd.set_option('display.max_columns', 120); pd.set_option('display.width', 240)
out=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\中国神华\_data_extract.txt')
parts=[]
fa=ak.stock_financial_abstract(symbol='601088')
parts.append('FA rows/cols '+str(fa.shape))
parts.append('指标列表:\n'+fa[['选项','指标']].to_string())
cols=['20260331','20251231','20241231','20231231','20221231','20211231']
sel=fa[['选项','指标']+cols].copy()
keywords=['归母净利润','营业总收入','净利润','基本每股收益','每股净资产','净资产收益率','销售毛利率','销售净利率','资产负债率','经营活动产生的现金流量净额','购建固定资产、无形资产和其他长期资产支付的现金','每股经营现金流','每股资本公积金','每股未分配利润','总资产','股东权益合计','货币资金','有息负债']
mask=sel['指标'].astype(str).apply(lambda x:any(k in x for k in keywords))
parts.append('\nSelected FA:\n'+sel[mask].to_string())
# reports
for sym in ['资产负债表','利润表','现金流量表']:
 try:
  df=ak.stock_financial_report_sina(stock='sh601088', symbol=sym)
  parts.append('\nREPORT '+sym+' '+str(df.shape)+' cols='+','.join(map(str,df.columns[:20])))
  parts.append(df.head(8).to_string())
 except Exception as e:
  parts.append('\nERR '+sym+' '+repr(e))
# spot em/sina maybe
try:
 spot=ak.stock_zh_a_spot_em()
 row=spot[spot['代码'].astype(str)=='601088']
 parts.append('\nSPOT EM:\n'+row.to_string())
except Exception as e: parts.append('\nERR spot '+repr(e))
# dividends funcs names
for fname in ['stock_dividend_cninfo','stock_history_dividend_detail','stock_fhps_em','stock_dividend_detail_cninfo']:
 if hasattr(ak,fname):
  try:
   import inspect
   parts.append('\nFUNC '+fname+' sig '+str(inspect.signature(getattr(ak,fname))))
  except Exception as e: parts.append('sig err '+fname+repr(e))
out.write_text('\n'.join(parts), encoding='utf-8')
print(out)