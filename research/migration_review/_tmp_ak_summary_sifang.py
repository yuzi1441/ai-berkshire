from pathlib import Path
import akshare as ak, pandas as pd, json, math
sym='601126'
# financial abstract
absdf=ak.stock_financial_abstract(symbol=sym)
metrics=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','销售毛利率','销售净利率','净资产收益率ROE(加权)','资产负债率','总资产','归属母公司股东权益合计','基本每股收益','每股净资产']
cols=['指标']+[c for c in absdf.columns if str(c).isdigit() and str(c) in ['20260331','20251231','20241231','20231231','20221231','20211231']]
sel=absdf[absdf['指标'].isin(metrics)][cols]
print('ABSTRACT')
print(sel.to_string(index=False))
# history for 2026-07-06
hist=ak.stock_zh_a_hist(symbol=sym, period='daily', start_date='20260706', end_date='20260706', adjust='')
print('HIST')
print(hist.to_string(index=False))
# spot eastmoney all market filtered maybe slow
spot=ak.stock_zh_a_spot_em()
row=spot[spot['代码'].astype(str)==sym]
print('SPOT')
print(row.to_string(index=False))
# save json/csv
out=Path('data/raw/sifang/akshare_sifang_summary.csv'); sel.to_csv(out,index=False,encoding='utf-8-sig')
row.to_csv('data/raw/sifang/akshare_spot.csv',index=False,encoding='utf-8-sig')
hist.to_csv('data/raw/sifang/akshare_hist_20260706.csv',index=False,encoding='utf-8-sig')